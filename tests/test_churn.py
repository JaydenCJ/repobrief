"""Churn scoring: exponential decay and deterministic ranking."""

from repobrief.churn import decay, rank
from repobrief.gitinfo import Commit

from conftest import DAY, NOW, T0


def commit(ts, author, *files):
    return Commit(sha="a" * 40, timestamp=ts, author=author, files=tuple(files))


def test_decay_halves_per_half_life_and_clamps_future():
    assert decay(0, 30.0) == 1.0
    assert abs(decay(30 * DAY, 30.0) - 0.5) < 1e-9
    assert abs(decay(60 * DAY, 30.0) - 0.25) < 1e-9
    # Clock skew can put a commit "in the future"; it must weigh 1.0, not >1.
    assert decay(-5 * DAY, 30.0) == 1.0


def test_recent_touches_outrank_many_old_touches():
    # THE core promise: 1 touch today beats 3 touches ~3 half-lives ago
    # (3 * 0.5^2.9 ≈ 0.40 < 1.0). Plain commit counting gets this backwards.
    commits = [
        commit(T0 - 57 * DAY, "Ana", "old.py"),
        commit(T0 - 58 * DAY, "Ana", "old.py"),
        commit(T0 - 59 * DAY, "Ana", "old.py"),
        commit(T0 + 30 * DAY, "Ana", "new.py"),
    ]
    ranked = rank(commits, now=NOW, half_life_days=30.0)
    assert [h.path for h in ranked] == ["new.py", "old.py"]
    assert ranked[1].commits == 3  # raw count is still reported honestly


def test_rank_filters_to_existing_files():
    commits = [commit(T0, "Ana", "kept.py", "deleted.py")]
    ranked = rank(commits, now=NOW, existing={"kept.py"})
    assert [h.path for h in ranked] == ["kept.py"]


def test_rank_counts_distinct_authors_and_last_touch():
    commits = [
        commit(T0, "Ana", "app.py"),
        commit(T0 + 5 * DAY, "Bo", "app.py"),
        commit(T0 + 9 * DAY, "Ana", "app.py"),
    ]
    (hot,) = rank(commits, now=NOW)
    assert hot.commits == 3 and hot.authors == 2
    assert hot.last_ts == T0 + 9 * DAY


def test_rank_tie_breaks_on_commits_then_path():
    same_ts = T0 + 10 * DAY
    commits = [
        commit(same_ts, "Ana", "b.py", "a.py"),  # both files: same score, same count
        commit(same_ts, "Ana", "z.py"),
        commit(same_ts, "Ana", "z.py"),  # more commits -> ahead despite name
    ]
    ranked = rank(commits, now=NOW)
    assert [h.path for h in ranked] == ["z.py", "a.py", "b.py"]


def test_rank_respects_top_limit():
    commits = [commit(T0 + i * DAY, "Ana", f"f{i}.py") for i in range(6)]
    assert len(rank(commits, now=NOW, top=3)) == 3
    assert rank(commits, now=NOW, top=0) == []
