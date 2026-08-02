#!/usr/bin/env python3
"""State-conditioned local repair model for an executable farm schedule.

The selected schedule remains the default policy.  This network is invoked only
when the planned command is illegal or when rule-derived deviation monitoring
flags material drift.  Candidate zero is FOLLOW_PLAN; every triggered sample
must also provide a deterministic RULE_REPAIR fallback candidate.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import torch
from torch import nn

from recurrent_option_value import ResidualMLP


MODEL_VERSION = 1
ARCHITECTURE = "schedule_conditioned_repair_value_v1"


@dataclass(frozen=True)
class RepairValueConfig:
    state_dim: int
    schedule_dim: int
    deviation_dim: int
    candidate_dim: int
    hidden_dim: int = 160
    recurrent_layers: int = 1
    ensemble_heads: int = 5
    dropout: float = 0.0
    planned_index: int = 0
    uncertainty_scale: float = 1.0
    minimum_advantage: float = 0.0

    def validate(self) -> None:
        dimensions = (
            self.state_dim,
            self.schedule_dim,
            self.deviation_dim,
            self.candidate_dim,
            self.hidden_dim,
            self.recurrent_layers,
        )
        if any(value <= 0 for value in dimensions):
            raise ValueError("all feature and hidden dimensions must be positive")
        if self.ensemble_heads < 2:
            raise ValueError("at least two ensemble heads are required")
        if self.planned_index < 0:
            raise ValueError("planned_index must be non-negative")
        if self.uncertainty_scale < 0:
            raise ValueError("uncertainty_scale must be non-negative")


class RepairValueNet(nn.Module):
    """Rank legal local repair candidates by terminal-margin advantage."""

    def __init__(self, config: RepairValueConfig) -> None:
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
            h,
            h,
            num_layers=config.recurrent_layers,
            dropout=config.dropout if config.recurrent_layers > 1 else 0.0,
            batch_first=True,
        )
        self.schedule_stem = nn.Sequential(
            nn.LayerNorm(config.schedule_dim), nn.Linear(config.schedule_dim, h), nn.SiLU()
        )
        self.deviation_stem = nn.Sequential(
            nn.LayerNorm(config.deviation_dim), nn.Linear(config.deviation_dim, h), nn.SiLU()
        )
        self.candidate_stem = nn.Sequential(
            nn.LayerNorm(config.candidate_dim),
            nn.Linear(config.candidate_dim, h),
            nn.SiLU(),
            ResidualMLP(h, config.dropout),
        )
        self.context = nn.Sequential(
            nn.LayerNorm(3 * h), nn.Linear(3 * h, h), nn.SiLU(), ResidualMLP(h, config.dropout)
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

    def encode_history(self, history: torch.Tensor, lengths: torch.Tensor) -> torch.Tensor:
        if history.ndim != 3 or history.shape[-1] != self.config.state_dim:
            raise ValueError("history has unexpected shape")
        if lengths.shape != (history.shape[0],):
            raise ValueError("lengths must have shape (batch,)")
        if torch.any(lengths <= 0) or torch.any(lengths > history.shape[1]):
            raise ValueError("lengths must be in [1, time]")
        encoded = self.state_stem(history)
        packed = nn.utils.rnn.pack_padded_sequence(
            encoded, lengths.detach().cpu(), batch_first=True, enforce_sorted=False
        )
        _, hidden = self.gru(packed)
        return hidden[-1]

    def forward(
        self,
        history: torch.Tensor,
        lengths: torch.Tensor,
        schedule_features: torch.Tensor,
        deviation_features: torch.Tensor,
        candidate_features: torch.Tensor,
    ) -> torch.Tensor:
        batch = history.shape[0]
        if schedule_features.shape != (batch, self.config.schedule_dim):
            raise ValueError("schedule_features has unexpected shape")
        if deviation_features.shape != (batch, self.config.deviation_dim):
            raise ValueError("deviation_features has unexpected shape")
        if candidate_features.ndim != 3:
            raise ValueError("candidate_features must have shape (batch, candidates, dim)")
        if candidate_features.shape[0] != batch or candidate_features.shape[-1] != self.config.candidate_dim:
            raise ValueError("candidate_features has unexpected shape")
        if self.config.planned_index >= candidate_features.shape[1]:
            raise ValueError("planned_index is outside the candidate axis")

        belief = self.encode_history(history, lengths)
        context = self.context(
            torch.cat(
                (
                    belief,
                    self.schedule_stem(schedule_features),
                    self.deviation_stem(deviation_features),
                ),
                dim=-1,
            )
        )
        candidate = self.candidate_stem(candidate_features)
        expanded = context.unsqueeze(1).expand_as(candidate)
        joint = torch.cat(
            (expanded, candidate, expanded * candidate, torch.abs(expanded - candidate)),
            dim=-1,
        )
        return torch.stack([head(joint).squeeze(-1) for head in self.heads], dim=0)

    @staticmethod
    def relative_to_fallback(
        raw_values: torch.Tensor, fallback_indices: torch.Tensor
    ) -> torch.Tensor:
        if raw_values.ndim != 3:
            raise ValueError("raw_values must have shape (heads, batch, candidates)")
        heads, batch, candidates = raw_values.shape
        if fallback_indices.shape != (batch,):
            raise ValueError("fallback_indices must have shape (batch,)")
        if torch.any(fallback_indices < 0) or torch.any(fallback_indices >= candidates):
            raise ValueError("fallback index is outside candidate axis")
        gather_index = fallback_indices.view(1, batch, 1).expand(heads, -1, -1)
        fallback = raw_values.gather(2, gather_index)
        return raw_values - fallback

    @torch.no_grad()
    def select(
        self,
        history: torch.Tensor,
        lengths: torch.Tensor,
        schedule_features: torch.Tensor,
        deviation_features: torch.Tensor,
        candidate_features: torch.Tensor,
        *,
        valid_mask: torch.Tensor,
        fallback_indices: torch.Tensor,
        repair_required: torch.Tensor,
    ) -> dict[str, torch.Tensor]:
        raw = self(
            history,
            lengths,
            schedule_features,
            deviation_features,
            candidate_features,
        )
        relative = self.relative_to_fallback(raw, fallback_indices)
        mean = relative.mean(dim=0)
        std = relative.std(dim=0, unbiased=False)
        lower = mean - self.config.uncertainty_scale * std
        if valid_mask.shape != mean.shape:
            raise ValueError("valid_mask must match (batch, candidates)")
        if repair_required.shape != (mean.shape[0],):
            raise ValueError("repair_required must have shape (batch,)")
        fallback_valid = valid_mask.gather(1, fallback_indices.unsqueeze(1)).squeeze(1)
        if not torch.all(fallback_valid):
            raise ValueError("every fallback candidate must be valid")
        lower = lower.masked_fill(~valid_mask, -torch.inf)
        lower.scatter_(1, fallback_indices.unsqueeze(1), 0.0)
        selected = lower.argmax(dim=-1)
        chosen = lower.gather(1, selected.unsqueeze(1)).squeeze(1)
        selected = torch.where(
            chosen <= self.config.minimum_advantage, fallback_indices, selected
        )
        planned = torch.full_like(selected, self.config.planned_index)
        planned_valid = valid_mask[:, self.config.planned_index]
        no_repair_choice = torch.where(planned_valid, planned, fallback_indices)
        selected = torch.where(repair_required, selected, no_repair_choice)
        return {
            "action": selected,
            "mean_advantage_vs_fallback": mean,
            "uncertainty": std,
            "lower_confidence_advantage": lower,
        }

    def metadata(self) -> dict[str, Any]:
        return {
            "model_version": MODEL_VERSION,
            "architecture": ARCHITECTURE,
            "config": asdict(self.config),
        }


def save_repair_checkpoint(
    path: Path,
    model: RepairValueNet,
    *,
    state_feature_names: list[str],
    schedule_feature_names: list[str],
    deviation_feature_names: list[str],
    candidate_feature_names: list[str],
    registry_fingerprint: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            **model.metadata(),
            "state_feature_names": state_feature_names,
            "schedule_feature_names": schedule_feature_names,
            "deviation_feature_names": deviation_feature_names,
            "candidate_feature_names": candidate_feature_names,
            "registry_fingerprint": registry_fingerprint,
            "model_state": {
                key: value.detach().cpu() for key, value in model.state_dict().items()
            },
            "metadata": metadata or {},
        },
        path,
    )
