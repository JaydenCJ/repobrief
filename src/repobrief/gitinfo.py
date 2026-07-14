"""Git history collection and log parsing.

repobrief shells out to the ``git`` binary instead of re-implementing the
object store: every machine that has the repository cloned has git, and the
plumbing output formats are stable. All parsing lives in pure functions
(:func:`parse_log`) so the history pipeline is unit-testable without a
repository, and every subprocess runs with ``LC_ALL=C`` so output never
depends on the host locale.

Everything degrades gracefully: no git binary, not a work tree, or an empty
repository all yield ``None`` rather than an error -- a brief for a plain
directory is still useful, it just has no "hot files" section.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from typing import List, Optional, Tuple

_HEADER_RE = re.compile(r"^([0-9a-f]{7,40})\t(\d+)\t(.*)$")

#: pretty format for the churn scan: sha TAB unix-timestamp TAB author-name
LOG_FORMAT = "%H%x09%ct%x09%an"


@dataclass(frozen=True)
class Commit:
    """One parsed commit: metadata plus the files it touched."""

    sha: str
    timestamp: int
    author: str
    files: Tuple[str, ...]


@dataclass(frozen=True)
class GitSummary:
    """Headline repository facts for the brief header."""

    branch: str
    total_commits: int
    last_commit_ts: int
    scanned_commits: int  # how many commits fed the churn ranking
    authors: int  # distinct authors within the scanned window


def _run_git(root: str, *args: str) -> Optional[str]:
    """Run a git subcommand in ``root``; None on any failure."""
    env = dict(os.environ, LC_ALL="C", LANG="C", GIT_OPTIONAL_LOCKS="0")
    try:
        proc = subprocess.run(
            ["git", "-c", "core.quotepath=false", *args],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def is_git_repo(root: str) -> bool:
    """True when ``root`` sits inside a git work tree."""
    out = _run_git(root, "rev-parse", "--is-inside-work-tree")
    return out is not None and out.strip() == "true"


def parse_log(text: str) -> List[Commit]:
    """Parse ``git log --pretty=format:<LOG_FORMAT> --name-only`` output.

    The format interleaves header lines (``sha TAB ts TAB author``) with the
    touched file paths, separated by blank lines. Author names may contain
    tabs in pathological configs, so the header regex captures the rest of
    the line greedily. Unrecognized lines before the first header are
    ignored, which makes the parser robust to leading noise.
    """
    commits: List[Commit] = []
    sha = author = None
    ts = 0
    files: List[str] = []

    def flush() -> None:
        nonlocal sha
        if sha is not None:
            commits.append(Commit(sha=sha, timestamp=ts, author=author or "", files=tuple(files)))
        sha = None
        del files[:]

    for line in text.splitlines():
        m = _HEADER_RE.match(line)
        if m:
            flush()
            sha, ts, author = m.group(1), int(m.group(2)), m.group(3)
        elif line.strip() and sha is not None:
            files.append(line.strip())
    flush()
    return commits


def collect(root: str, max_commits: int = 400) -> Optional[Tuple[GitSummary, List[Commit]]]:
    """Gather a :class:`GitSummary` plus the recent commits for churn ranking.

    ``max_commits`` bounds the scan so briefs stay fast on decade-old
    monorepos; churn is about *recent* activity anyway. Merge commits are
    excluded -- they touch every file of the merged branch and would drown
    the signal.
    """
    if not is_git_repo(root):
        return None

    branch_out = _run_git(root, "rev-parse", "--abbrev-ref", "HEAD")
    count_out = _run_git(root, "rev-list", "--count", "HEAD")
    if branch_out is None or count_out is None:
        return None  # e.g. a freshly-initialized repository with no commits

    log_out = _run_git(
        root,
        "log",
        "--no-merges",
        f"--pretty=format:{LOG_FORMAT}",
        "--name-only",
        "-n",
        str(max_commits),
    )
    commits = parse_log(log_out or "")

    last_ts = 0
    all_ts_out = _run_git(root, "log", "-1", "--pretty=%ct")
    if all_ts_out and all_ts_out.strip().isdigit():
        last_ts = int(all_ts_out.strip())
    elif commits:
        last_ts = max(c.timestamp for c in commits)

    try:
        total = int(count_out.strip())
    except ValueError:
        total = len(commits)

    summary = GitSummary(
        branch=branch_out.strip() or "HEAD",
        total_commits=total,
        last_commit_ts=last_ts,
        scanned_commits=len(commits),
        authors=len({c.author for c in commits}),
    )
    return summary, commits
