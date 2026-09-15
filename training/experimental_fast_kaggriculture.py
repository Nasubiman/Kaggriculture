#!/usr/bin/env python3
"""Aggressively optimized experimental Kaggriculture runner.

This module is intentionally separate from ``fast_kaggriculture.py``.  It
specializes the normal two-player/default-competition hot path and falls back
to the stable fast runner whenever an assumption does not hold.

The goal is training/search throughput.  Promotion to the stable runner must
remain gated by full-trajectory parity tests.
"""
from __future__ import annotations

from collections.abc import Callable
from types import FunctionType
from typing import Any

import fast_kaggriculture as stable
from kaggle_environments.envs.kaggriculture import kaggriculture


_PASS = ["PASS"]
_ACTIVE = "ACTIVE"
_DEFAULT_BOARD_SIZE = 10
_DEFAULT_TURNS_PER_DAY = 24
_DEFAULT_SHED_CAPACITY = 100
_DEFAULT_SHOP_SELL_INTERVAL = 4
_DEFAULT_CENTER_SELL_INTERVAL = 24

# The earliest finite plant can decay under the default competition rules:
# CARROT planted on day 0 -> (0 + max_yield_day 3 + 1) * 24 == 96.
_EARLIEST_DEFAULT_DECAY_STEP = 96

_PRODUCTS = tuple(kaggriculture.PRODUCTS)
if len(_PRODUCTS) != 9:
    raise RuntimeError("experimental simulator expects the 9-product rule set")

# Sidecars live outside observations, so agents see the exact official schema.
# They are keyed by object identity and removed at episode completion.
_MARKET_SIGNATURES: dict[int, tuple[int, ...]] = {}
_DECAY_COORDS: dict[int, tuple[int, list[tuple[int, int]]]] = {}
_SIDECAR_LIMIT = 16_384


def _prune_sidecars() -> None:
    # Defensive bound for unusual long-lived processes that abandon episodes.
    if len(_MARKET_SIGNATURES) > _SIDECAR_LIMIT:
        _MARKET_SIGNATURES.clear()
    if len(_DECAY_COORDS) > _SIDECAR_LIMIT:
        _DECAY_COORDS.clear()


def _market_signature(market: Any) -> tuple[int, ...]:
    inv = market["inventory"]
    return (
        inv["WHEAT"],
        inv["CARROT"],
        inv["TOMATO"],
        inv["STRAWBERRY"],
        inv["MELON"],
        inv["EGG"],
        inv["MILK"],
        inv["WOOL"],
        inv["FERTILIZER"],
    )


def _register_market(market: Any) -> None:
    _prune_sidecars()
    _MARKET_SIGNATURES[id(market)] = _market_signature(market)


def _fast_refresh_prices(market: Any) -> None:
    """Refresh only products whose inventory changed.

    Custom market parameters are deliberately delegated to the official helper.
    The optimized path is for the exact default competition rules.
    """
    if market.get("params") is not None:
        kaggriculture._refresh_prices(market)
        return

    inv = market["inventory"]
    current = (
        inv["WHEAT"],
        inv["CARROT"],
        inv["TOMATO"],
        inv["STRAWBERRY"],
        inv["MELON"],
        inv["EGG"],
        inv["MILK"],
        inv["WOOL"],
        inv["FERTILIZER"],
    )
    key = id(market)
    previous = _MARKET_SIGNATURES.get(key)
    prices = market["prices"]

    if previous is None:
        # A branch/clone may enter here without registration.
        for item, value in zip(_PRODUCTS, current):
            prices[item] = stable._fast_market_price(item, value)
        _MARKET_SIGNATURES[key] = current
        return

    if current == previous:
        return

    # Unrolled comparisons avoid a loop and repeated tuple/dict indirections in
    # one of the hottest rule helpers.
    if current[0] != previous[0]:
        prices["WHEAT"] = stable._fast_market_price("WHEAT", current[0])
    if current[1] != previous[1]:
        prices["CARROT"] = stable._fast_market_price("CARROT", current[1])
    if current[2] != previous[2]:
        prices["TOMATO"] = stable._fast_market_price("TOMATO", current[2])
    if current[3] != previous[3]:
        prices["STRAWBERRY"] = stable._fast_market_price("STRAWBERRY", current[3])
    if current[4] != previous[4]:
        prices["MELON"] = stable._fast_market_price("MELON", current[4])
    if current[5] != previous[5]:
        prices["EGG"] = stable._fast_market_price("EGG", current[5])
    if current[6] != previous[6]:
        prices["MILK"] = stable._fast_market_price("MILK", current[6])
    if current[7] != previous[7]:
        prices["WOOL"] = stable._fast_market_price("WOOL", current[7])
    if current[8] != previous[8]:
        prices["FERTILIZER"] = stable._fast_market_price("FERTILIZER", current[8])

    _MARKET_SIGNATURES[key] = current


