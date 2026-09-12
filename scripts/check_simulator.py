#!/usr/bin/env python3
"""Fail fast when Kaggriculture is using stale rules or a drifting fast runner."""

from __future__ import annotations

import importlib.util
from importlib.metadata import version
from pathlib import Path
from typing import Any

from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture

from fast_kaggriculture import run_fast_episode


EXPECTED_VERSION = "1.32.7"
SEED = 8_150_2026
EPISODE_STEPS = 49
ROOT = Path(__file__).resolve().parents[1]


def probe_agent(observation: Any) -> dict[str, Any]:
    """Exercise hiring, locked-tile movement, town ticks, and daily refreshes."""
    hour = int(observation.get("hour", 0))
    hands = []
    for position in observation["farms"][observation["player"]].get("hands", []):
        # The first hand normally spawns at locked (5, 4). Moving WEST proves
        # that the new interpreter does not strand it there.
        hands.append(["WEST"] if int(position[0]) >= 5 else ["PASS"])
    market = [["HIRE"]] if hour == 0 else []
    return {"farmer": ["PASS"], "hands": hands, "market": market}


def plain(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(item) for item in value]
    return value


def state_snapshot(state: list[Any]) -> list[dict[str, Any]]:
    snapshots = []
    for agent_state in state:
        observation = plain(agent_state.observation)
        # The framework injects ``step`` only into the active agent view and may
        # omit it from the other final view. It is metadata, not game state.
        observation.pop("step", None)
        snapshots.append({
            "status": str(agent_state.status),
            "reward": agent_state.reward,
            "observation": observation,
        })
    return snapshots


def check_rule_constants() -> None:
    installed = version("kaggle-environments")
    assert installed == EXPECTED_VERSION, (
        f"expected kaggle-environments {EXPECTED_VERSION}, found {installed}; "
        "run `make simulator-update`"
    )
    assert kaggriculture.MARKET_PARAMS["CARROT"]["below_func"] == "hinge"
    assert kaggriculture.MARKET_PARAMS["CARROT"]["below_target"] == 1.0
    assert kaggriculture.MARKET_PARAMS["TOMATO"]["below_func"] == "hinge"
    assert kaggriculture.MARKET_PARAMS["EGG"]["below_func"] == "hinge"
    assert kaggriculture._shape("hinge", 2.0, 1.0) == 10.0

    environment = make("kaggriculture", configuration={"seed": SEED})
    assert int(environment.configuration.townCenterSellInterval) == 24


def check_locked_tile_movement() -> None:
    environment = make(
        "kaggriculture",
        configuration={"episodeSteps": 3, "seed": SEED},
        debug=True,
    )
    environment.run([probe_agent, probe_agent])
    # Step 1 hires the first hand onto locked (5, 4); on step 2 it moves WEST.
    for agent_state in environment.steps[-1]:
        assert list(agent_state.observation.farms[agent_state.observation.player]["hands"][0]) == [4, 4]


def check_fast_standard_parity() -> None:
    standard_environment = make(
        "kaggriculture",
        configuration={"episodeSteps": EPISODE_STEPS, "seed": SEED},
        debug=True,
    )
    standard_environment.run([probe_agent, probe_agent])
    standard = state_snapshot(standard_environment.steps[-1])
    fast = state_snapshot(
        run_fast_episode(
            [probe_agent, probe_agent],
            seed=SEED,
            episode_steps=EPISODE_STEPS,
        )
    )
    assert fast == standard, "fast runner state drifted from the standard runner"


def load_agent(module_name: str) -> Any:
    path = ROOT / "main.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load agent from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.agent


def check_full_game_parity() -> None:
    """Cover real crop, animal, market, and town behavior for all 720 turns."""
    standard_environment = make(
        "kaggriculture",
        configuration={"episodeSteps": 720, "seed": SEED + 1},
        debug=True,
    )
    standard_environment.run(
        [load_agent("simulator_standard_0"), load_agent("simulator_standard_1")]
    )
    standard = state_snapshot(standard_environment.steps[-1])
    fast = state_snapshot(
        run_fast_episode(
            [load_agent("simulator_fast_0"), load_agent("simulator_fast_1")],
            seed=SEED + 1,
            episode_steps=720,
        )
    )
    assert fast == standard, "full-game fast runner state drifted from standard"


def main() -> None:
    check_rule_constants()
    check_locked_tile_movement()
    check_fast_standard_parity()
    check_full_game_parity()
    print(
        "simulator OK: "
        f"kaggle-environments={EXPECTED_VERSION}, rules=2026-08, "
        "locked-movement=OK, fast-standard-parity=OK"
    )


if __name__ == "__main__":
    main()
