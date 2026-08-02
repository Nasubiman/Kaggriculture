#!/usr/bin/env python3
"""Conservative recurrent value model for selecting whole farm schedules.

The 720-turn execution engine remains deterministic.  This model is not a raw
turn policy and is not intended to switch freely between incompatible plans.
It scores complete, versioned schedule options at game start or at explicitly
validated re-entry checkpoints.  A separate repair model handles local drift.

The model consumes sparse history snapshots because the opponent's private
shed, seeds, and carried inventories are hidden.  Each ensemble head predicts
terminal-margin advantage relative to KEEP, and inference abstains unless the
lower confidence bound is convincingly positive.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import torch
from torch import nn
from torch.nn import functional as F


MODEL_VERSION = 2
ARCHITECTURE = "recurrent_schedule_value_v2"


@dataclass(frozen=True)
class OptionValueConfig:
    state_dim: int
    option_dim: int
    hidden_dim: int = 192
    recurrent_layers: int = 1
    ensemble_heads: int = 5
    dropout: float = 0.0
    keep_index: int = 0
    uncertainty_scale: float = 1.0
    minimum_advantage: float = 0.0

    def validate(self) -> None:
        if self.state_dim <= 0 or self.option_dim <= 0:
            raise ValueError("state_dim and option_dim must be positive")
        if self.hidden_dim <= 0 or self.recurrent_layers <= 0:
            raise ValueError("hidden dimensions must be positive")
        if self.ensemble_heads < 2:
            raise ValueError("at least two ensemble heads are required")
        if self.keep_index < 0:
            raise ValueError("keep_index must be non-negative")
        if self.uncertainty_scale < 0:
            raise ValueError("uncertainty_scale must be non-negative")
        if self.dropout < 0 or self.dropout >= 1:
            raise ValueError("dropout must be in [0, 1)")


class ResidualMLP(nn.Module):
    def __init__(self, width: int, dropout: float) -> None:
        super().__init__()
        self.norm = nn.LayerNorm(width)
        self.net = nn.Sequential(
            nn.Linear(width, width * 2),
            nn.SiLU(),
            nn.Dropout(dropout),
            nn.Linear(width * 2, width),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.net(self.norm(x))


class RecurrentOptionValueNet(nn.Module):
    """Score complete schedule options from a belief over sparse history.

    ``state_history`` has shape ``(batch, time, state_dim)`` and padding is at
    the end. ``option_features`` may be shared across the batch or supplied per
    sample.  Output shape is ``(heads, batch, options)``.  KEEP is exactly zero
    for every head by construction.
    """

    def __init__(self, config: OptionValueConfig) -> None:
        super().__init__()
        config.validate()
        self.config = config
        h = config.hidden_dim
        self.state_stem = nn.Sequential(
            nn.LayerNorm(config.state_dim),
            nn.Linear(config.state_dim, h),
            nn.SiLU(),
            ResidualMLP(h, config.dropout),
        )
        self.gru = nn.GRU(
            input_size=h,
            hidden_size=h,
            num_layers=config.recurrent_layers,
            dropout=config.dropout if config.recurrent_layers > 1 else 0.0,
            batch_first=True,
        )
        self.option_stem = nn.Sequential(
            nn.LayerNorm(config.option_dim),
            nn.Linear(config.option_dim, h),
            nn.SiLU(),
            ResidualMLP(h, config.dropout),
        )
        self.context = nn.Sequential(
            nn.LayerNorm(h),
            nn.Linear(h, h),
            nn.SiLU(),
        )
        joint_dim = 4 * h
        self.heads = nn.ModuleList(
            nn.Sequential(
                nn.LayerNorm(joint_dim),
                nn.Linear(joint_dim, h),
                nn.SiLU(),
                nn.Linear(h, 1),
            )
            for _ in range(config.ensemble_heads)
        )
        self.reset_parameters()

    def reset_parameters(self) -> None:
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
        for name, parameter in self.gru.named_parameters():
            if "weight_ih" in name:
                nn.init.xavier_uniform_(parameter)
            elif "weight_hh" in name:
                nn.init.orthogonal_(parameter)
            elif "bias" in name:
                nn.init.zeros_(parameter)

    def encode_history(
        self, state_history: torch.Tensor, lengths: torch.Tensor
    ) -> torch.Tensor:
        if state_history.ndim != 3:
            raise ValueError("state_history must have shape (batch, time, state_dim)")
        if state_history.shape[-1] != self.config.state_dim:
            raise ValueError("unexpected state feature width")
        if lengths.ndim != 1 or lengths.shape[0] != state_history.shape[0]:
            raise ValueError("lengths must have shape (batch,)")
        if torch.any(lengths <= 0) or torch.any(lengths > state_history.shape[1]):
            raise ValueError("lengths must be in [1, time]")
        encoded = self.state_stem(state_history)
        packed = nn.utils.rnn.pack_padded_sequence(
            encoded,
            lengths.detach().cpu(),
            batch_first=True,
            enforce_sorted=False,
        )
        _, hidden = self.gru(packed)
        return self.context(hidden[-1])

    def forward(
        self,
        state_history: torch.Tensor,
        lengths: torch.Tensor,
        option_features: torch.Tensor,
    ) -> torch.Tensor:
        belief = self.encode_history(state_history, lengths)
        if option_features.ndim == 2:
            option_features = option_features.unsqueeze(0).expand(
                state_history.shape[0], -1, -1
            )
        if option_features.ndim != 3:
            raise ValueError(
                "option_features must have shape (options, dim) or "
                "(batch, options, dim)"
            )
        if option_features.shape[0] != state_history.shape[0]:
            raise ValueError("option batch does not match state batch")
        if option_features.shape[-1] != self.config.option_dim:
            raise ValueError("unexpected option feature width")
        if self.config.keep_index >= option_features.shape[1]:
            raise ValueError("keep_index is outside the option axis")

        option = self.option_stem(option_features)
        belief_expanded = belief.unsqueeze(1).expand_as(option)
        joint = torch.cat(
            (
                belief_expanded,
                option,
                belief_expanded * option,
                torch.abs(belief_expanded - option),
            ),
            dim=-1,
        )
        raw = torch.stack(
            [head(joint).squeeze(-1) for head in self.heads], dim=0
        )
        keep = raw[:, :, self.config.keep_index : self.config.keep_index + 1]
        return raw - keep

    @torch.no_grad()
    def select(
        self,
        state_history: torch.Tensor,
        lengths: torch.Tensor,
        option_features: torch.Tensor,
        valid_mask: torch.Tensor | None = None,
    ) -> dict[str, torch.Tensor]:
        """Choose a schedule only when its conservative advantage is positive."""
        per_head = self(state_history, lengths, option_features)
        mean = per_head.mean(dim=0)
        std = per_head.std(dim=0, unbiased=False)
        lower = mean - self.config.uncertainty_scale * std
        if valid_mask is not None:
            if valid_mask.shape != mean.shape:
                raise ValueError("valid_mask must match (batch, options)")
            if not torch.all(valid_mask[:, self.config.keep_index]):
                raise ValueError("KEEP must always be valid")
            lower = lower.masked_fill(~valid_mask, -torch.inf)
        lower[:, self.config.keep_index] = 0.0
        action = lower.argmax(dim=-1)
        chosen = lower.gather(1, action.unsqueeze(1)).squeeze(1)
        abstain = chosen <= self.config.minimum_advantage
        action = torch.where(
            abstain,
            torch.full_like(action, self.config.keep_index),
            action,
        )
        return {
            "action": action,
            "mean_advantage": mean,
            "uncertainty": std,
            "lower_confidence_advantage": lower,
        }

    def metadata(self) -> dict[str, Any]:
        return {
            "model_version": MODEL_VERSION,
            "architecture": ARCHITECTURE,
            "config": asdict(self.config),
        }


def counterfactual_value_loss(
    per_head_advantages: torch.Tensor,
    target_advantages: torch.Tensor,
    *,
    valid_mask: torch.Tensor | None = None,
    bootstrap_mask: torch.Tensor | None = None,
    ranking_weight: float = 0.25,
    false_positive_weight: float = 0.5,
) -> dict[str, torch.Tensor]:
    """Loss for full-information counterfactual schedule outcomes.

    ``per_head_advantages`` is ``(heads, batch, options)`` and targets are
    terminal-margin advantages over KEEP.  ``bootstrap_mask`` has shape
    ``(heads, batch)`` and lets each ensemble member train on a different
    resample.  Harmful schedules predicted as profitable receive an asymmetric
    false-positive penalty because such mistakes are costlier than abstention.
    """
    if per_head_advantages.ndim != 3:
        raise ValueError("per_head_advantages must have shape (heads, batch, options)")
    heads, batch, options = per_head_advantages.shape
    if target_advantages.shape != (batch, options):
        raise ValueError("target_advantages must match (batch, options)")
    if valid_mask is None:
        valid_mask = torch.ones_like(target_advantages, dtype=torch.bool)
    if valid_mask.shape != target_advantages.shape:
        raise ValueError("valid_mask must match target_advantages")
    if bootstrap_mask is None:
        bootstrap_mask = torch.ones(
            heads, batch, dtype=torch.bool, device=per_head_advantages.device
        )
    if bootstrap_mask.shape != (heads, batch):
        raise ValueError("bootstrap_mask must have shape (heads, batch)")

    expanded_target = target_advantages.unsqueeze(0).expand_as(per_head_advantages)
    active = bootstrap_mask.unsqueeze(-1) & valid_mask.unsqueeze(0)
    if not torch.any(active):
        raise ValueError("loss has no active samples")

    regression_values = F.smooth_l1_loss(
        per_head_advantages, expanded_target, reduction="none"
    )
    regression = regression_values[active].mean()

    pred_diff = per_head_advantages.unsqueeze(-1) - per_head_advantages.unsqueeze(-2)
    target_diff = target_advantages.unsqueeze(-1) - target_advantages.unsqueeze(-2)
    sign = torch.sign(target_diff).unsqueeze(0)
    comparable = sign != 0
    pair_valid = valid_mask.unsqueeze(-1) & valid_mask.unsqueeze(-2)
    pair_active = (
        bootstrap_mask.unsqueeze(-1).unsqueeze(-1)
        & pair_valid.unsqueeze(0)
        & comparable
    )
    ranking_values = F.softplus(-sign * pred_diff)
    ranking = (
        ranking_values[pair_active].mean()
        if torch.any(pair_active)
        else regression.new_zeros(())
    )

    harmful = expanded_target < 0
    false_positive_active = active & harmful
    false_positive = (
        F.softplus(per_head_advantages[false_positive_active]).mean()
        if torch.any(false_positive_active)
        else regression.new_zeros(())
    )
    total = regression + ranking_weight * ranking + false_positive_weight * false_positive
    return {
        "loss": total,
        "regression": regression,
        "ranking": ranking,
        "false_positive": false_positive,
    }


def save_checkpoint(
    path: Path,
    model: RecurrentOptionValueNet,
    *,
    option_names: list[str],
    state_feature_names: list[str],
    option_feature_names: list[str],
    registry_fingerprint: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            **model.metadata(),
            "option_names": option_names,
            "state_feature_names": state_feature_names,
            "option_feature_names": option_feature_names,
            "registry_fingerprint": registry_fingerprint,
            "model_state": {
                key: value.detach().cpu() for key, value in model.state_dict().items()
            },
            "metadata": metadata or {},
        },
        path,
    )


def load_checkpoint(
    path: Path,
    device: str | torch.device = "cpu",
    *,
    expected_registry_fingerprint: str | None = None,
) -> tuple[RecurrentOptionValueNet, dict[str, Any]]:
    payload = torch.load(path, map_location=device, weights_only=False)
    if payload.get("architecture") != ARCHITECTURE:
        raise RuntimeError(f"unsupported checkpoint architecture: {path}")
    if int(payload.get("model_version", -1)) != MODEL_VERSION:
        raise RuntimeError(f"unsupported checkpoint version: {path}")
    if (
        expected_registry_fingerprint is not None
        and payload.get("registry_fingerprint") != expected_registry_fingerprint
    ):
        raise RuntimeError("checkpoint schedule registry does not match runtime registry")
    model = RecurrentOptionValueNet(
        OptionValueConfig(**dict(payload["config"]))
    ).to(device)
    model.load_state_dict(payload["model_state"])
    model.eval()
    return model, payload
