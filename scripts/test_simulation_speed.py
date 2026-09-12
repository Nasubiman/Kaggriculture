#!/usr/bin/env python3
"""Regression checks for action-copy isolation and fast interpreter helpers."""
from __future__ import annotations

import copy
import importlib.util
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
import fast_kaggriculture as fast
from kaggle_environments.envs.kaggriculture import kaggriculture as official

spec = importlib.util.spec_from_file_location("speed_test_agent", ROOT / "main.py")
agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent)


class ActionCopies(unittest.TestCase):
    def test_copy_isolates_every_mutable_action_container(self):
        original = {"farmer": ["PICKUP", "WHEAT", 3],
                    "hands": [["PASS"], ["FEED"]],
                    "market": [["SELL", "MILK", 6]],
                    "metadata": {"nested": [1]}}
        before = copy.deepcopy(original)
        cloned = agent._copy_action(original)
        self.assertEqual(cloned, before)
        cloned["farmer"][2] = 99
        cloned["hands"][0][0] = "NORTH"
        cloned["hands"].append(["PASS"])
        cloned["market"][0][2] = 1
        cloned["market"].append(["HIRE"])
        cloned["metadata"]["nested"].append(2)
        self.assertEqual(original, before)
        self.assertEqual(agent._copy_action({}), {})

    def test_all_route_commands_obey_scalar_copy_contract(self):
        # A future tape format change must not silently introduce shared objects.
        for tape in agent._IMPL.chassis.routes.values():
            for action in tape:
                self.assertEqual(agent._copy_action(action), copy.deepcopy(action))
                commands = [action["farmer"], *action["hands"], *action["market"]]
                for command in commands:
                    self.assertIs(type(command), list)
                    self.assertTrue(all(type(arg) in (str, int, float, bool, type(None))
                                        for arg in command))

    def test_layer_failure_returns_original_tape_and_leaves_it_intact(self):
        original = {"farmer": ["PASS"], "hands": [], "market": [["HIRE"]]}
        before = copy.deepcopy(original)
        chassis = agent.Chassis({"test": [original]})

        def fail(action, view):
            action["farmer"][0] = "EAST"
            action["market"][0][0] = "INVALID"
            raise RuntimeError("injected failure after mutation")

        chassis._hand_align = fail
        _, state = fast.create_fast_episode(seed=123)
        result = chassis.act(state[0].observation)
        self.assertEqual(result, before)
        self.assertEqual(original, before)
        self.assertEqual(chassis.diagnostics["layer_fallbacks"], 1)
        result["market"][0][0] = "PASS"
        self.assertEqual(original, before)


class InterpreterHelpers(unittest.TestCase):
    def test_decay_matches_official_at_expiry_and_across_days(self):
        rng = random.Random(193)
        for board in (4, 6, 10):
            for trial in range(10):
                tiles = [[rng.choice([
                    None, "LOCKED", {"kind": "WEED"}, {"kind": "PASTURE"},
                    {"kind": "PLANT", "max_lifespan_step": rng.choice([-1, 0, 1, 23, 24, 48]),
                     "yield_units": rng.randint(0, 6)},
                ]) for _ in range(board)] for _ in range(board)]
                expected = {"tiles": copy.deepcopy(tiles)}
                actual = copy.deepcopy(expected)
                for step in range(60):
                    official._decay_plants(expected, step)
                    fast._fast_decay_plants(actual, step)
                    self.assertEqual(actual, expected, (board, trial, step))

    def test_shed_adjacency_matches_official_for_multiple_boards(self):
        for board in (4, 5, 6, 10, 12):
            for x in range(-1, board + 1):
                for y in range(-1, board + 1):
                    for pos in ([x, y], (x, y)):
                        self.assertEqual(fast._fast_is_shed_adjacent(pos, board),
                                         official._is_shed_adjacent(pos, board))

    def test_standard_interpreter_globals_remain_untouched(self):
        self.assertIs(official.interpreter.__globals__["_decay_plants"], official._decay_plants)
        self.assertIs(official._apply_unit_action.__globals__["_is_shed_adjacent"],
                      official._is_shed_adjacent)
        self.assertIs(official.market_price, fast._OFFICIAL_MARKET_PRICE)
        self.assertIsNot(fast._FAST_INTERPRETER.__globals__, official.interpreter.__globals__)


if __name__ == "__main__":
    unittest.main()