def _fast_is_shed_adjacent(pos: Any, board_size: int) -> bool:
    """Arithmetic version of the four central shed-access coordinates."""
    x, y = pos[0], pos[1]
    half = board_size >> 1
    return (x == half or x == half - 1) and (y == half or y == half - 1)


def _rebuild_decay_coords(farm: Any, step: int) -> list[tuple[int, int]]:
    coords: list[tuple[int, int]] = []
    tiles = farm["tiles"]
    for y, row in enumerate(tiles):
        for x, tile in enumerate(row):
            if (
                isinstance(tile, dict)
                and tile.get("kind") == "PLANT"
                and tile.get("max_lifespan_step", -1) >= 0
            ):
                coords.append((y, x))
    _DECAY_COORDS[id(farm)] = (step // _DEFAULT_TURNS_PER_DAY, coords)
    return coords


def _fast_decay_plants_default(farm: Any, step: int) -> None:
    """Default-rule decay with no full-board scan on most turns."""
    if step < _EARLIEST_DEFAULT_DECAY_STEP or (step & 1):
        return

    key = id(farm)
    day = step // _DEFAULT_TURNS_PER_DAY
    cached = _DECAY_COORDS.get(key)
    if cached is None or cached[0] != day:
        coords = _rebuild_decay_coords(farm, step)
    else:
        coords = cached[1]

    tiles = farm["tiles"]
    # Keep the sidecar conservative: stale coordinates are harmless and are
    # rebuilt daily. Newly planted finite crops cannot expire on their planting
    # day, so daily rebuilds are sufficient for decay correctness.
    for y, x in coords:
        tile = tiles[y][x]
        if not isinstance(tile, dict) or tile.get("kind") != "PLANT":
            continue
        lifespan = tile["max_lifespan_step"]
        if lifespan < 0 or step < lifespan or ((step - lifespan) & 1):
            continue
        tile["yield_units"] -= 1
        if tile["yield_units"] <= 0:
            tiles[y][x] = {"kind": "WEED"}


def _clone_official(function: Callable[..., Any], globals_: dict[str, Any]) -> Any:
    """Clone an official helper with isolated optimized globals."""
    clone = FunctionType(
        function.__code__,
        globals_,
        function.__name__,
        function.__defaults__,
        function.__closure__,
    )
    clone.__kwdefaults__ = function.__kwdefaults__
    return clone


# Clone only the official helpers whose global lookups matter in our hot path.
_HELPER_GLOBALS = dict(vars(kaggriculture))
_HELPER_GLOBALS["market_price"] = stable._fast_market_price
_HELPER_GLOBALS["_refresh_prices"] = _fast_refresh_prices
_HELPER_GLOBALS["_is_shed_adjacent"] = _fast_is_shed_adjacent
_HELPER_GLOBALS["_decay_plants"] = _fast_decay_plants_default

_FAST_APPLY_UNIT_ACTION = _clone_official(
    kaggriculture._apply_unit_action, _HELPER_GLOBALS
)
_HELPER_GLOBALS["_apply_unit_action"] = _FAST_APPLY_UNIT_ACTION
_FAST_MARKET_PROCESSOR = _clone_official(
    kaggriculture._process_market, _HELPER_GLOBALS
)


def _market_actions(action: Any) -> list[Any] | None:
    if not isinstance(action, dict):
        return None
    market = action.get("market")
    if isinstance(market, list) and market:
        return market
    return None


def _fast_process_market(state: list[Any], env: Any) -> None:
    """Skip the allocation-heavy official market path on no-order turns."""
    a0 = state[0].action
    a1 = state[1].action
    if _market_actions(a0) is None and _market_actions(a1) is None:
        return
    _FAST_MARKET_PROCESSOR(state, env)


def _fast_town_consume_default(env: Any, state: list[Any], step: int) -> None:
    """Default town demand, with an immediate no-op return on 18/24 turns."""
    shop_tick = step % _DEFAULT_SHOP_SELL_INTERVAL == 0
    center_tick = step % _DEFAULT_CENTER_SELL_INTERVAL == 0
    if not shop_tick and not center_tick:
        return

    obs0 = state[0].observation
    market = obs0.market
    inventory = market["inventory"]

    if shop_tick:
        for shop_name in obs0.town.get("unlocked_shops", []):
            products = kaggriculture.SHOPS[shop_name]
            multiplier = 2 if len(products) == 1 else 1
            for item in products:
                inventory[item] -= multiplier

    if center_tick:
        # Fixed tuple/list under the pinned rule set.
        for item in kaggriculture.TOWN_CENTER_PRODUCTS:
            inventory[item] -= 1

    _fast_refresh_prices(market)


def _cfg_value(cfg: Any, name: str, default: Any) -> Any:
    if isinstance(cfg, dict):
        return cfg.get(name, default)
    return getattr(cfg, name, default)


def _is_default_hot_config(env: Any) -> bool:
    cfg = env.configuration
    return (
        int(_cfg_value(cfg, "boardSize", 10)) == _DEFAULT_BOARD_SIZE
        and max(1, int(_cfg_value(cfg, "turnsPerDay", 24)))
        == _DEFAULT_TURNS_PER_DAY
        and int(_cfg_value(cfg, "shedCapacity", 100)) == _DEFAULT_SHED_CAPACITY
        and max(1, int(_cfg_value(cfg, "townShopSellInterval", 4)))
        == _DEFAULT_SHOP_SELL_INTERVAL
        and max(1, int(_cfg_value(cfg, "townCenterSellInterval", 24)))
        == _DEFAULT_CENTER_SELL_INTERVAL
        and _cfg_value(cfg, "marketParams", None) in (None, {})
    )


def _blocked_plants(
    farmer_action: Any, hands_actions: list[Any], seeds: Any
) -> set[str] | None:
    """Return atomically blocked crops, or None for the common no-PLANT case."""
    demand: dict[str, int] | None = None

    if (
        isinstance(farmer_action, list)
        and len(farmer_action) >= 2
        and farmer_action[0] == "PLANT"
    ):
        crop = farmer_action[1]
        demand = {crop: 1}

    for action in hands_actions:
        if isinstance(action, list) and len(action) >= 2 and action[0] == "PLANT":
            crop = action[1]
            if demand is None:
                demand = {crop: 1}
            else:
                demand[crop] = demand.get(crop, 0) + 1

    if demand is None:
        return None

    blocked = {crop for crop, count in demand.items() if count > seeds.get(crop, 0)}
    return blocked


def _allowed_action(action: Any, blocked: set[str] | None) -> Any:
    if (
        blocked
        and isinstance(action, list)
        and len(action) >= 2
        and action[0] == "PLANT"
        and action[1] in blocked
    ):
        return _PASS
    return action


def _apply_player_actions(
    farm: Any,
    private: Any,
    action: Any,
    *,
    day: int,
) -> None:
    """Two-player/default-config specialization of official unit dispatch."""
    if not isinstance(action, dict):
        farmer_action = _PASS
        hands_actions: list[Any] = []
    else:
        farmer_action = action.get("farmer", _PASS)
        hands_actions = action.get("hands", [])
        if not isinstance(hands_actions, list):
            hands_actions = []

    seeds = private.get("seeds", {}) if hasattr(private, "get") else {}
    blocked = _blocked_plants(farmer_action, hands_actions, seeds)

    _FAST_APPLY_UNIT_ACTION(
        farm,
        private,
        0,
        _allowed_action(farmer_action, blocked),
        _DEFAULT_BOARD_SIZE,
        day,
        _DEFAULT_TURNS_PER_DAY,
        _DEFAULT_SHED_CAPACITY,
    )
    for index, hand_action in enumerate(hands_actions, 1):
        _FAST_APPLY_UNIT_ACTION(
            farm,
            private,
            index,
            _allowed_action(hand_action, blocked),
            _DEFAULT_BOARD_SIZE,
            day,
            _DEFAULT_TURNS_PER_DAY,
            _DEFAULT_SHED_CAPACITY,
        )


def _experimental_interpreter_default(state: list[Any], env: Any) -> list[Any]:
    """Specialized official interpreter for two players and default rules."""
    # run_fast_steps establishes initialized state and shared observation aliases.
    if env.done:
        return state

    s0 = state[0]
    s1 = state[1]
    obs0 = s0.observation
    step = obs0.get("step", 0)
    day = step // _DEFAULT_TURNS_PER_DAY
    farms = obs0.farms

    _apply_player_actions(
        farms[0], s0.observation.private, s0.action, day=day
    )
    _apply_player_actions(
        farms[1], s1.observation.private, s1.action, day=day
    )

    _fast_process_market(state, env)
    _fast_town_consume_default(env, state, step)
    _fast_decay_plants_default(farms[0], step)
    _fast_decay_plants_default(farms[1], step)

    if (step + 1) % _DEFAULT_TURNS_PER_DAY == 0:
        kaggriculture._end_of_day(state, env, day)

    next_step = step + 1
    next_day = next_step // _DEFAULT_TURNS_PER_DAY
    next_hour = next_step % _DEFAULT_TURNS_PER_DAY
    obs0.day = next_day
    obs0.hour = next_hour
    # farms/market/town are intentionally not reassigned every turn.  Both
    # observations already share these live objects; only scalar day/hour need
    # synchronization.
    obs1 = s1.observation
    obs1.day = next_day
    obs1.hour = next_hour

    if step >= env.configuration.episodeSteps - 2:
        s0.status = "DONE"
        s1.status = "DONE"
        s0.reward = float(farms[s0.observation.player]["money"])
        s1.reward = float(farms[s1.observation.player]["money"])

    return state


# Public aliases matching the stable runner API.
create_fast_episode = stable.create_fast_episode
clone_fast_state = stable.clone_fast_state


def _prepare_two_player_state(state: list[Any]) -> None:
    obs0 = state[0].observation
    obs1 = state[1].observation
    # Preserve the official shared-public-observation contract once, not once
    # per interpreter turn.
    obs1.farms = obs0.farms
    obs1.market = obs0.market
    obs1.town = obs0.town
    obs1.day = obs0.day
    obs1.hour = obs0.hour
    _register_market(obs0.market)
    _prune_sidecars()


def _cleanup_sidecars(state: list[Any]) -> None:
    if not state:
        return
    obs0 = state[0].observation
    market = getattr(obs0, "market", None)
    if market is not None:
        _MARKET_SIGNATURES.pop(id(market), None)
    farms = getattr(obs0, "farms", None)
    if farms:
        for farm in farms:
            _DECAY_COORDS.pop(id(farm), None)


def run_experimental_fast_episode(
    agents: list[Callable[[Any], dict[str, Any]]],
    *,
    seed: int,
    episode_steps: int = 720,
    cache_market_prices: bool = True,
) -> list[Any]:
    env, state = create_fast_episode(
        seed=seed,
        episode_steps=episode_steps,
        num_agents=len(agents),
    )
    try:
        return run_experimental_fast_steps(
            agents,
            env=env,
            state=state,
            stop_step=episode_steps - 1,
            cache_market_prices=cache_market_prices,
        )
    finally:
        _cleanup_sidecars(state)


def _run_two_player_steps(
    agent0: Callable[[Any], dict[str, Any]],
    agent1: Callable[[Any], dict[str, Any]],
    *,
    env: Any,
    state: list[Any],
    stop_step: int,
) -> list[Any]:
    s0 = state[0]
    s1 = state[1]
    if s0.status != _ACTIVE and s1.status != _ACTIVE:
        return state

    step = int(s0.observation.get("step", 0))
    env.state = state

    # Initial states do not necessarily carry ``step``.  Set it once before the
    # first agent call; subsequent iterations inherit the value written below.
    s0.observation.step = step
    s1.observation.step = step

    interpreter = _experimental_interpreter_default
    while step < stop_step:
        s0.action = agent0(s0.observation)
        s1.action = agent1(s1.observation)

        state = interpreter(state, env)
        step += 1
        s0 = state[0]
        s1 = state[1]
        s0.observation.step = step
        s1.observation.step = step

        # The interpreter's env.done check and the next call must see the live
        # returned state.  Unlike the stable loop, there is no redundant write
        # at the top of every iteration.
        env.state = state

        if s0.status != _ACTIVE and s1.status != _ACTIVE:
            break

    return state


def run_experimental_fast_steps(
    agents: list[Callable[[Any], dict[str, Any]]],
    *,
    env: Any,
    state: list[Any],
    stop_step: int,
    cache_market_prices: bool = True,
) -> list[Any]:
    # Every aggressive optimization is guarded.  Nonstandard configurations,
    # branch shapes, or uncached-market tests retain stable semantics.
    if (
        len(agents) != 2
        or len(state) != 2
        or not cache_market_prices
        or not getattr(state[0].observation, "farms", None)
        or not _is_default_hot_config(env)
    ):
        return stable.run_fast_steps(
            agents,
            env=env,
            state=state,
            stop_step=stop_step,
            cache_market_prices=cache_market_prices,
        )

    _prepare_two_player_state(state)
    return _run_two_player_steps(
        agents[0],
        agents[1],
        env=env,
        state=state,
        stop_step=stop_step,
    )


# Drop-in names used by current training/benchmark helpers.
run_fast_episode = run_experimental_fast_episode
run_fast_steps = run_experimental_fast_steps
