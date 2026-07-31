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
from typing import Any

from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture


_ENV_CACHE: dict[tuple[int, int], tuple[Any, list[Any]]] = {}


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
) -> list[Any]:
    """Advance a live state until observation.step reaches ``stop_step``."""
    start_step = int(state[0].observation.get("step", 0))
    env.state = state

    for step in range(start_step, stop_step):
        for index, agent in enumerate(agents):
            state[index].observation.step = step
            state[index].action = agent(state[index].observation)

        # interpreter() checks env.done and reads env.configuration/info.
        # Point env.state at the live state without invoking Environment.step.
        env.state = state
        state = kaggriculture.interpreter(state, env)
        for agent_state in state:
            agent_state.observation.step = step + 1
        env.state = state

        if all(agent_state.status != "ACTIVE" for agent_state in state):
            break

    return state
