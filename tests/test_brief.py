"""End-to-end brief assembly through the public build() pipeline."""

from repobrief import Options, build, walk

from conftest import DAY, NOW, T0, requires_git


@requires_git
def test_full_brief_on_git_fixture(git_repo):
    brief = build(str(git_repo), Options(now=float(NOW)))
    assert brief.name == "hotproj"
    assert brief.description == "History fixture project"
    assert brief.primary_language and brief.primary_language.name == "Python"
    assert brief.git and brief.git.total_commits == 3
    # core.py: touched at T0, T0+10d, T0+25d -> highest decayed score.
    assert brief.hot_files[0].path == "src/hotproj/core.py"
    assert brief.hot_files[0].commits == 3
    assert brief.hot_files[0].last_ts == T0 + 25 * DAY
    # Options.top caps the ranking.
    assert len(build(str(git_repo), Options(now=float(NOW), top=1)).hot_files) == 1


@requires_git
def test_hot_files_never_point_at_deleted_paths(git_repo):
    (git_repo / "README.md").unlink()  # deleted after being committed
    brief = build(str(git_repo), Options(now=float(NOW)))
    assert brief.hot_files  # ranking still works
    assert all(h.path != "README.md" for h in brief.hot_files)


@requires_git
def test_use_git_false_skips_history_entirely(git_repo):
    brief = build(str(git_repo), Options(now=float(NOW), use_git=False))
    assert brief.git is None and brief.hot_files == []


def test_totals_layout_entrypoints_and_commands_all_flow_in(sample_repo):
    brief = build(str(sample_repo), Options(now=float(NOW), use_git=False))
    assert brief.total_files == len(walk(str(sample_repo)))
    assert brief.total_lines > 0 and brief.total_bytes > 0
    assert sum(e.files for e in brief.layout) == brief.total_files
    assert any(ep.run == "node src/server.js" for ep in brief.entry_points)
    assert any(c.run == "make build" for c in brief.commands)
    assert any(c.run == "bash scripts/deploy.sh" for c in brief.commands)


def test_build_is_deterministic_for_pinned_now(sample_repo):
    a = build(str(sample_repo), Options(now=float(NOW), use_git=False))
    b = build(str(sample_repo), Options(now=float(NOW), use_git=False))
    assert a.to_dict() == b.to_dict()
