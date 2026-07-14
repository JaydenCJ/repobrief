"""Git log parsing (pure) and history collection (against real fixtures)."""

from repobrief.gitinfo import collect, is_git_repo, parse_log

from conftest import DAY, T0, requires_git

SAMPLE_LOG = (
    "1111111111111111111111111111111111111111\t1700000000\tAna Dev\n"
    "src/app.py\n"
    "README.md\n"
    "\n"
    "2222222222222222222222222222222222222222\t1700086400\tBo Smith\n"
    "src/app.py\n"
)


def test_parse_log_two_commits_with_files():
    commits = parse_log(SAMPLE_LOG)
    assert len(commits) == 2
    first, second = commits
    assert first.sha.startswith("1111") and first.timestamp == 1700000000
    assert first.author == "Ana Dev"
    assert first.files == ("src/app.py", "README.md")
    assert second.files == ("src/app.py",)


def test_parse_log_edge_cases():
    assert parse_log("") == []
    # File-looking lines before any header are noise, not commits.
    assert parse_log("orphan.py\nanother.py\n") == []
    # --allow-empty commits produce a header with no file list.
    (empty,) = parse_log("3333333333333333333333333333333333333333\t1700000000\tAna Dev\n")
    assert empty.files == ()
    # Unicode and spaces in paths must survive (core.quotepath=false output).
    (uni,) = parse_log(
        "4444444444444444444444444444444444444444\t1700000000\tAna Dev\ndocs/読み方.md\nsrc/my file.py\n"
    )
    assert uni.files == ("docs/読み方.md", "src/my file.py")


@requires_git
def test_is_git_repo_and_collect_on_plain_dirs(git_repo, tmp_path):
    assert is_git_repo(str(git_repo)) is True
    plain = tmp_path / "plain"
    plain.mkdir()
    assert is_git_repo(str(plain)) is False
    assert collect(str(plain)) is None


@requires_git
def test_collect_summary_matches_fixture_history(git_repo):
    result = collect(str(git_repo))
    assert result is not None
    summary, _ = result
    assert summary.branch == "main"
    assert summary.total_commits == 3
    assert summary.scanned_commits == 3
    assert summary.authors == 2  # Ana Dev + Bo Smith
    assert summary.last_commit_ts == T0 + 25 * DAY


@requires_git
def test_collect_commits_carry_pinned_timestamps_and_files(git_repo):
    _, commits = collect(str(git_repo))
    # git log is newest-first.
    assert [c.timestamp for c in commits] == [T0 + 25 * DAY, T0 + 10 * DAY, T0]
    assert commits[0].files == ("src/hotproj/core.py",)
    assert set(commits[1].files) == {"src/hotproj/core.py", "src/hotproj/cli.py"}


@requires_git
def test_collect_respects_max_commits_window(git_repo):
    summary, commits = collect(str(git_repo), max_commits=2)
    assert len(commits) == 2
    assert commits[0].timestamp == T0 + 25 * DAY  # newest kept
    assert summary.total_commits == 3  # full depth still reported honestly
