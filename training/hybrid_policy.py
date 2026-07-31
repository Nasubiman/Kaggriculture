#!/usr/bin/env python3
"""Shared model and semantic-action wrapper for hybrid Kaggriculture RL.

The neural policy acts once per in-game day.  It changes a small set of
strategic parameters while the existing deterministic agent continues to
handle movement, feeding, harvesting, and legal low-level commands.
"""

from __future__ import annotations

import importlib.util
import math
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import torch
from torch import nn


PRODUCTS = (
    "WHEAT",
    "CARROT",
    "TOMATO",
    "STRAWBERRY",
    "MELON",
    "EGG",
    "MILK",
    "WOOL",
    "FERTILIZER",
)
CROPS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON")
ANIMALS = ("GOOSE", "COW", "SHEEP")
SHOPS = (
    "BAKERY",
    "PIZZA_SHOP",
    "BRUNCH_SPOT",
    "YARN_STORE",
    "ICE_CREAM_SHOP",
    "PET_CAFE",
    "SMOOTHIE_SHOP",
    "FARMERS_MARKET",
)
BASE_PRICES = {
    "WHEAT": 25,
    "CARROT": 35,
    "TOMATO": 60,
    "STRAWBERRY": 120,
    "MELON": 250,
    "EGG": 50,
    "MILK": 160,
    "WOOL": 200,
    "FERTILIZER": 100,
}

ACTION_NAMES = (
    "KEEP",
    "COMMIT_COWS",
    "DELAY_COWS",
    "EARLIER_COWS",
    "MORE_COWS",
    "FEWER_COWS",
    "MORE_SHEEP",
    "FEWER_SHEEP",
    "MORE_HANDS",
    "FEWER_HANDS",
    "MORE_WHEAT",
    "FEWER_WHEAT",
    "BUY_FASTER",
    "BUY_SLOWER",
    "SPEND_MORE",
    "SPEND_LESS",
    "PICKUP_MORE",
    "PICKUP_LESS",
)
ACTION_COUNT = len(ACTION_NAMES)
OBSERVATION_SIZE = 102
POLICY_VERSION = 1


@dataclass
class MacroState:
    cow_start_day: int = 8
    cow_target: int = 16
    cow_purchase_batch: int = 4
    cow_hands: int = 11
    wheat_tiles: int = 3
    wheat_pickup_batch: int = 12
    sale_proceeds_factor: float = 0.5
    sheep_target: int = 4
    transitioned: bool = False

    @classmethod
    def from_agent_module(cls, module: Any) -> "MacroState":
        return cls(
            cow_start_day=int(module.COW_START_DAY),
            cow_target=int(module.COW_TARGET),
            cow_purchase_batch=int(module.COW_PURCHASE_BATCH),
            cow_hands=int(module.COW_HANDS),
            wheat_tiles=int(module.WHEAT_TILES),
            wheat_pickup_batch=int(module.WHEAT_PICKUP_BATCH),
            sale_proceeds_factor=float(module.SALE_PROCEEDS_FACTOR),
            sheep_target=int(module.SHEEP_TARGET),
        )

    def refresh_phase(self, day: int) -> None:
        if day >= self.cow_start_day:
            self.transitioned = True

    def action_mask(self, day: int) -> np.ndarray:
        self.refresh_phase(day)
        mask = np.ones(ACTION_COUNT, dtype=np.bool_)
        mask[1] = not self.transitioned and day >= 4
        mask[2] = not self.transitioned and self.cow_start_day < 14
        mask[3] = not self.transitioned and self.cow_start_day > day
        mask[4] = self.transitioned and self.cow_target < 28
        mask[5] = self.transitioned and self.cow_target > 12
        mask[6] = self.sheep_target < 6
        mask[7] = self.sheep_target > 0
        mask[8] = self.cow_hands < 16
        mask[9] = self.cow_hands > 7
        mask[10] = self.wheat_tiles < 8
        mask[11] = self.wheat_tiles > 0
        mask[12] = self.cow_purchase_batch < 20
        mask[13] = self.cow_purchase_batch > 2
        mask[14] = self.sale_proceeds_factor < 0.95
        mask[15] = self.sale_proceeds_factor > 0.4
        mask[16] = self.wheat_pickup_batch < 20
        mask[17] = self.wheat_pickup_batch > 2
        return mask

    def apply_action(self, action: int, day: int) -> None:
        if action == 1:
            self.cow_start_day = day
            self.transitioned = True
        elif action == 2:
            self.cow_start_day = min(14, max(day + 1, self.cow_start_day + 1))
        elif action == 3:
            self.cow_start_day = max(day, self.cow_start_day - 1)
        elif action == 4:
            self.cow_target = min(28, self.cow_target + 2)
        elif action == 5:
            self.cow_target = max(12, self.cow_target - 2)
        elif action == 6:
            self.sheep_target = min(6, self.sheep_target + 1)
        elif action == 7:
            self.sheep_target = max(0, self.sheep_target - 1)
        elif action == 8:
            self.cow_hands = min(16, self.cow_hands + 1)
        elif action == 9:
            self.cow_hands = max(7, self.cow_hands - 1)
        elif action == 10:
            self.wheat_tiles = min(8, self.wheat_tiles + 1)
        elif action == 11:
            self.wheat_tiles = max(0, self.wheat_tiles - 1)
        elif action == 12:
            self.cow_purchase_batch = min(20, self.cow_purchase_batch + 2)
        elif action == 13:
            self.cow_purchase_batch = max(2, self.cow_purchase_batch - 2)
        elif action == 14:
            self.sale_proceeds_factor = min(
                0.95, round(self.sale_proceeds_factor + 0.05, 2)
            )
        elif action == 15:
            self.sale_proceeds_factor = max(
                0.4, round(self.sale_proceeds_factor - 0.05, 2)
            )
        elif action == 16:
            self.wheat_pickup_batch = min(20, self.wheat_pickup_batch + 2)
        elif action == 17:
            self.wheat_pickup_batch = max(2, self.wheat_pickup_batch - 2)
        self.refresh_phase(day)

    def apply_to_module(self, module: Any) -> None:
        module.COW_START_DAY = self.cow_start_day
        module.COW_TARGET = self.cow_target
        module.COW_PURCHASE_BATCH = self.cow_purchase_batch
        module.COW_HANDS = self.cow_hands
        module.WHEAT_TILES = self.wheat_tiles
        module.WHEAT_PICKUP_BATCH = self.wheat_pickup_batch
        module.SALE_PROCEEDS_FACTOR = self.sale_proceeds_factor
        module.SHEEP_TARGET = self.sheep_target


