"""Cheap regression checks for incumbent-centered genome search."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import random
import types
import unittest

from current_genome import configure_module, mutate
from search_current_genomes import DEFAULT_OPPONENTS, initial_pool, read_incumbent


ROOT = Path(__file__).resolve().parents[1]


class CurrentGenomeSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = read_incumbent(ROOT / "main.py")

    def test_pool_is_centered_on_current_model(self):
        pool = initial_pool(self.base, random.Random(1), 48)
        self.assertEqual(len(pool), 48)
        self.assertEqual(pool[0]["label"], "incumbent")
        self.assertEqual(pool[0]["genome"].key(), self.base.key())
        self.assertGreaterEqual(sum(
            row["genome"].secondary_item == self.base.secondary_item
            and row["genome"].tertiary_item == self.base.tertiary_item
            and row["genome"].wool_policy == self.base.wool_policy
            for row in pool
        ), 36)
        self.assertTrue(any(
            row["genome"].opening_roundtrip_mode != "inherit" for row in pool
        ))
        self.assertIn("public_v45_competitive_20260916", DEFAULT_OPPONENTS)

    def test_opening_orders_are_net_thirteen(self):
        observation = {"step": 0, "player": 0, "private": {"shed": {}},
                       "market": {"prices": {}}, "farms": []}
        for mode in ("roundtrip_first", "sell_buy_tail", "combined"):
            with self.subTest(mode=mode):
                module = types.SimpleNamespace(agent=lambda *_: {
                    "farmer": ["PASS"], "hands": [], "market": []
                })
                agent = configure_module(module, replace(
                    self.base, opening_roundtrip_mode=mode,
                    opening_roundtrip_quantity=45,
                ))
                market = agent(observation)["market"]
                net = sum(order[2] if order[0] == "BUY_PRODUCT" else -order[2]
                          for order in market)
                self.assertEqual(net, 13)
                self.assertLessEqual(len(market), 3)

    def test_mutations_preserve_valid_genomes(self):
        rng = random.Random(3)
        for _ in range(100):
            genome = mutate(self.base, rng, changes=3)
            self.assertEqual(genome, genome.normalized())


if __name__ == "__main__":
    unittest.main()
