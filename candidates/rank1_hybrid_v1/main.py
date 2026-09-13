"""Exact rank-1 opening followed by the current robust reactive policy."""

from __future__ import annotations

from pathlib import Path
import sys


_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import base_policy
import leader_bc


def agent(observation, configuration=None):
    # Keep the stateful fallback synchronized even while its action is hidden.
    fallback = base_policy.agent(observation, configuration)
    step = int(observation.get("step", 0))
    if step < len(leader_bc._OPENING):
        return leader_bc.agent(observation)
    return fallback
