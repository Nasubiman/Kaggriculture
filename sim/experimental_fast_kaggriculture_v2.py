#!/usr/bin/env python3
"""Second-stage aggressive Kaggriculture simulator optimizations."""
from __future__ import annotations

import random
from typing import Any

import experimental_fast_kaggriculture as base
from kaggle_environments.envs.kaggriculture import kaggriculture

try:
    import _kaggriculture_simulator as _native_simulator
except Exception:
    _native_simulator = None

# Resolve native entry points once. Attribute lookup/hasattr in the interpreter
# runs hundreds of times per episode, so keep the hot loop on local callables.
_NATIVE_APPLY_PLAYER = (
    getattr(_native_simulator, "apply_player_actions", None)
    if _native_simulator is not None else None
)
_NATIVE_APPLY_TWO = (
    getattr(_native_simulator, "apply_two_player_actions", None)
    if _native_simulator is not None else None
)
_NATIVE_MARKET = (
    getattr(_native_simulator, "process_market_default", None)
    if _native_simulator is not None else None
)
_NATIVE_TOWN = (
    getattr(_native_simulator, "town_consume_default", None)
    if _native_simulator is not None else None
)
_NATIVE_DECAY_TWO = (
    getattr(_native_simulator, "decay_two_default", None)
    if _native_simulator is not None else None
)
_NATIVE_STEP = (
    getattr(_native_simulator, "step_default", None)
    if _native_simulator is not None else None
)
_NATIVE_RULES = (
    _NATIVE_APPLY_TWO is not None
    and _NATIVE_MARKET is not None
    and _NATIVE_TOWN is not None
    and _NATIVE_DECAY_TWO is not None
)


def _fast_spawn_hand(farm: Any, board_size: int) -> list[int]:
    half = board_size >> 1
    x0, x1 = half - 1, half
    y0, y1 = half - 1, half
    counts = [0, 0, 0, 0]

    def count(pos: Any) -> None:
        x, y = pos[0], pos[1]
        if y == y0:
            if x == x0: counts[0] += 1
            elif x == x1: counts[1] += 1
        elif y == y1:
            if x == x0: counts[2] += 1
            elif x == x1: counts[3] += 1

    count(farm["farmer"])
    for pos in farm["hands"]:
        count(pos)
    best = 0
    for idx in (1, 2, 3):
        if counts[idx] < counts[best]:
            best = idx
    return ([x0, y0], [x1, y0], [x0, y1], [x1, y1])[best]


def _fast_do_hire(farm: Any, private: Any, board_size: int, mult: int = None) -> None:
    if mult is None:
        mult = kaggriculture.FARM_HAND_COST_MULT
    cost = kaggriculture._hire_cost(farm["hires_today"], mult)
    if farm["money"] < cost:
        return
    farm["money"] -= cost
    farm["hires_today"] += 1
    farm["hands"].append(_fast_spawn_hand(farm, board_size))
    private["inventories"].append({})


def _fast_drop_inventories_to_shed(private: Any, capacity: int) -> None:
    shed = private["shed"]
    current = sum(shed.values())
    for inv in private["inventories"]:
        for item, n in list(inv.items()):
            if n <= 0:
                del inv[item]
                continue
            room = capacity - current
            if room > 0:
                take = n if n < room else room
                if take > 0:
                    shed[item] = shed.get(item, 0) + take
                    current += take
            del inv[item]


def _fast_end_of_day_default(state: list[Any], env: Any, day: int) -> None:
    obs0 = state[0].observation
    seed = env.info.get("seed", 0)
    rng = random.Random((seed * 1_000_003) ^ day)
    farms = obs0.farms
    for player_id in (0, 1):
        farm = farms[player_id]
        private = state[player_id].observation.private
        kaggriculture._daily_refresh_plants(farm, day, base._DEFAULT_TURNS_PER_DAY)
        kaggriculture._daily_refresh_animals(farm, day)
        kaggriculture._spawn_weeds(farm, base._DEFAULT_BOARD_SIZE, 0.005, rng)
        _fast_drop_inventories_to_shed(private, base._DEFAULT_SHED_CAPACITY)
        farm["farmer"] = [4, 4]
        farm["hands"] = []
        farm["hires_today"] = 0
        private["inventories"] = [{}]

    next_day = day + 1
    if next_day > 0 and next_day % 3 == 0:
        unlocked = obs0.town["unlocked_shops"]
        if len(unlocked) < kaggriculture.MAX_SHOP_INSTANCES:
            unlocked.append(rng.choice(_SORTED_SHOPS))