def _get(mapping: Any, key: str, default: Any) -> Any:
    if isinstance(mapping, dict):
        return mapping.get(key, default)
    return getattr(mapping, key, default)


def _farm_features(farm: Any) -> list[float]:
    farm = farm or {}
    counts = {
        "empty": 0,
        "weeds": 0,
        **{crop.lower(): 0 for crop in CROPS},
        **{animal.lower(): 0 for animal in ANIMALS},
        "empty_structures": 0,
        "yield": 0,
        "unfed": 0,
        "uncared": 0,
    }
    for row in _get(farm, "tiles", []) or []:
        for tile in row or []:
            if tile is None:
                counts["empty"] += 1
                continue
            if not isinstance(tile, dict):
                continue
            kind = str(tile.get("kind", ""))
            if kind == "WEED":
                counts["weeds"] += 1
            elif kind == "PLANT":
                crop = str(tile.get("crop", "")).lower()
                if crop in counts:
                    counts[crop] += 1
                counts["yield"] += int(tile.get("yield_units", 0))
            elif kind in ("COOP", "PASTURE"):
                animal = str(tile.get("animal", "")).lower()
                if animal in counts:
                    counts[animal] += 1
                    counts["unfed"] += int(not tile.get("fed_today", False))
                    counts["uncared"] += int(not tile.get("cared_today", False))
                else:
                    counts["empty_structures"] += 1
                counts["yield"] += int(tile.get("yield_units", 0))

    features = [
        min(1.5, math.log1p(max(0.0, float(_get(farm, "money", 0)))) / 11.5),
        min(1.0, len(_get(farm, "hands", []) or []) / 16.0),
        min(1.0, len(_get(farm, "unlocked_quadrants", []) or []) / 4.0),
        counts["empty"] / 100.0,
        counts["weeds"] / 25.0,
    ]
    features.extend(counts[crop.lower()] / 25.0 for crop in CROPS)
    features.extend(counts[animal.lower()] / 25.0 for animal in ANIMALS)
    features.extend(
        (
            counts["empty_structures"] / 25.0,
            counts["yield"] / 100.0,
            counts["unfed"] / 25.0,
            counts["uncared"] / 25.0,
        )
    )
    return features


