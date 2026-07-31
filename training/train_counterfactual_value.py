#!/usr/bin/env python3
"""Train a GPU macro-profile value/ranking model from counterfactual games."""

from __future__ import annotations

import argparse
import json
import random
import time
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F

from counterfactual_value import (
    ProfileValueNet,
    load_contexts,
    save_value_checkpoint,
)


def metrics(predictions: np.ndarray, targets: np.ndarray, profiles: list[str]) -> dict[str, Any]:
    chosen = predictions.argmax(axis=1)
    oracle = targets.argmax(axis=1)
    rows = np.arange(len(targets))
    regret = targets[rows, oracle] - targets[rows, chosen]
    keep = profiles.index("KEEP")
    selected_gain = targets[rows, chosen]
    return {
        "contexts": int(len(targets)),
        "top1_accuracy": float(np.mean(chosen == oracle)),
        "mean_regret": float(np.mean(regret)),
        "median_regret": float(np.median(regret)),
        "zero_regret_rate": float(np.mean(regret == 0)),
        "mean_selected_advantage": float(np.mean(selected_gain)),
        "mean_keep_advantage": float(np.mean(targets[:, keep])),
        "oracle_mean_advantage": float(np.mean(targets[rows, oracle])),
        "selected_profiles": dict(
            sorted(Counter(profiles[index] for index in chosen).items())
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, nargs="+", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--validation-input", type=Path, nargs="+")
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    parser.add_argument("--epochs", type=int, default=500)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--hidden-size", type=int, default=512)
    parser.add_argument("--hidden-layers", type=int, default=3)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--ranking-coefficient", type=float, default=0.25)
    parser.add_argument("--classification-coefficient", type=float, default=0.25)
    parser.add_argument("--target-scale", type=float, default=25_000.0)
    parser.add_argument("--patience", type=int, default=80)
    parser.add_argument("--seed", type=int, default=20260731)
    parser.add_argument("--device", default="cuda")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")

    feature_names, profile_names, contexts = load_contexts(
        [path.resolve() for path in args.input]
    )
    rng = np.random.default_rng(args.seed)
    rng.shuffle(contexts)
    if args.validation_input:
        val_features, val_profiles, validation = load_contexts(
            [path.resolve() for path in args.validation_input]
        )
        if val_features != feature_names or val_profiles != profile_names:
            raise RuntimeError("Training and validation schemas differ")
        training = contexts
    else:
        validation_size = max(1, round(len(contexts) * args.validation_fraction))
        validation = contexts[:validation_size]
        training = contexts[validation_size:]
    if not training or not validation:
        raise RuntimeError("Training and validation sets must both be non-empty")

    train_x = np.stack([item["features"] for item in training])
    train_y = np.stack([item["advantages"] for item in training])
    val_x = np.stack([item["features"] for item in validation])
    val_y = np.stack([item["advantages"] for item in validation])
    feature_mean = train_x.mean(axis=0)
    feature_scale = train_x.std(axis=0)
    feature_scale[feature_scale < 1e-6] = 1.0
    train_x = (train_x - feature_mean) / feature_scale
    val_x = (val_x - feature_mean) / feature_scale

    train_features = torch.from_numpy(train_x).to(device)
    train_targets = torch.from_numpy(train_y / args.target_scale).to(device)
    val_features_tensor = torch.from_numpy(val_x).to(device)
    model = ProfileValueNet(
        len(feature_names),
        len(profile_names),
        hidden_size=args.hidden_size,
        hidden_layers=args.hidden_layers,
    ).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay
    )
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    best_regret = float("inf")
    best_epoch = 0
    best_state = None
    started = time.monotonic()
    history = []

    for epoch in range(1, args.epochs + 1):
        model.train()
        order = torch.randperm(len(training), device=device)
        epoch_losses = []
        for start in range(0, len(training), args.batch_size):
            indices = order[start : start + args.batch_size]
            targets = train_targets[indices]
            predicted = model(train_features[indices])
            regression = F.smooth_l1_loss(predicted, targets)
            target_diff = targets.unsqueeze(2) - targets.unsqueeze(1)
            prediction_diff = predicted.unsqueeze(2) - predicted.unsqueeze(1)
            signs = torch.sign(target_diff)
            comparable = signs != 0
            ranking = (
                F.softplus(-signs * prediction_diff)[comparable].mean()
                if bool(comparable.any())
                else predicted.sum() * 0.0
            )
            classification = F.cross_entropy(predicted, targets.argmax(dim=1))
            loss = (
                regression
                + args.ranking_coefficient * ranking
                + args.classification_coefficient * classification
            )
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            epoch_losses.append(float(loss.detach()))

        if epoch == 1 or epoch % 10 == 0 or epoch == args.epochs:
            model.eval()
            with torch.no_grad():
                predictions = (
                    model(val_features_tensor).cpu().numpy() * args.target_scale
                )
            validation_metrics = metrics(predictions, val_y, profile_names)
            record = {
                "epoch": epoch,
                "loss": float(np.mean(epoch_losses)),
                "validation": validation_metrics,
            }
            history.append(record)
            regret = validation_metrics["mean_regret"]
            if regret < best_regret:
                best_regret = regret
                best_epoch = epoch
                best_state = {
                    key: value.detach().cpu().clone()
                    for key, value in model.state_dict().items()
                }
            if epoch - best_epoch >= args.patience:
                break

    if best_state is None:
        raise RuntimeError("Training produced no checkpoint")
    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        train_predictions = model(train_features).cpu().numpy() * args.target_scale
        val_predictions = model(val_features_tensor).cpu().numpy() * args.target_scale
    result = {
        "elapsed_seconds": time.monotonic() - started,
        "device": str(device),
        "gpu": torch.cuda.get_device_name(device) if device.type == "cuda" else None,
        "gpu_peak_memory_mb": (
            torch.cuda.max_memory_allocated(device) / 2**20
            if device.type == "cuda"
            else 0.0
        ),
        "feature_count": len(feature_names),
        "profiles": profile_names,
        "training": metrics(train_predictions, train_y, profile_names),
        "validation": metrics(val_predictions, val_y, profile_names),
        "best_epoch": best_epoch,
        "history": history,
        "arguments": {
            key: [str(item) for item in value]
            if isinstance(value, list) and value and isinstance(value[0], Path)
            else str(value)
            if isinstance(value, Path)
            else value
            for key, value in vars(args).items()
        },
    }
    (output_dir / "metrics.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    save_value_checkpoint(
        output_dir / "best.pt",
        model,
        feature_names=feature_names,
        profile_names=profile_names,
        feature_mean=feature_mean,
        feature_scale=feature_scale,
        target_scale=args.target_scale,
        hidden_size=args.hidden_size,
        hidden_layers=args.hidden_layers,
        metadata=result,
    )
    print(json.dumps({key: result[key] for key in ("elapsed_seconds", "device", "gpu_peak_memory_mb", "training", "validation", "best_epoch")}, indent=2))


if __name__ == "__main__":
    main()
