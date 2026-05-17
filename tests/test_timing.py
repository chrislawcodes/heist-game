"""Per-round timing: every AI call must be logged with a label and elapsed
seconds, and the markdown report must render the timing table."""

import random

from heist.content import DEFAULT_PROMPT
from heist.output import render_markdown
from heist.runner import run_heist
from heist.state import TurnLog
from heist.stub_responses import build_stub_ai


def test_turn_logs_captured_for_every_ai_call():
    state, extras = run_heist(DEFAULT_PROMPT, build_stub_ai(), rng=random.Random(7))
    logs = extras["turn_logs"]
    assert logs, "no rounds were logged"
    assert all(isinstance(t, TurnLog) for t in logs)
    # Every log entry needs a non-empty label and a non-negative elapsed time
    for t in logs:
        assert t.label, "round had empty label"
        assert t.seconds >= 0, f"round {t.label} had negative time {t.seconds}"


def test_log_labels_cover_canonical_phases():
    state, extras = run_heist(DEFAULT_PROMPT, build_stub_ai(), rng=random.Random(7))
    labels = [t.label for t in extras["turn_logs"]]
    # These should always appear in a stub-driven run
    assert "bid" in labels
    assert "job_pick" in labels
    assert "casting_summary" in labels
    assert "epilogue" in labels
    # At least one scene-assign and one scene-narrate
    assert any(lbl.endswith("_assign") for lbl in labels)
    assert any(lbl.endswith("_narrate") for lbl in labels)


def test_total_seconds_recorded():
    _, extras = run_heist(DEFAULT_PROMPT, build_stub_ai(), rng=random.Random(7))
    assert "total_seconds" in extras
    assert extras["total_seconds"] >= 0


def test_markdown_includes_timing_table():
    state, extras = run_heist(DEFAULT_PROMPT, build_stub_ai(), rng=random.Random(7))
    md = render_markdown(state, extras)
    assert "## Timing" in md
    assert "| Round | Seconds |" in md
    assert "AI total" in md
    assert "Wall clock" in md
    # The bid round should appear by label
    assert "| bid |" in md
