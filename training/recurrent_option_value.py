#!/usr/bin/env python3
"""Recurrent conservative option-value model for Kaggriculture.

The low-level scripted agent remains responsible for all legal 720-turn play.
This model is used only at sparse strategic decision points.  It consumes a
history of public/private summary features and scores coherent, validated
strategy options by their expected final-margin advantage over KEEP.

Why this is not a direct PPO policy:
- the opponent's shed, seeds, and inventories are hidden, so one snapshot is
  not Markov;
- terminal money is the true objective and intermediate cash is a poor proxy
  for productive assets;
- existing branched counterfactual data gives much stronger supervision than
  sparse on-policy daily rewards;
- the incumbent is already strong, so uncertain interventions should abstain.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import torch
from torch import nn


MODEL_VERSION = 1


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
    """Scores coherent options from a belief state over decision history.

    Inputs
    ------
    state_history:
        ``(batch, time, state_dim)`` snapshots at sparse decision points.
    lengths:
        ``(batch,)`` valid sequence lengths. Padding must be at the end.
    option_features:
        ``(options, option_dim)`` or ``(batch, options, option_dim)``.

    Output
    ------
    Per-head advantages with shape ``(heads, batch, options)``.  Values are
    defined relative to KEEP by subtracting the selected KEEP score from every
    option, so KEEP is exactly zero for every head.
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
        # Each head receives [belief, option, belief*option, |belief-option|].
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
            raise ValueError("option_features must have shape (options, dim) or (batch, options, dim)")
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
        """Conservatively choose an option, abstaining to KEEP when uncertain.

        The lower-confidence score is ``mean - uncertainty_scale * std``.
        Non-KEEP options must additionally exceed ``minimum_advantage``.
        """
        per_head = self(state_history, lengths, option_features)
        mean = per_head.mean(dim=0)
        std = per_head.std(dim=0, unbiased=False)
        lower = mean - self.config.uncertainty_scale * std
        if valid_mask is not None:
            if valid_mask.shape != mean.shape:
                raise ValueError("valid_mask must match (batch, options)")
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
            "architecture": "recurrent_conservative_option_value_v1",
            "config": asdict(self.config),
        }


def save_checkpoint(
    path: Path,
    model: RecurrentOptionValueNet,
    *,
    option_names: list[str],
    state_feature_names: list[str],
    option_feature_names: list[str],
    metadata: dict[str, Any] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            **model.metadata(),
            "option_names": option_names,
            "state_feature_names": state_feature_names,
            "option_feature_names": option_feature_names,
            "model_state": {
                key: value.detach().cpu() for key, value in model.state_dict().items()
            },
            "metadata": metadata or {},
        },
        path,
    )


def load_checkpoint(
    path: Path, device: str | torch.device = "cpu"
) -> tuple[RecurrentOptionValueNet, dict[str, Any]]:
    payload = torch.load(path, map_location=device, weights_only=False)
    if payload.get("architecture") != "recurrent_conservative_option_value_v1":
        raise RuntimeError(f"unsupported checkpoint architecture: {path}")
    if int(payload.get("model_version", -1)) != MODEL_VERSION:
        raise RuntimeError(f"unsupported checkpoint version: {path}")
    model = RecurrentOptionValueNet(
        OptionValueConfig(**dict(payload["config"]))
    ).to(device)
    model.load_state_dict(payload["model_state"])
    model.eval()
    return model, payload
