"""Research hybrid: Fourth Quadrant replay opening, incumbent continuation."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import rank1_knn
import incumbent


SWITCH_STEP = int(json.loads((ROOT / "hybrid_settings.json").read_text())["switch_step"])


def agent(observation, configuration=None):
    # Keep both internal clocks synchronized with every observed turn.
    imitated = rank1_knn.agent(observation, configuration)
    baseline = incumbent.kaggle_agent(observation, configuration)
    return imitated if int(observation["step"]) < SWITCH_STEP else baseline