def encode_observation(obs: Any, macro: MacroState) -> np.ndarray:
    player = int(_get(obs, "player", 0))
    day = int(_get(obs, "day", 0))
    farms = list(_get(obs, "farms", []) or [])
    own = farms[player] if player < len(farms) else {}
    opponent_index = 1 - player if len(farms) == 2 else 0
    opponent = farms[opponent_index] if opponent_index < len(farms) else {}
    private = _get(obs, "private", {}) or {}
    market = _get(obs, "market", {}) or {}
    town = _get(obs, "town", {}) or {}

    phase = 2.0 * math.pi * day / 30.0
    values = [day / 29.0, math.sin(phase), math.cos(phase)]
    values.extend(_farm_features(own))
    values.extend(_farm_features(opponent))
    money_difference = float(_get(own, "money", 0)) - float(
        _get(opponent, "money", 0)
    )
    values.append(math.tanh(money_difference / 25_000.0))

    shed = _get(private, "shed", {}) or {}
    seeds = _get(private, "seeds", {}) or {}
    inventories = _get(private, "inventories", []) or []
    item_order = PRODUCTS + ANIMALS
    values.extend(min(1.0, int(shed.get(item, 0)) / 100.0) for item in item_order)
    values.extend(min(1.0, int(seeds.get(crop, 0)) / 25.0) for crop in CROPS)
    carried = {
        item: sum(int((inventory or {}).get(item, 0)) for inventory in inventories)
        for item in item_order
    }
    values.extend(min(1.0, carried[item] / 100.0) for item in item_order)

    prices = _get(market, "prices", {}) or {}
    market_inventory = _get(market, "inventory", {}) or {}
    values.extend(
        min(4.0, max(0.0, float(prices.get(item, BASE_PRICES[item]))) / BASE_PRICES[item])
        / 4.0
        for item in PRODUCTS
    )
    values.extend(
        max(-1.0, min(1.0, (10_000 - int(market_inventory.get(item, 10_000))) / 500.0))
        for item in PRODUCTS
    )
    unlocked_shops = set(_get(town, "unlocked_shops", []) or [])
    values.extend(float(shop in unlocked_shops) for shop in SHOPS)
    values.extend(
        (
            macro.cow_start_day / 14.0,
            macro.cow_target / 28.0,
            macro.cow_purchase_batch / 20.0,
            macro.cow_hands / 16.0,
            macro.wheat_tiles / 8.0,
            macro.wheat_pickup_batch / 20.0,
            macro.sale_proceeds_factor,
            macro.sheep_target / 6.0,
            float(macro.transitioned),
        )
    )
    array = np.asarray(values, dtype=np.float32)
    if array.shape != (OBSERVATION_SIZE,):
        raise RuntimeError(
            f"Observation shape {array.shape}, expected {(OBSERVATION_SIZE,)}"
        )
    return array


