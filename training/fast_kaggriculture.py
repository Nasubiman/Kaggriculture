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
    env, state = _initial_state(
        seed=seed,
        episode_steps=episode_steps,
        num_agents=len(agents),
    )

    for step in range(episode_steps - 1):
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
