"""Production Kaggriculture runner selected by the v4 parity gate.

Keep this small facade as the import boundary for searches and evaluations.
The stable runner remains available in ``fast_kaggriculture`` for differential
tests and as the guarded fallback used by the v4 implementation.
"""

from experimental_fast_kaggriculture_v3 import (
    clone_fast_state,
    create_fast_episode,
    run_fast_episode,
    run_fast_steps,
)

__all__ = (
    "clone_fast_state",
    "create_fast_episode",
    "run_fast_episode",
    "run_fast_steps",
)
