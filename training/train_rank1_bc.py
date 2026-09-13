#!/usr/bin/env python3
"""Train the hierarchical rank-1 behavior-cloning policy on a GPU."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

import numpy as np
import torch
import torch.nn.functional as F

from rank1_bc_model import build_model


def batches(indices: np.ndarray, size: int):
    for start in range(0, len(indices), size):
        yield indices[start:start+size]


@torch.no_grad()
def evaluate(model, arrays, indices, batch_size, device):
    states, actors, actor_y, market_y = arrays
    model.eval(); actor_ok = actor_total = market_ok = market_total = nonpad_ok = nonpad_total = 0
    actor_turn_ok = market_turn_ok = turns = 0
    for index in batches(indices, batch_size):
        x = torch.from_numpy(np.asarray(states[index], dtype=np.float32)).to(device)
        a = torch.from_numpy(np.asarray(actors[index], dtype=np.float32)).to(device)
        ay = torch.from_numpy(np.asarray(actor_y[index], dtype=np.int64)).to(device)
        my = torch.from_numpy(np.asarray(market_y[index], dtype=np.int64)).to(device)
        actor_logits, market_logits = model(x, a)
        ap = actor_logits.argmax(-1); mp = market_logits.argmax(-1)
        valid = ay >= 0; nonpad = my != 0
        actor_ok += int(((ap == ay) & valid).sum()); actor_total += int(valid.sum())
        market_ok += int((mp == my).sum()); market_total += my.numel()
        nonpad_ok += int(((mp == my) & nonpad).sum()); nonpad_total += int(nonpad.sum())
        actor_turn_ok += int((((ap == ay) | ~valid).all(dim=1)).sum())
        market_turn_ok += int((mp == my).all(dim=1).sum()); turns += len(index)
    return {
        "actor_command_accuracy": actor_ok / actor_total,
        "actor_exact_turn_accuracy": actor_turn_ok / turns,
        "market_slot_accuracy": market_ok / market_total,
        "market_nonpad_accuracy": nonpad_ok / max(nonpad_total, 1),
        "market_exact_turn_accuracy": market_turn_ok / turns,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--learning-rate", type=float, default=2e-3)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--seed", type=int, default=1337)
    args = parser.parse_args()
    torch.manual_seed(args.seed); np.random.seed(args.seed)
    device = torch.device(args.device if args.device != "cuda" or torch.cuda.is_available() else "cpu")
    metadata = json.loads((args.data_dir/"metadata.json").read_text())
    states = np.load(args.data_dir/"states.npy", mmap_mode="r")
    actors = np.load(args.data_dir/"actors.npy", mmap_mode="r")
    actor_y = np.load(args.data_dir/"actor_targets.npy", mmap_mode="r")
    market_y = np.load(args.data_dir/"market_targets.npy", mmap_mode="r")
    episodes = np.load(args.data_dir/"episodes.npy", mmap_mode="r")
    train_indices = np.flatnonzero(episodes % 5 != 0); validation_indices = np.flatnonzero(episodes % 5 == 0)
    model = build_model(metadata["state_size"], len(metadata["actor_vocab"]), len(metadata["market_vocab"])).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=1e-4)
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
    pad_weight = torch.ones(len(metadata["market_vocab"]), device=device); pad_weight[0] = .15
    args.output_dir.mkdir(parents=True, exist_ok=True); history = []; best = -1.0
    arrays = (states, actors, actor_y, market_y)
    for epoch in range(1, args.epochs + 1):
        started = time.time(); order = np.random.permutation(train_indices); model.train(); total_loss = 0.0; seen = 0
        for index in batches(order, args.batch_size):
            x = torch.from_numpy(np.asarray(states[index], dtype=np.float32)).to(device)
            a = torch.from_numpy(np.asarray(actors[index], dtype=np.float32)).to(device)
            ay = torch.from_numpy(np.asarray(actor_y[index], dtype=np.int64)).to(device)
            my = torch.from_numpy(np.asarray(market_y[index], dtype=np.int64)).to(device)
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(device_type=device.type, dtype=torch.float16, enabled=device.type == "cuda"):
                actor_logits, market_logits = model(x, a)
                actor_loss = F.cross_entropy(actor_logits.reshape(-1, actor_logits.shape[-1]), ay.reshape(-1), ignore_index=-1)
                market_loss = F.cross_entropy(market_logits.reshape(-1, market_logits.shape[-1]), my.reshape(-1), weight=pad_weight)
                loss = actor_loss + market_loss
            scaler.scale(loss).backward(); scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            scaler.step(optimizer); scaler.update()
            total_loss += float(loss) * len(index); seen += len(index)
        metrics = evaluate(model, arrays, validation_indices, args.batch_size, device)
        metrics.update(epoch=epoch, train_loss=total_loss/seen, seconds=time.time()-started)
        history.append(metrics); score = metrics["actor_command_accuracy"] + metrics["market_nonpad_accuracy"]
        print(json.dumps(metrics), flush=True)
        if score > best:
            best = score
            torch.save({"model": model.state_dict(), "metadata": metadata, "metrics": metrics}, args.output_dir/"best.pt")
            np.savez_compressed(args.output_dir/"best_weights.npz",
                                **{name: value.detach().cpu().numpy() for name, value in model.state_dict().items()})
            (args.output_dir/"vocab.json").write_text(json.dumps({
                "state_size": metadata["state_size"], "actor_vocab": metadata["actor_vocab"],
                "market_vocab": metadata["market_vocab"], "metrics": metrics,
            }, indent=2)+"\n")
        (args.output_dir/"history.json").write_text(json.dumps(history, indent=2)+"\n")
    print(f"best combined command accuracy={best:.4f}; output={args.output_dir}")


if __name__ == "__main__":
    main()