class ActorCritic(nn.Module):
    def __init__(self, observation_size: int = OBSERVATION_SIZE) -> None:
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(observation_size, 128),
            nn.Tanh(),
            nn.Linear(128, 128),
            nn.Tanh(),
        )
        self.actor = nn.Linear(128, ACTION_COUNT)
        self.critic = nn.Linear(128, 1)
        self.apply(self._initialize)
        with torch.no_grad():
            # Analytic behavior-cloning prior: KEEP reproduces the strong
            # deterministic teacher exactly, while the remaining probability
            # still explores semantic deviations during PPO rollouts.
            self.actor.bias[0] = 4.5

    @staticmethod
    def _initialize(module: nn.Module) -> None:
        if isinstance(module, nn.Linear):
            nn.init.orthogonal_(module.weight, gain=math.sqrt(2.0))
            nn.init.zeros_(module.bias)

    def forward(self, observations: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        encoded = self.encoder(observations)
        return self.actor(encoded), self.critic(encoded).squeeze(-1)


def masked_logits(logits: torch.Tensor, masks: torch.Tensor) -> torch.Tensor:
    return logits.masked_fill(~masks, torch.finfo(logits.dtype).min)


def load_agent_module(path: Path, suffix: str) -> Any:
    spec = importlib.util.spec_from_file_location(
        f"hybrid_agent_{os.getpid()}_{suffix}", path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load agent module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_pasted_agent(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    marker = "%%writefile /kaggle/working/main.py"
    source = text.split(marker, 1)[1] if marker in text else text
    source = source.rsplit("Writing /kaggle/working/main.py", 1)[0]
    namespace: dict[str, Any] = {}
    exec(compile(source, str(path), "exec"), namespace)
    return SimpleNamespace(agent=namespace["agent"])


def save_checkpoint(
    path: Path,
    model: ActorCritic,
    update: int,
    metadata: dict[str, Any] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "policy_version": POLICY_VERSION,
            "observation_size": OBSERVATION_SIZE,
            "action_names": ACTION_NAMES,
            "update": update,
            "model_state": {
                key: value.detach().cpu() for key, value in model.state_dict().items()
            },
            "metadata": metadata or {},
        },
        path,
    )


def load_checkpoint(path: Path, device: str | torch.device = "cpu") -> tuple[ActorCritic, dict[str, Any]]:
    payload = torch.load(path, map_location=device, weights_only=False)
    if int(payload.get("policy_version", -1)) != POLICY_VERSION:
        raise RuntimeError(f"Unsupported policy checkpoint: {path}")
    model = ActorCritic(int(payload["observation_size"])).to(device)
    model.load_state_dict(payload["model_state"])
    model.eval()
    return model, payload


class HybridPolicyAgent:
    """A callable Kaggle agent that records one semantic action per day."""

    def __init__(
        self,
        base_agent_path: Path,
        model: ActorCritic,
        *,
        deterministic: bool,
        seed: int,
        record_trajectory: bool,
        suffix: str,
    ) -> None:
        self.module = load_agent_module(base_agent_path, suffix)
        self.model = model.to("cpu").eval()
        self.deterministic = deterministic
        self.rng = np.random.default_rng(seed)
        self.record_trajectory = record_trajectory
        self.macro = MacroState.from_agent_module(self.module)
        self.last_day = -1
        self.trajectory: list[dict[str, Any]] = []

    def __call__(self, obs: Any) -> dict[str, Any]:
        day = int(_get(obs, "day", 0))
        if day != self.last_day:
            self.macro.refresh_phase(day)
            observation = encode_observation(obs, self.macro)
            mask = self.macro.action_mask(day)
            tensor = torch.from_numpy(observation).unsqueeze(0)
            with torch.no_grad():
                logits, value = self.model(tensor)
                logits = masked_logits(logits, torch.from_numpy(mask).unsqueeze(0))
                probabilities = torch.softmax(logits, dim=-1)[0].cpu().numpy()
            action = (
                int(np.argmax(probabilities))
                if self.deterministic
                else int(self.rng.choice(ACTION_COUNT, p=probabilities))
            )
            log_probability = float(math.log(max(1e-12, probabilities[action])))
            farms = list(_get(obs, "farms", []) or [])
            player = int(_get(obs, "player", 0))
            opponent = 1 - player if len(farms) == 2 else 0
            money_advantage = (
                float(_get(farms[player], "money", 0))
                - float(_get(farms[opponent], "money", 0))
                if player < len(farms) and opponent < len(farms)
                else 0.0
            )
            if self.record_trajectory:
                self.trajectory.append(
                    {
                        "observation": observation,
                        "mask": mask,
                        "action": action,
                        "old_log_probability": log_probability,
                        "value": float(value.item()),
                        "day": day,
                        "money_advantage": money_advantage,
                        "macro_before": asdict(self.macro),
                    }
                )
            self.macro.apply_action(action, day)
            self.macro.apply_to_module(self.module)
            self.last_day = day
        return self.module.agent(obs)

    def finalized_trajectory(
        self,
        reward: float,
        opponent_reward: float,
        shaping_coefficient: float,
    ) -> list[dict[str, Any]]:
        if not self.trajectory:
            return []
        potentials = [
            math.tanh(float(step["money_advantage"]) / 25_000.0)
            for step in self.trajectory
        ]
        final_potential = math.tanh((reward - opponent_reward) / 25_000.0)
        rewards = []
        for index, potential in enumerate(potentials):
            next_potential = (
                potentials[index + 1]
                if index + 1 < len(potentials)
                else final_potential
            )
            rewards.append(shaping_coefficient * (next_potential - potential))
        outcome = 1.0 if reward > opponent_reward else -1.0 if reward < opponent_reward else 0.0
        rewards[-1] += outcome + 0.5 * final_potential
        finalized = []
        for step, step_reward in zip(self.trajectory, rewards):
            record = dict(step)
            record["reward"] = float(step_reward)
            finalized.append(record)
        return finalized


def sanitize_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)
