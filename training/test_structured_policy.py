#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import torch
from torch.distributions import Categorical

from hybrid_policy import ACTION_COUNT, OBSERVATION_SIZE, masked_logits
from structured_checkpoint import (
    load_structured_checkpoint,
    save_structured_checkpoint,
)
from structured_policy import TOKEN_SLICES, build_structured_policy


class StructuredPolicyTests(unittest.TestCase):
    def test_token_layout_covers_observation_once(self) -> None:
        cursor = 0
        for spec in TOKEN_SLICES:
            self.assertEqual(spec.start, cursor)
            self.assertGreater(spec.stop, spec.start)
            cursor = spec.stop
        self.assertEqual(cursor, OBSERVATION_SIZE)

    def test_forward_shapes_and_finite_outputs(self) -> None:
        model = build_structured_policy(d_model=64, n_heads=4, n_layers=2)
        observations = torch.randn(7, OBSERVATION_SIZE)
        logits, values = model(observations)
        self.assertEqual(tuple(logits.shape), (7, ACTION_COUNT))
        self.assertEqual(tuple(values.shape), (7,))
        self.assertTrue(torch.isfinite(logits).all())
        self.assertTrue(torch.isfinite(values).all())

    def test_masked_ppo_loss_backpropagates(self) -> None:
        torch.manual_seed(7)
        model = build_structured_policy(d_model=64, n_heads=4, n_layers=2)
        observations = torch.randn(16, OBSERVATION_SIZE)
        masks = torch.rand(16, ACTION_COUNT) > 0.25
        masks[:, 0] = True
        logits, values = model(observations)
        distribution = Categorical(logits=masked_logits(logits, masks))
        actions = distribution.sample()
        advantages = torch.randn(16)
        returns = torch.randn(16)
        loss = -(distribution.log_prob(actions) * advantages).mean()
        loss = loss + 0.5 * (values - returns).square().mean()
        loss.backward()
        gradients = [
            parameter.grad
            for parameter in model.parameters()
            if parameter.requires_grad and parameter.grad is not None
        ]
        self.assertTrue(gradients)
        total = sum(float(gradient.abs().sum()) for gradient in gradients)
        self.assertGreater(total, 0.0)

    def test_checkpoint_round_trip(self) -> None:
        torch.manual_seed(11)
        model = build_structured_policy(d_model=64, n_heads=4, n_layers=2).eval()
        observations = torch.randn(3, OBSERVATION_SIZE)
        expected = model(observations)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "policy.pt"
            save_structured_checkpoint(path, model, update=12, metadata={"smoke": True})
            loaded, payload = load_structured_checkpoint(path)
            actual = loaded(observations)
        self.assertEqual(payload["update"], 12)
        self.assertEqual(payload["metadata"], {"smoke": True})
        torch.testing.assert_close(actual[0], expected[0])
        torch.testing.assert_close(actual[1], expected[1])


if __name__ == "__main__":
    unittest.main()
