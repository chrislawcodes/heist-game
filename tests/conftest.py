"""Shared test setup.

Sets ``HEIST_TURN_DELAY=0`` for the entire test session so:
  • per-turn delays are zero (existing behavior the smoke tests already use), and
  • the feature-003 parallel-call rate-limit stagger (default 30s in production)
    drops to 0 so tests aren't paying real wall-clock for the production guard.

The HEIST_TURN_DELAY=0 knob is the canonical "fast/test mode" flag in this repo;
production servers and live Quick Tests on staging do not set it.
"""

from __future__ import annotations

import os

os.environ.setdefault("HEIST_TURN_DELAY", "0")
