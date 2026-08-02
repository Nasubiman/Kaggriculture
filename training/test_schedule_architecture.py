#!/usr/bin/env python3
from __future__ import annotations

import unittest

import torch

from recurrent_option_value import (
    OptionValueConfig,
    RecurrentOptionValueNet,
    counterfactual_value_loss,
)
from schedule_registry import ScheduleAnchor, ScheduleOption, ScheduleRegistry
from schedule_repair_policy import RepairValueConfig, RepairValueNet


class ScheduleRegistryTests(unittest.TestCase):
    def make_registry(self) -> ScheduleRegistry:
        return ScheduleRegistry(
            [
                ScheduleOption(
                    option_id="KEEP",
                    version=1,
                    family="incumbent",
                    controller="main:_decide",
                    source="promoted main.py",
                    description="Keep the promoted controller",
                    descriptor=(0.0, 0.0, 0.0),
                    anchors=(ScheduleAnchor(0, {"hands": 4}, {"hands": 2}),),
                    entry_days=(0, 8),
                    commit_until_day=0,
                    licence="repository",
                ),
                ScheduleOption(
                    option_id="KAITO_STRAWBERRY_BALANCED",
                    version=1,
                    family="tape",
                    controller="tapes:kaito_89454731",
                    source="public episode 89454731",
                    description="Melon opening, strawberry scale, mixed herd",
                    descriptor=(1.0, 0.5, 0.8),
                    anchors=(
                        ScheduleAnchor(0, {"hands": 4, "cows": 3, "sheep": 1}),
                        ScheduleAnchor(12, {"hands": 12, "cows": 8, "sheep": 7}),
                    ),
                    entry_days=(0,),
                    commit_until_day=29,
                    licence="public replay",
                ),
            ]
        )

    def test_fingerprint_is_stable(self) -> None:
        first = self.make_registry()
        second = self.make_registry()
        self.assertEqual(first.fingerprint(), second.fingerprint())
        self.assertEqual(first.descriptor_width, 3)

    def test_commitment_blocks_arbitrary_switches(self) -> None:
        registry = self.make_registry()
        active = registry.options[1].key
        self.assertEqual(registry.valid_mask(8, active_key=active), (True, True))
        self.assertEqual(registry.valid_mask(8, active_key=registry.options[0].key), (True, False))

    def test_anchor_deviation_is_normalized(self) -> None:
        anchor = ScheduleAnchor(12, {"hands": 12, "cows": 8}, {"hands": 2, "cows": 4})
        self.assertEqual(anchor.deviation({"hands": 10, "cows": 12}, ["hands", "cows"]), (-1.0, 1.0))


class ScheduleValueTests(unittest.TestCase):
    def test_counterfactual_loss_backpropagates(self) -> None:
        torch.manual_seed(1)
        model = RecurrentOptionValueNet(
            OptionValueConfig(state_dim=8, option_dim=3, hidden_dim=24, ensemble_heads=3)
        )
        history = torch.randn(5, 4, 8)
        lengths = torch.tensor([4, 3, 2, 4, 1])
        options = torch.randn(4, 3)
        target = torch.randn(5, 4)
        target[:, 0] = 0
        per_head = model(history, lengths, options)
        metrics = counterfactual_value_loss(per_head, target)
        metrics["loss"].backward()
        gradient = sum(
            float(parameter.grad.abs().sum())
            for parameter in model.parameters()
            if parameter.grad is not None
        )
        self.assertGreater(gradient, 0)
        self.assertTrue(torch.isfinite(metrics["loss"]))


class RepairValueTests(unittest.TestCase):
    def make_model(self) -> RepairValueNet:
        return RepairValueNet(
            RepairValueConfig(
                state_dim=10,
                schedule_dim=4,
                deviation_dim=5,
                candidate_dim=6,
                hidden_dim=32,
                ensemble_heads=3,
                minimum_advantage=1e9,
            )
        ).eval()

    def make_inputs(self):
        history = torch.randn(3, 4, 10)
        lengths = torch.tensor([4, 3, 2])
        schedule = torch.randn(3, 4)
        deviation = torch.randn(3, 5)
        candidates = torch.randn(3, 5, 6)
        valid = torch.ones(3, 5, dtype=torch.bool)
        fallback = torch.tensor([1, 2, 1])
        required = torch.tensor([True, True, False])
        return history, lengths, schedule, deviation, candidates, valid, fallback, required

    def test_high_threshold_uses_rule_fallback(self) -> None:
        torch.manual_seed(2)
        model = self.make_model()
        args = self.make_inputs()
        result = model.select(
            *args[:5], valid_mask=args[5], fallback_indices=args[6], repair_required=args[7]
        )
        expected = torch.tensor([1, 2, 0])
        torch.testing.assert_close(result["action"], expected)

    def test_invalid_planned_action_uses_fallback_without_trigger(self) -> None:
        torch.manual_seed(3)
        model = self.make_model()
        args = list(self.make_inputs())
        args[5][2, 0] = False
        result = model.select(
            *args[:5], valid_mask=args[5], fallback_indices=args[6], repair_required=args[7]
        )
        self.assertEqual(int(result["action"][2]), int(args[6][2]))

    def test_relative_values_anchor_each_fallback(self) -> None:
        raw = torch.tensor(
            [
                [[1.0, 3.0, 5.0], [2.0, 4.0, 7.0]],
                [[0.0, 2.0, 6.0], [1.0, 5.0, 8.0]],
            ]
        )
        relative = RepairValueNet.relative_to_fallback(raw, torch.tensor([1, 2]))
        torch.testing.assert_close(relative[:, 0, 1], torch.zeros(2))
        torch.testing.assert_close(relative[:, 1, 2], torch.zeros(2))


if __name__ == "__main__":
    unittest.main()
