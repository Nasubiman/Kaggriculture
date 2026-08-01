#!/usr/bin/env python3
"""Low-overhead Kaggriculture runner for trusted in-process training agents.

The public kaggle-environments runner validates actions, deep-copies shared
observations, converts nested objects, and stores every replay step. Those
features are valuable for evaluation and untrusted agents, but dominate CPU
time during training. This runner calls the official Kaggriculture interpreter
directly while preserving its initialization, state transitions, RNG, and
terminal rewards.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from functools import lru_cache
from types import FunctionType
from typing import Any

from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture


_ENV_CACHE: dict[tuple[int, int], tuple[Any, list[Any]]] = {}
_MARKET_PRICE_CACHE_SIZE = 65_536


# The interpreter refreshes all nine prices after most market/town operations.
# In normal games this asks for the same (item, inventory) price tens of
# thousands of times.  Default market parameters are immutable, so caching
# that pure calculation is safe; custom per-environment parameters keep using
# the official implementation.
_OFFICIAL_MARKET_PRICE = kaggriculture.market_price


@lru_cache(maxsize=_MARKET_PRICE_CACHE_SIZE)
def _cached_default_market_price(item: str, inventory: int) -> int:
    return _OFFICIAL_MARKET_PRICE(item, inventory)


def _fast_market_price(
    item: str, inventory: int, params: Any = None
) -> int:
    if params is not None:
        return _OFFICIAL_MARKET_PRICE(item, inventory, params)
    return _cached_default_market_price(item, inventory)


def _clone_function(function: Callable[..., Any], globals_: dict[str, Any]) -> Any:
    """Clone official code with isolated globals, leaving the public runner alone."""
    clone = FunctionType(
        function.__code__,
        globals_,
        function.__name__,
        function.__defaults__,
        function.__closure__,
    )
    clone.__kwdefaults__ = function.__kwdefaults__
    return clone


def _build_fast_interpreter() -> Callable[[list[Any], Any], list[Any]]:
    # These are the only official functions whose global lookups lead to
    # market_price.  Reusing their original code objects minimizes drift risk
    # while keeping kaggriculture.market_price untouched for standard runs.
    globals_ = dict(vars(kaggriculture))
    globals_["market_price"] = _fast_market_price
    for name in (
        "_refresh_prices",
        "_process_market",
        "_town_consume",
        "interpreter",
    ):
        globals_[name] = _clone_function(getattr(kaggriculture, name), globals_)
    return globals_["interpreter"]


_FAST_INTERPRETER = _build_fast_interpreter()


def _initial_state(
    *, seed: int, episode_steps: int, num_agents: int
) -> tuple[Any, list[Any]]:
    """Return a fresh initial state, reusing validated environment metadata."""
    key = (episode_steps, num_agents)
    cached = _ENV_CACHE.get(key)
    if cached is None:
        # make() already resets and initializes the requested two-player state;
        # calling reset() again would repeat schema validation unnecessarily.
        env = make(
            "kaggriculture",
            configuration={"episodeSteps": episode_steps, "seed": seed},
            debug=False,
        )
        template = copy.deepcopy(env.state)
        _ENV_CACHE[key] = (env, template)
        return env, env.state

    env, template = cached
    env.info["seed"] = seed
    state = copy.deepcopy(template)
    env.state = state
    env.steps = [state]
    env.logs = []
    return env, state


def run_fast_episode(
    agents: list[Callable[[Any], dict[str, Any]]],
    *,
    seed: int,
    episode_steps: int = 720,
    cache_market_prices: bool = True,
) -> list[Any]:
    """Run trusted agents without schema/deepcopy/replay overhead."""
    env, state = create_fast_episode(
        seed=seed,
        episode_steps=episode_steps,
        num_agents=len(agents),
    )

    return run_fast_steps(
        agents,
        env=env,
        state=state,
        stop_step=episode_steps - 1,
        cache_market_prices=cache_market_prices,
    )


def create_fast_episode(
    *, seed: int, episode_steps: int = 720, num_agents: int = 2
) -> tuple[Any, list[Any]]:
    """Create a fresh official initial state for interval/branch execution."""
    return _initial_state(
        seed=seed,
        episode_steps=episode_steps,
        num_agents=num_agents,
    )


def clone_fast_state(state: list[Any]) -> list[Any]:
    """Clone a trusted live state for counterfactual continuation."""
    return copy.deepcopy(state)


def run_fast_steps(
    agents: list[Callable[[Any], dict[str, Any]]],
    *,
    env: Any,
    state: list[Any],
    stop_step: int,
    cache_market_prices: bool = True,
) -> list[Any]:
    """Advance a live state until observation.step reaches ``stop_step``."""
    start_step = int(state[0].observation.get("step", 0))
    env.state = state
    interpreter = (
        _FAST_INTERPRETER
        if cache_market_prices
        else kaggriculture.interpreter
    )

    for step in range(start_step, stop_step):
        for index, agent in enumerate(agents):
            state[index].observation.step = step
            state[index].action = agent(state[index].observation)

        # interpreter() checks env.done and reads env.configuration/info.
        # Point env.state at the live state without invoking Environment.step.
        env.state = state
        state = interpreter(state, env)
        for agent_state in state:
            agent_state.observation.step = step + 1
        env.state = state

        if all(agent_state.status != "ACTIVE" for agent_state in state):
            break

    return state
