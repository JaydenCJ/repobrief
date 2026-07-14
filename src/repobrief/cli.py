"""The ``repobrief`` command-line interface.

One command, one job: point it at a directory, get a brief on stdout (or into
a file with ``--out``). Exit codes follow CLI convention: 0 on success, 2 for
usage errors such as a nonexistent path.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional

from .brief import Options, build
from .render import render_json, render_markdown
from .version import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="repobrief",
        description=(
            "Generate a one-page orientation brief for a repository: layout, "
            "churn-ranked hot files, entry points, and runnable commands."
        ),
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="repository root to analyze (default: current directory)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the brief as JSON instead of markdown",
    )
    parser.add_argument(
        "-o",
        "--out",
        metavar="FILE",
        help="write the brief to FILE instead of stdout",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=10,
        metavar="N",
        help="number of hot files to rank (default: 10)",
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=2,
        metavar="N",
        help="directory depth of the layout table (default: 2)",
    )
    parser.add_argument(
        "--max-commits",
        type=int,
        default=400,
        metavar="N",
        help="how many recent commits feed the churn ranking (default: 400)",
    )
    parser.add_argument(
        "--half-life",
        type=float,
        default=30.0,
        metavar="DAYS",
        help="churn decay half-life in days; smaller favors recent work (default: 30)",
    )
    parser.add_argument(
        "--no-git",
        action="store_true",
        help="skip git entirely (no history header, no hot files)",
    )
    parser.add_argument(
        "--now",
        type=int,
        default=None,
        metavar="EPOCH",
        help="pin 'now' to a unix timestamp for reproducible output (used by tests)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"repobrief {__version__}",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    root = args.path
    if not os.path.isdir(root):
        print(f"repobrief: error: not a directory: {root}", file=sys.stderr)
        return 2
    for flag, value, minimum in (
        ("--top", args.top, 0),
        ("--depth", args.depth, 1),
        ("--max-commits", args.max_commits, 1),
    ):
        if value < minimum:
            print(
                f"repobrief: error: {flag} is out of range: got {value}, minimum is {minimum}",
                file=sys.stderr,
            )
            return 2

    options = Options(
        top=args.top,
        depth=args.depth,
        use_git=not args.no_git,
        now=float(args.now) if args.now is not None else None,
        max_commits=args.max_commits,
        half_life_days=args.half_life,
    )
    brief = build(root, options)
    text = render_json(brief) if args.json else render_markdown(brief)

    if args.out:
        try:
            with open(args.out, "w", encoding="utf-8") as fh:
                fh.write(text)
        except OSError as exc:
            print(f"repobrief: error: cannot write {args.out}: {exc}", file=sys.stderr)
            return 2
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
