#!/usr/bin/env python3
"""Structured transformer policy for Kaggriculture macro reinforcement learning.

The existing hybrid PPO policy flattens the complete game state into 102 values.
This module preserves the same observation and semantic-action contracts, while
splitting the flat vector into domain tokens before attention:

- temporal/global state
- own farm
- opponent farm
- private economy and inventory
- market state
- town/shop state
- current macro strategy

The design is intentionally compatible with the current rollout collector:
``forward(observations) -> (action_logits, value)``.  It can therefore replace
``hybrid_policy.ActorCritic`` without changing trajectory records or PPO math.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Final

import torch
from torch import nn

from hybrid_policy import ACTION_COUNT, ACTION_NAMES, OBSERVATION_SIZE


STRUCTURED_POLICY_VERSION: Final[int] = 3


@dataclass(frozen=True)
class TokenSlice:
    """A named contiguous slice of the legacy 102-dimensional observation."""

    name: str
    start: int
    stop: int

    @property
    def width(self) -> int:
        return self.stop - self.start


# Keep this table next to the model.  encode_observation() is deliberately
# stable, and the assertions below fail loudly if that contract changes.
TOKEN_SLICES: Final[tuple[TokenSlice, ...]] = (
    TokenSlice("time", 0, 3),
    TokenSlice("own_farm", 3, 21),
    TokenSlice("opponent_farm", 21, 39),
    TokenSlice("relative_score", 39, 40),
    TokenSlice("shed", 40, 52),
    TokenSlice("seeds", 52, 57),
    TokenSlice("carried", 57, 69),
    TokenSlice("market_prices", 69, 78),
    TokenSlice("market_inventory", 78, 87),
    TokenSlice("shops", 87, 95),
    TokenSlice("macro", 95, 104),
)

# The current encoder is 102 wide.  Its final macro block starts at 93 rather
# than 95 because the farm feature block is 17 values, not 18.  Define the
# authoritative layout explicitly after documenting the semantic grouping.
TOKEN_SLICES = (
    TokenSlice("time", 0, 3),
    TokenSlice("own_farm", 3, 20),
    TokenSlice("opponent_farm", 20, 37),
    TokenSlice("relative_score", 37, 38),
    TokenSlice("shed", 38, 50),
    TokenSlice("seeds", 50, 55),
    TokenSlice("carried", 55, 67),
    TokenSlice("market_prices", 67, 76),
    TokenSlice("market_inventory", 76, 85),
    TokenSlice("shops", 85, 93),
    TokenSlice("macro", 93, 102),
)

assert TOKEN_SLICES[0].start == 0
assert TOKEN_SLICES[-1].stop == OBSERVATION_SIZE
assert all(a.stop == b.start for a, b in zip(TOKEN_SLICES, TOKEN_SLICES[1:]))


@dataclass(frozen=True)
class StructuredPolicyConfig:
    d_model: int = 128
    n_heads: int = 4
    n_layers: int = 3
    ff_multiplier: int = 4
    dropout: float = 0.0
    action_embedding_dim: int = 64
    keep_prior_logit: float = 3.0

    def validate(self) -> None:
        if self.d_model <= 0:
            raise ValueError("d_model must be positive")
        if self.d_model % self.n_heads:
            raise ValueError("d_model must be divisible by n_heads")
        if self.n_layers <= 0:
            raise ValueError("n_layers must be positive")
        if self.ff_multiplier <= 0:
            raise ValueError("ff_multiplier must be positive")


class TokenProjector(nn.Module):
    """Projects each heterogeneous domain block into one transformer token."""

    def __init__(self, config: StructuredPolicyConfig) -> None:
        super().__init__()
        self.slices = TOKEN_SLICES
        hidden = config.d_model * 2
        self.projectors = nn.ModuleList(
            nn.Sequential(
                nn.Linear(spec.width, hidden),
                nn.GELU(),
                nn.Linear(hidden, config.d_model),
            )
            for spec in self.slices
        )
        self.type_embedding = nn.Parameter(
            torch.empty(1, len(self.slices), config.d_model)
        )
        self.cls_token = nn.Parameter(torch.empty(1, 1, config.d_model))

    def reset_parameters(self) -> None:
        nn.init.normal_(self.type_embedding, std=0.02)
        nn.init.normal_(self.cls_token, std=0.02)

    def forward(self, observations: torch.Tensor) -> torch.Tensor:
        if observations.ndim != 2 or observations.shape[-1] != OBSERVATION_SIZE:
            raise ValueError(
                f"Expected (batch, {OBSERVATION_SIZE}), got {tuple(observations.shape)}"
            )
        tokens = [
            projector(observations[:, spec.start : spec.stop])
            for spec, projector in zip(self.slices, self.projectors)
        ]
        stacked = torch.stack(tokens, dim=1) + self.type_embedding
        cls = self.cls_token.expand(observations.shape[0], -1, -1)
        return torch.cat((cls, stacked), dim=1)


class StructuredActorCritic(nn.Module):
    """Domain-token transformer with semantic action queries.

    Instead of a plain ``Linear(d_model, ACTION_COUNT)`` head, every semantic
    action owns a learned query.  The score is a dot product between that query
    and the encoded state, plus an action-specific bias.  This makes related
    actions share the trunk while retaining explicit action identities and is a
    useful stepping stone toward an autoregressive action-factor policy.
    """

    def __init__(self, config: StructuredPolicyConfig | None = None) -> None:
        super().__init__()
        self.config = config or StructuredPolicyConfig()
        self.config.validate()

        self.tokenizer = TokenProjector(self.config)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=self.config.d_model,
            nhead=self.config.n_heads,
            dim_feedforward=self.config.d_model * self.config.ff_multiplier,
            dropout=self.config.dropout,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        self.encoder = nn.TransformerEncoder(
            encoder_layer,
            num_layers=self.config.n_layers,
            norm=nn.LayerNorm(self.config.d_model),
        )
        self.state_head = nn.Sequential(
            nn.LayerNorm(self.config.d_model * 2),
            nn.Linear(self.config.d_model * 2, self.config.d_model),
            nn.GELU(),
        )
        self.action_queries = nn.Embedding(ACTION_COUNT, self.config.d_model)
        self.action_bias = nn.Parameter(torch.zeros(ACTION_COUNT))
        self.value_head = nn.Sequential(
            nn.LayerNorm(self.config.d_model),
            nn.Linear(self.config.d_model, self.config.d_model),
            nn.GELU(),
            nn.Linear(self.config.d_model, 1),
        )
        self.reset_parameters()

    def reset_parameters(self) -> None:
        self.tokenizer.reset_parameters()
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.orthogonal_(module.weight, gain=math.sqrt(2.0))
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
        nn.init.normal_(self.action_queries.weight, std=0.02)
        nn.init.zeros_(self.action_bias)
        with torch.no_grad():
            self.action_bias[0] = self.config.keep_prior_logit
            # Small policy outputs and a unit-gain critic are standard PPO
            # initialisation choices and reduce destructive first updates.
            self.action_queries.weight.mul_(0.1)
            final_value = self.value_head[-1]
            assert isinstance(final_value, nn.Linear)
            nn.init.orthogonal_(final_value.weight, gain=1.0)

    def encode(self, observations: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        tokens = self.encoder(self.tokenizer(observations))
        cls = tokens[:, 0]
        pooled = tokens[:, 1:].mean(dim=1)
        state = self.state_head(torch.cat((cls, pooled), dim=-1))
        return state, cls

    def forward(self, observations: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        state, cls = self.encode(observations)
        logits = torch.einsum("bd,ad->ba", state, self.action_queries.weight)
        logits = logits / math.sqrt(self.config.d_model) + self.action_bias
        value = self.value_head(cls).squeeze(-1)
        return logits, value

    def checkpoint_metadata(self) -> dict[str, object]:
        return {
            "policy_version": STRUCTURED_POLICY_VERSION,
            "architecture": "structured_transformer_v1",
            "observation_size": OBSERVATION_SIZE,
            "action_names": ACTION_NAMES,
            "config": asdict(self.config),
            "token_slices": [asdict(spec) for spec in TOKEN_SLICES],
        }


def build_structured_policy(
    *,
    d_model: int = 128,
    n_heads: int = 4,
    n_layers: int = 3,
) -> StructuredActorCritic:
    """Small default suitable for initial single-GPU PPO experiments."""

    return StructuredActorCritic(
        StructuredPolicyConfig(
            d_model=d_model,
            n_heads=n_heads,
            n_layers=n_layers,
        )
    )
