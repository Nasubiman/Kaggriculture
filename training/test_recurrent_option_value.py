#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import torch

from recurrent_option_value import (
    OptionValueConfig,
    RecurrentOptionValueNet,
    load_checkpoint,
    save_checkpoint,
)


class RecurrentOptionValueTests(unittest.TestCase):
    def make_model(self) -> RecurrentOptionValueNet:
        return RecurrentOptionValueNet(
            OptionValueConfig(
                state_dim=34,
                option_dim=12,
                hidden_dim=48,
                ensemble_heads=3,
                uncertainty_scale=1.0,
                minimum_advantage=0.1,
            )
        )

    def test_forward_is_keep_relative(self) -> None:
        torch.manual_seed(1)
        model = self.make_model()
        history = torch.randn(4, 5, 34)
        lengths = torch.tensor([5, 3, 4, 1])
        options = torch.randn(7, 12)
        values = model(history, lengths, options)
        self.assertEqual(tuple(values.shape), (3, 4, 7))
        torch.testing.assert_close(values[:, :, 0], torch.zeros(3, 4))
        self.assertTrue(torch.isfinite(values).all())

    def test_padding_after_length_does_not_change_output(self) -> None:
        torch.manual_seed(2)
        model = self.make_model().eval()
        history = torch.randn(2, 4, 34)
        lengths = torch.tensor([2, 4])
        options = torch.randn(6, 12)
        baseline = model(history, lengths, options)
        history[0, 2:] = torch.randn_like(history[0, 2:]) * 1000
        changed = model(history, lengths, options)
        torch.testing.assert_close(baseline[:, 0], changed[:, 0])

    def test_conservative_selector_abstains(self) -> None:
        torch.manual_seed(3)
        model = self.make_model().eval()
        history = torch.randn(2, 3, 34)
        lengths = torch.tensor([3, 3])
        options = torch.randn(5, 12)
        # A very large threshold must force KEEP regardless of random weights.
        object.__setattr__(
            model.config,
            "minimum_advantage",
            1e9,
        )
        selected = model.select(history, lengths, options)
        torch.testing.assert_close(selected["action"], torch.zeros(2, dtype=torch.long))

    def test_masked_options_are_never_selected(self) -> None:
        torch.manual_seed(4)
        model = self.make_model().eval()
        history = torch.randn(3, 2, 34)
        lengths = torch.tensor([2, 2, 2])
        options = torch.randn(4, 12)
        mask = torch.zeros(3, 4, dtype=torch.bool)
        mask[:, 0] = True
        selected = model.select(history, lengths, options, mask)
        torch.testing.assert_close(selected["action"], torch.zeros(3, dtype=torch.long))

    def test_ranking_loss_backpropagates(self) -> None:
        torch.manual_seed(5)
        model = self.make_model()
        history = torch.randn(8, 5, 34)
        lengths = torch.randint(1, 6, (8,))
        options = torch.randn(7, 12)
        target = torch.randn(8, 7)
        target[:, 0] = 0.0
        predicted = model(history, lengths, options)
        regression = torch.nn.functional.smooth_l1_loss(
            predicted.mean(dim=0), target
        )
        target_diff = target.unsqueeze(2) - target.unsqueeze(1)
        prediction = predicted.mean(dim=0)
        prediction_diff = prediction.unsqueeze(2) - prediction.unsqueeze(1)
        signs = torch.sign(target_diff)
        comparable = signs != 0
        ranking = torch.nn.functional.softplus(
            -signs * prediction_diff
        )[comparable].mean()
        loss = regression + 0.25 * ranking
        loss.backward()
        total = sum(
            float(parameter.grad.abs().sum())
            for parameter in model.parameters()
            if parameter.grad is not None
        )
        self.assertGreater(total, 0.0)

    def test_checkpoint_round_trip(self) -> None:
        torch.manual_seed(6)
        model = self.make_model().eval()
        history = torch.randn(2, 3, 34)
        lengths = torch.tensor([3, 2])
        options = torch.randn(5, 12)
        expected = model(history, lengths, options)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "option_value.pt"
            save_checkpoint(
                path,
                model,
                option_names=["KEEP", "A", "B", "C", "D"],
                state_feature_names=[f"s{i}" for i in range(34)],
                option_feature_names=[f"o{i}" for i in range(12)],
                metadata={"smoke": True},
            )
            loaded, payload = load_checkpoint(path)
            actual = loaded(history, lengths, options)
        torch.testing.assert_close(actual, expected)
        self.assertEqual(payload["metadata"], {"smoke": True})


if __name__ == "__main__":
    unittest.main()
