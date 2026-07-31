#!/usr/bin/env python3
"""Shared utilities for counterfactual macro-profile value learning."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import nn


CHECKPOINT_VERSION = 1


class ProfileValueNet(nn.Module):
    """Predict the final-margin advantage of every macro profile."""

    def __init__(
        self,
        feature_count: int,
        profile_count: int,
        *,
        hidden_size: int = 512,
        hidden_layers: int = 3,
    ) -> None:
        super().__init__()
        layers: list[nn.Module] = []
        width = feature_count
        for _ in range(hidden_layers):
            layers.extend(
                (
                    nn.Linear(width, hidden_size),
                    nn.LayerNorm(hidden_size),
                    nn.SiLU(),
                )
            )
            width = hidden_size
        self.encoder = nn.Sequential(*layers)
        self.head = nn.Linear(width, profile_count)
        self.apply(self._initialize)

    @staticmethod
    def _initialize(module: nn.Module) -> None:
        if isinstance(module, nn.Linear):
            nn.init.orthogonal_(module.weight)
            nn.init.zeros_(module.bias)

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        return self.head(self.encoder(features))


def load_contexts(
    paths: list[Path],
) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    """Load complete seed/seat counterfactual matrices from JSON reports."""
    games: list[dict[str, Any]] = []
    declared_profiles: set[str] | None = None
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        current = set(payload.get("profiles", {}))
        declared_profiles = (
            current
            if declared_profiles is None
            else declared_profiles & current
        )
        games.extend(payload.get("games", []))
    if not games or not declared_profiles:
        raise RuntimeError("No counterfactual games or common profiles found")
    if "KEEP" not in declared_profiles:
        raise RuntimeError("Counterfactual data must include KEEP")

    grouped: dict[tuple[int, int], dict[str, dict[str, Any]]] = defaultdict(dict)
    for game in games:
        profile = str(game["profile"])
        if profile in declared_profiles and game.get("features") is not None:
            grouped[(int(game["seed"]), int(game["seat"]))][profile] = game

    profile_names = sorted(declared_profiles)
    feature_names = sorted(
        next(iter(next(iter(grouped.values())).values()))["features"]
    )
    contexts = []
    for (seed, seat), by_profile in sorted(grouped.items()):
        if any(profile not in by_profile for profile in profile_names):
            continue
        feature_signatures = {
            tuple(float(game["features"][name]) for name in feature_names)
            for game in by_profile.values()
        }
        if len(feature_signatures) != 1:
            raise RuntimeError(
                f"Profiles do not share a decision state for seed={seed}, seat={seat}"
            )
        margins = np.asarray(
            [float(by_profile[name]["margin"]) for name in profile_names],
            dtype=np.float32,
        )
        keep_margin = float(by_profile["KEEP"]["margin"])
        contexts.append(
            {
                "seed": seed,
                "seat": seat,
                "features": np.asarray(next(iter(feature_signatures)), dtype=np.float32),
                "advantages": margins - keep_margin,
                "margins": margins,
            }
        )
    if not contexts:
        raise RuntimeError("No complete counterfactual contexts found")
    return feature_names, profile_names, contexts


def save_value_checkpoint(
    path: Path,
    model: ProfileValueNet,
    *,
    feature_names: list[str],
    profile_names: list[str],
    feature_mean: np.ndarray,
    feature_scale: np.ndarray,
    target_scale: float,
    hidden_size: int,
    hidden_layers: int,
    metadata: dict[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "checkpoint_version": CHECKPOINT_VERSION,
            "feature_names": feature_names,
            "profile_names": profile_names,
            "feature_mean": feature_mean.astype(np.float32),
            "feature_scale": feature_scale.astype(np.float32),
            "target_scale": float(target_scale),
            "hidden_size": int(hidden_size),
            "hidden_layers": int(hidden_layers),
            "model_state": {
                key: value.detach().cpu() for key, value in model.state_dict().items()
            },
            "metadata": metadata,
        },
        path,
    )


def load_value_checkpoint(
    path: Path, device: str | torch.device = "cpu"
) -> tuple[ProfileValueNet, dict[str, Any]]:
    payload = torch.load(path, map_location=device, weights_only=False)
    if int(payload.get("checkpoint_version", -1)) != CHECKPOINT_VERSION:
        raise RuntimeError(f"Unsupported value checkpoint: {path}")
    model = ProfileValueNet(
        len(payload["feature_names"]),
        len(payload["profile_names"]),
        hidden_size=int(payload["hidden_size"]),
        hidden_layers=int(payload["hidden_layers"]),
    ).to(device)
    model.load_state_dict(payload["model_state"])
    model.eval()
    return model, payload

