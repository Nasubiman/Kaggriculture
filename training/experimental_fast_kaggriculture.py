#!/usr/bin/env python3
"""Experimental lower-overhead Kaggriculture runner.

This module deliberately lives next to, rather than replacing,
``fast_kaggriculture.py``.  It reuses the parity-tested fast interpreter and
initial-state creation, then specializes only the per-step hot loop for the
normal two-player training case.

The optimization relies on this invariant maintained by the existing runner:
after each interpreter call every returned observation already has its step
advanced to the next value.  Therefore the next loop iteration does not need
to write the same ``observation.step`` value again before calling the agents.
Likewise ``env.state`` already points at the current live state after the
previous iteration, so it only needs to be updated after the interpreter
returns a replacement state.

This is intentionally experimental.  Keep using ``fast_kaggriculture.py`` for
trusted production/evaluation work until trajectory parity and benchmark gates
have been run on the target machine.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

import fast_kaggriculture as stable
from kaggle_environments.envs.kaggriculture import kaggriculture


# Public aliases make this module drop-in compatible with benchmark/evaluation
# helpers that expect the stable runner API.
create_fast_episode = stable.create_fast_episode
clone_fast_state = stable.clone_fast_state


def run_experimental_fast_episode(
    agents: list[Callable[[Any], dict[str, Any]]],
    *,
    seed: int,
    episode_steps: int = 720,
    cache_market_prices: bool = True,
) -> list[Any]:
    """Run one episode through the experimental specialized hot loop."""
    env, state = create_fast_episode(
        seed=seed,
        episode_steps=episode_steps,
        num_agents=len(agents),
    )
    return run_experimental_fast_steps(
        agents,
        env=env,
        state=state,
        stop_step=episode_steps - 1,
        cache_market_prices=cache_market_prices,
    )


def _run_two_player_steps(
    agent0: Callable[[Any], dict[str, Any]],
    agent1: Callable[[Any], dict[str, Any]],
    *,
    env: Any,
    state: list[Any],
    stop_step: int,
    interpreter: Callable[[list[Any], Any], list[Any]],
) -> list[Any]:
    """Specialized hot loop for Kaggriculture's normal two-player case."""
    step = int(state[0].observation.get("step", 0))
    env.state = state

    while step < stop_step:
        state0 = state[0]
        state1 = state[1]

        # observation.step is already equal to ``step`` here: it is initialized
        # that way for the first turn and explicitly advanced after each call.
        state0.action = agent0(state0.observation)
        state1.action = agent1(state1.observation)

        state = interpreter(state, env)
        step += 1

        # The official interpreter does not own the framework's step counter;
        # preserve the stable runner's observable contract for the next agents.
        state0 = state[0]
        state1 = state[1]
        state0.observation.step = step
        state1.observation.step = step

        # Environment.done and future interpreter calls must observe the newly
        # returned live state.  A second assignment at the top of the next loop
        # would be redundant, so this is the only per-turn env.state write.
        env.state = state

        # Avoid constructing a generator and calling all() on every step in the
        # overwhelmingly common two-player case.
        if state0.status != "ACTIVE" and state1.status != "ACTIVE":
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
    """Advance a live state with a two-player specialization when possible.

    Non-two-player calls intentionally fall back to the stable implementation;
    the experiment should only change the hot path we can validate directly.
    """
    if len(agents) != 2 or len(state) != 2:
        return stable.run_fast_steps(
            agents,
            env=env,
            state=state,
            stop_step=stop_step,
            cache_market_prices=cache_market_prices,
        )

    interpreter = (
        stable._FAST_INTERPRETER
        if cache_market_prices
        else kaggriculture.interpreter
    )
    return _run_two_player_steps(
        agents[0],
        agents[1],
        env=env,
        state=state,
        stop_step=stop_step,
        interpreter=interpreter,
    )


# Drop-in name used by existing benchmark helpers.
run_fast_episode = run_experimental_fast_episode
run_fast_steps = run_experimental_fast_steps
