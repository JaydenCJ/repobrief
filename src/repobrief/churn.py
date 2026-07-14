"""Churn scoring: which files is this repository actually about, right now.

A file's heat is the sum of an exponentially-decayed contribution from every
commit that touched it: a commit today contributes 1.0, a commit one
half-life ago contributes 0.5, two half-lives ago 0.25, and so on. Recency
weighting is the whole point -- a config file hammered during a rewrite two
years ago should rank below the module edited every day this month. Raw
commit counts (what ``git effort`` and most "hot files" scripts use) get
this exactly backwards on long-lived repositories.

Scoring is a pure function of ``(commits, now)``, so tests pin ``now`` and
the ranking is fully deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Set

from .gitinfo import Commit

_SECONDS_PER_DAY = 86400.0

DEFAULT_HALF_LIFE_DAYS = 30.0


@dataclass(frozen=True)
class HotFile:
    """One churn-ranked file."""

    path: str
    commits: int
    authors: int
    last_ts: int
    score: float


def decay(age_seconds: float, half_life_days: float) -> float:
    """Weight of one touch that happened ``age_seconds`` ago."""
    if half_life_days <= 0:
        return 1.0  # degenerate config: fall back to plain commit counting
    age_days = max(0.0, age_seconds) / _SECONDS_PER_DAY
    return 0.5 ** (age_days / half_life_days)


def rank(
    commits: Iterable[Commit],
    now: float,
    half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
    existing: Optional[Set[str]] = None,
    top: int = 10,
) -> List[HotFile]:
    """Rank files by decayed churn.

    ``existing`` restricts the ranking to paths still present in the work
    tree: ``git log --name-only`` reports deleted files and pre-rename paths,
    and a hot-files table pointing a newcomer at files that no longer exist
    would be worse than useless.

    Ties break on raw commit count, then path, so equal-score files always
    appear in the same order.
    """
    scores: Dict[str, float] = {}
    counts: Dict[str, int] = {}
    authors: Dict[str, Set[str]] = {}
    last_ts: Dict[str, int] = {}

    for commit in commits:
        weight = decay(now - commit.timestamp, half_life_days)
        for path in commit.files:
            if existing is not None and path not in existing:
                continue
            scores[path] = scores.get(path, 0.0) + weight
            counts[path] = counts.get(path, 0) + 1
            authors.setdefault(path, set()).add(commit.author)
            if commit.timestamp > last_ts.get(path, 0):
                last_ts[path] = commit.timestamp

    ranked = [
        HotFile(
            path=path,
            commits=counts[path],
            authors=len(authors[path]),
            last_ts=last_ts[path],
            score=score,
        )
        for path, score in scores.items()
    ]
    ranked.sort(key=lambda h: (-h.score, -h.commits, h.path))
    return ranked[: max(0, top)]