_SORTED_SHOPS = tuple(sorted(kaggriculture.SHOPS))
base._HELPER_GLOBALS["_do_hire"] = _fast_do_hire


def _apply_player_actions_v2(farm: Any, private: Any, action: Any, day: int) -> None:
    native_apply = _NATIVE_APPLY_PLAYER
    if native_apply is not None:
        native_apply(farm, private, action, day)
        return
    base._apply_player_actions(farm, private, action, day=day)


def _experimental_interpreter_v2(state: list[Any], env: Any) -> list[Any]:
    s0, s1 = state[0], state[1]
    obs0 = s0.observation
    step = obs0.get("step", 0)
    day = step // base._DEFAULT_TURNS_PER_DAY
    farms = obs0.farms
    private0 = s0.observation.private
    private1 = s1.observation.private
    action0 = s0.action
    action1 = s1.action

    native_step = _NATIVE_STEP
    if native_step is not None:
        native_step(
            farms,
            private0, action0,
            private1, action1,
            obs0.market, obs0.town,
            step,
        )
    elif _NATIVE_RULES:
        _NATIVE_APPLY_TWO(
            farms,
            private0, action0,
            private1, action1,
            day,
        )
        _NATIVE_MARKET(
            farms,
            private0, action0,
            private1, action1,
            obs0.market,
        )
        _NATIVE_TOWN(obs0.market, obs0.town, step)
        _NATIVE_DECAY_TWO(farms, step)
    else:
        _apply_player_actions_v2(farms[0], private0, action0, day)
        _apply_player_actions_v2(farms[1], private1, action1, day)
        base._fast_process_market(state, env)
        base._fast_town_consume_default(env, state, step)
        base._fast_decay_plants_default(farms[0], step)
        base._fast_decay_plants_default(farms[1], step)

    if (step + 1) % base._DEFAULT_TURNS_PER_DAY == 0:
        _fast_end_of_day_default(state, env, day)

    next_step = step + 1
    next_day = next_step // base._DEFAULT_TURNS_PER_DAY
    next_hour = next_step % base._DEFAULT_TURNS_PER_DAY
    obs0.day = next_day
    obs0.hour = next_hour
    obs1 = s1.observation
    obs1.day = next_day
    obs1.hour = next_hour

    if step >= env.configuration.episodeSteps - 2:
        s0.status = "DONE"
        s1.status = "DONE"
        s0.reward = float(farms[s0.observation.player]["money"])
        s1.reward = float(farms[s1.observation.player]["money"])
    return state


base._experimental_interpreter_default = _experimental_interpreter_v2


def _run_two_player_steps_v2(agent0, agent1, *, env, state, stop_step):
    s0, s1 = state[0], state[1]
    if s0.status != base._ACTIVE and s1.status != base._ACTIVE:
        return state
    step = int(s0.observation.get("step", 0))
    s0.observation.step = step
    s1.observation.step = step
    env.state = state
    interpreter = _experimental_interpreter_v2
    active = base._ACTIVE
    while step < stop_step:
        s0.action = agent0(s0.observation)
        s1.action = agent1(s1.observation)
        state = interpreter(state, env)
        step += 1
        s0, s1 = state[0], state[1]
        s0.observation.step = step
        s1.observation.step = step
        if s0.status != active and s1.status != active:
            break
    env.state = state
    return state


base._run_two_player_steps = _run_two_player_steps_v2

create_fast_episode = base.create_fast_episode
clone_fast_state = base.clone_fast_state
run_experimental_fast_episode = base.run_experimental_fast_episode
run_experimental_fast_steps = base.run_experimental_fast_steps
run_fast_episode = base.run_fast_episode
run_fast_steps = base.run_fast_steps
