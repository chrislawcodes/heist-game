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
    if agent == "codex":
        from heist.backends import CodexHeistAI
        return CodexHeistAI()
    if agent == "gemini":
        from heist.backends import GeminiHeistAI
        return GeminiHeistAI()
    raise SystemExit(f"unknown agent {agent!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="heist")
    subparsers = parser.add_subparsers(dest="command")

    # serve subcommand
    serve_p = subparsers.add_parser("serve", help="Start the live viewer server.")
    serve_p.add_argument("--port", type=int, default=8000)

    # run subcommand (default behaviour)
    run_p = subparsers.add_parser("run", help="Run a heist and write a markdown report.")
    run_p.add_argument("--prompt-file", type=Path, default=None)
    run_p.add_argument("--out", type=Path, default=Path("heist_report.md"))
    run_p.add_argument("--seed", type=int, default=None)
    run_p.add_argument("--agent", default="stub", choices=["stub", "codex", "gemini"])

    # backwards-compat: bare flags with no subcommand → treat as `run`
    parser.add_argument("--prompt-file", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=Path("heist_report.md"))
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--agent", default="stub", choices=["stub", "codex", "gemini"])

    args = parser.parse_args(argv)

    if args.command == "serve":
        from heist.server import serve
        serve(port=args.port)
        return 0

    # run (subcommand or bare)
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
