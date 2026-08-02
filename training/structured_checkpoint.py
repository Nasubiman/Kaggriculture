#!/usr/bin/env python3
"""Checkpoint IO for the structured Kaggriculture policy."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

import torch

from structured_policy import (
    STRUCTURED_POLICY_VERSION,
    StructuredActorCritic,
    StructuredPolicyConfig,
)


def save_structured_checkpoint(
    path: Path,
    model: StructuredActorCritic,
    update: int,
    metadata: dict[str, Any] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            **model.checkpoint_metadata(),
            "update": int(update),
            "model_state": {
                key: value.detach().cpu() for key, value in model.state_dict().items()
            },
            "metadata": metadata or {},
        },
        path,
    )


def load_structured_checkpoint(
    path: Path,
    device: str | torch.device = "cpu",
) -> tuple[StructuredActorCritic, dict[str, Any]]:
    payload = torch.load(path, map_location=device, weights_only=False)
    if int(payload.get("policy_version", -1)) != STRUCTURED_POLICY_VERSION:
        raise RuntimeError(f"Unsupported structured checkpoint: {path}")
    if payload.get("architecture") != "structured_transformer_v1":
        raise RuntimeError(f"Unexpected architecture in {path}")
    config = StructuredPolicyConfig(**dict(payload["config"]))
    model = StructuredActorCritic(config).to(device)
    model.load_state_dict(payload["model_state"])
    model.eval()
    return model, payload


def describe_structured_checkpoint(path: Path) -> dict[str, Any]:
    model, payload = load_structured_checkpoint(path)
    return {
        "path": str(path),
        "update": int(payload.get("update", 0)),
        "architecture": payload["architecture"],
        "config": asdict(model.config),
        "parameters": sum(parameter.numel() for parameter in model.parameters()),
        "metadata": payload.get("metadata", {}),
    }
