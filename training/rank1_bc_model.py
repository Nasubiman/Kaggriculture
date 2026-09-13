"""Observation encoder and hierarchical behavior-cloning model for rank-1 replays."""

from __future__ import annotations

import json
import math
from typing import Any

import numpy as np


CROPS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON")
ANIMALS = ("GOOSE", "COW", "SHEEP")
PRODUCTS = (*CROPS, "EGG", "MILK", "WOOL", "FERTILIZER")
SHOPS = (
    "BAKERY", "PIZZA_SHOP", "BRUNCH_SPOT", "YARN_STORE",
    "ICE_CREAM_SHOP", "PET_CAFE", "SMOOTHIE_SHOP", "FARMERS_MARKET",
)
TILE_CATEGORY_COUNT = 13
TILE_NUMERIC_COUNT = 10
MAX_ACTORS = 16
MAX_MARKET_ORDERS = 10


def canonical_command(command: Any) -> str:
    if not isinstance(command, list) or not command:
        command = ["PASS"]
    return json.dumps(command, separators=(",", ":"))


def tile_features(tile: Any, day: int, step: int) -> tuple[np.ndarray, np.ndarray]:
    category = np.zeros(TILE_CATEGORY_COUNT, dtype=np.float32)
    numeric = np.zeros(TILE_NUMERIC_COUNT, dtype=np.float32)
    if tile == "LOCKED":
        category[0] = 1
        return category, numeric
    if tile is None:
        category[1] = 1
        return category, numeric
    if not isinstance(tile, dict):
        return category, numeric
    kind = str(tile.get("kind", ""))
    if kind == "WEED":
        category[2] = 1
    elif kind == "PLANT":
        crop = str(tile.get("crop", ""))
        category[3 + CROPS.index(crop) if crop in CROPS else 3] = 1
        numeric[0] = min(float(tile.get("yield_units", 0)) / 20.0, 5.0)
        numeric[1] = bool(tile.get("watered_today", False))
        numeric[2] = max(0.0, float(tile.get("fertilized_until_day", -1)) - day) / 5.0
        numeric[3] = min(float(tile.get("consecutive_unwatered", 0)) / 2.0, 2.0)
        numeric[9] = min(max(0.0, day - float(tile.get("planted_day", day))) / 30.0, 1.0)
    elif kind == "PASTURE":
        animal = tile.get("animal")
        category[{None: 8, "COW": 9, "SHEEP": 10}.get(animal, 8)] = 1
        numeric[0] = min(float(tile.get("yield_units", 0)) / 20.0, 5.0)
        numeric[4] = bool(tile.get("fed_today", False))
        numeric[5] = bool(tile.get("cared_today", False))
        numeric[6] = min(float(tile.get("consecutive_unfed", 0)) / 2.0, 2.0)
        numeric[7] = bool(tile.get("fertilizer_available", False))
        numeric[8] = min(float(tile.get("pending_care_bonus", 0)) / 10.0, 5.0)
        numeric[9] = min(max(0.0, day - float(tile.get("placed_day", day))) / 30.0, 1.0)
    elif kind == "COOP":
        category[12 if tile.get("animal") == "GOOSE" else 11] = 1
        numeric[0] = min(float(tile.get("yield_units", 0)) / 20.0, 5.0)
        numeric[4] = bool(tile.get("fed_today", False))
        numeric[5] = bool(tile.get("cared_today", False))
        numeric[6] = min(float(tile.get("consecutive_unfed", 0)) / 2.0, 2.0)
        numeric[7] = bool(tile.get("fertilizer_available", False))
        numeric[8] = min(float(tile.get("pending_care_bonus", 0)) / 10.0, 5.0)
        numeric[9] = min(max(0.0, day - float(tile.get("placed_day", day))) / 30.0, 1.0)
    return category, numeric


