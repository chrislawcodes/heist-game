"""CLI entrypoint: `python -m heist [--prompt-file PATH] [--out PATH] [--seed N]
[--agent stub|codex|gemini]`.

Iteration 1: only `--agent stub` works. Real backends land in iteration 3.
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

from heist.ai import HeistAI
from heist.content import DEFAULT_PROMPT
from heist.output import render_markdown
from heist.runner import run_heist
from heist.stub_responses import build_stub_ai


def _build_ai(agent: str) -> HeistAI:
    if agent == "stub":
        return build_stub_ai()
    raise SystemExit(
        f"agent={agent!r} not wired yet — iteration 1 only supports --agent stub"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="heist")
    parser.add_argument("--prompt-file", type=Path, default=None,
                        help="File with strategy prompt; default = built-in default.")
    parser.add_argument("--out", type=Path, default=Path("heist_report.md"),
                        help="Markdown output path.")
    parser.add_argument("--seed", type=int, default=None,
                        help="RNG seed for reproducible hidden-depth rolls.")
    parser.add_argument("--agent", default="stub", choices=["stub", "codex", "gemini"],
                        help="Heist AI backend.")
    args = parser.parse_args(argv)

    prompt = args.prompt_file.read_text() if args.prompt_file else DEFAULT_PROMPT
    rng = random.Random(args.seed)
    ai = _build_ai(args.agent)

    def echo_scene(result):
        print(f"\n--- Scene {result.scene.number}: {result.scene.title} ---")
        if result.success is not None:
            print(f"  [mechanical: {'OK' if result.success else 'FAIL'}]")
        print(result.narration)

    state, extras = run_heist(prompt, ai, rng=rng, on_scene=echo_scene)
    markdown = render_markdown(state, extras)
    args.out.write_text(markdown)
    print(f"\nWrote {args.out} (take: ${state.final_take:,})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