def encode_observation(obs: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return shared state, actor features, and actor-valid mask."""
    day = int(obs.get("day", 0)); hour = int(obs.get("hour", 0)); step = int(obs.get("step", day*24+hour))
    seat = int(obs.get("player", 0)); farms = obs.get("farms", []) or []
    ordered_farms = [farms[seat], farms[1-seat]]
    state: list[float] = []
    tile_cache: list[list[list[tuple[np.ndarray, np.ndarray]]]] = []
    for farm in ordered_farms:
        cached_rows = []
        for row in farm.get("tiles", []) or []:
            cached_row = []
            for tile in row:
                cat, num = tile_features(tile, day, step)
                state.extend(cat); state.extend(num); cached_row.append((cat, num))
            cached_rows.append(cached_row)
        tile_cache.append(cached_rows)

    # Unit occupancy maps retain the spatial relation between both policies.
    for farm in ordered_farms:
        for units in ([farm.get("farmer", [4, 4])], farm.get("hands", []) or []):
            occupancy = np.zeros(100, dtype=np.float32)
            for position in units:
                if isinstance(position, list) and len(position) == 2:
                    x, y = map(int, position)
                    if 0 <= x < 10 and 0 <= y < 10: occupancy[y*10+x] += 1
            state.extend(occupancy)

    state.extend((day/29.0, hour/23.0, math.sin(2*math.pi*hour/24), math.cos(2*math.pi*hour/24),
                  step/719.0, float(seat == 0), float(seat == 1)))
    for farm in ordered_farms:
        unlocked = set(farm.get("unlocked_quadrants", []) or [])
        state.extend((min(float(farm.get("money", 0))/150000.0, 3.0),
                      len(farm.get("hands", []) or []) / 15.0,
                      float(farm.get("hires_today", 0)) / 15.0,
                      *(float(name in unlocked) for name in ("NW", "NE", "SW", "SE"))))
    private = obs.get("private", {}) or {}; shed = private.get("shed", {}) or {}; seeds = private.get("seeds", {}) or {}
    state.extend(min(float(shed.get(name, 0))/100.0, 2.0) for name in PRODUCTS)
    state.extend(min(float(seeds.get(name, 0))/100.0, 2.0) for name in CROPS)
    inventories = private.get("inventories", []) or []
    aggregate = {name: 0.0 for name in PRODUCTS}
    for inventory in inventories:
        for name in PRODUCTS: aggregate[name] += float((inventory or {}).get(name, 0))
    state.extend(min(aggregate[name]/100.0, 2.0) for name in PRODUCTS)
    market = obs.get("market", {}) or {}; prices = market.get("prices", {}) or {}; supply = market.get("inventory", {}) or {}
    state.extend(min(float(prices.get(name, 0))/500.0, 3.0) for name in PRODUCTS)
    state.extend(min(float(supply.get(name, 0))/500.0, 3.0) for name in PRODUCTS)
    unlocked_shops = obs.get("town", {}).get("unlocked_shops", []) or []
    state.extend(float(name in unlocked_shops) for name in SHOPS)

    own = ordered_farms[0]
    positions = [own.get("farmer", [4, 4]), *(own.get("hands", []) or [])]
    actors = np.zeros((MAX_ACTORS, 38), dtype=np.float32)
    mask = np.zeros(MAX_ACTORS, dtype=np.bool_)
    for index, position in enumerate(positions[:MAX_ACTORS]):
        x, y = map(int, position); mask[index] = True
        actor_inventory = inventories[index] if index < len(inventories) else {}
        vector = [index/15.0, float(index == 0), x/9.0, y/9.0]
        vector.extend(min(float((actor_inventory or {}).get(name, 0))/20.0, 3.0) for name in PRODUCTS)
        vector.extend((abs(x-4)/9.0 + abs(y-4)/9.0, (x+y)/18.0))
        if 0 <= y < len(tile_cache[0]) and 0 <= x < len(tile_cache[0][y]):
            cat, num = tile_cache[0][y][x]; vector.extend(cat); vector.extend(num)
        else:
            vector.extend([0.0] * (TILE_CATEGORY_COUNT + TILE_NUMERIC_COUNT))
        actors[index] = vector
    return np.asarray(state, dtype=np.float32), actors, mask


def build_model(state_size: int, actor_vocab: int, market_vocab: int):
    import torch
    from torch import nn

    class Rank1BC(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.state = nn.Sequential(
                nn.Linear(state_size, 512), nn.LayerNorm(512), nn.GELU(),
                nn.Linear(512, 256), nn.LayerNorm(256), nn.GELU(),
            )
            self.actor = nn.Sequential(nn.Linear(38, 64), nn.GELU())
            self.actor_head = nn.Sequential(nn.Linear(320, 256), nn.GELU(), nn.Linear(256, actor_vocab))
            self.market_head = nn.Sequential(nn.Linear(256, 512), nn.GELU(),
                                             nn.Linear(512, MAX_MARKET_ORDERS * market_vocab))
            self.market_vocab = market_vocab

        def forward(self, state, actors):
            shared = self.state(state)
            actor_embedding = self.actor(actors)
            expanded = shared[:, None, :].expand(-1, actors.shape[1], -1)
            actor_logits = self.actor_head(torch.cat((expanded, actor_embedding), dim=-1))
            market_logits = self.market_head(shared).reshape(-1, MAX_MARKET_ORDERS, self.market_vocab)
            return actor_logits, market_logits

    return Rank1BC()
