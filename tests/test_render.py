"""Markdown and JSON rendering."""

import json

from repobrief import Options, build, render_json, render_markdown
from repobrief.render import fmt_bytes, fmt_int, heat_bar, humanize_age
from repobrief.version import __version__

from conftest import DAY, NOW, T0, commit_all, git, requires_git, write


def test_number_and_size_formatting():
    assert fmt_int(0) == "0"
    assert fmt_int(1234567) == "1,234,567"
    assert fmt_bytes(512) == "512 B"
    assert fmt_bytes(2048) == "2.0 KiB"
    assert fmt_bytes(5 * 1024 * 1024) == "5.0 MiB"


def test_humanize_age_buckets():
    now = float(NOW)
    assert humanize_age(now, NOW) == "today"
    assert humanize_age(now, NOW - 1 * DAY) == "yesterday"
    assert humanize_age(now, NOW - 5 * DAY) == "5 days ago"
    assert humanize_age(now, NOW - 21 * DAY) == "3 weeks ago"
    assert humanize_age(now, NOW - 100 * DAY) == "3 months ago"
    assert humanize_age(now, NOW - 800 * DAY) == "2 years ago"
    assert humanize_age(now, 0) == "unknown"


def test_heat_bar_scales_relative_to_max():
    assert heat_bar(1.0, 1.0) == "█" * 8
    assert heat_bar(0.5, 1.0) == "█" * 4
    assert heat_bar(0.01, 1.0) == "█"  # tiny but nonzero stays visible
    assert heat_bar(0.0, 1.0) == ""


def test_markdown_contains_every_section(sample_repo):
    md = render_markdown(build(str(sample_repo), Options(now=float(NOW), use_git=False)))
    for heading in (
        "# Repo brief: acme-relay",
        "## Languages",
        "## Layout",
        "## Entry points",
        "## Commands",
        "## Hot files (churn-ranked)",
        "## Health",
    ):
        assert heading in md
    assert f"v{__version__}" in md


def test_markdown_no_git_message_and_health_checkboxes(sample_repo):
    md = render_markdown(build(str(sample_repo), Options(now=float(NOW), use_git=False)))
    assert "no churn history to rank" in md
    assert "- **Git:** no history available" in md
    assert "- [x] README (`README.md`)" in md
    assert "- [x] License: MIT" in md
    assert "- [ ] Changelog" in md
    assert "- [x] Tests" in md


@requires_git
def test_git_header_uses_singular_for_one_commit_one_author(tmp_path):
    # Regression: a fresh repository must read "1 commit ... 1 author in the
    # last 1 commit", never "1 commits" / "1 authors".
    root = tmp_path / "solo"
    write(root, "main.py", "print('hi')\n")
    git(root, "init", "-q", "-b", "main")
    commit_all(root, T0, "Solo Dev", "initial commit")
    md = render_markdown(build(str(root), Options(now=float(NOW))))
    assert "· 1 commit ·" in md
    assert "1 author in the last 1 commit" in md
    assert "1 commits" not in md and "1 authors" not in md


@requires_git
def test_json_roundtrips_and_is_deterministic(git_repo):
    brief = build(str(git_repo), Options(now=float(NOW)))
    data = json.loads(render_json(brief))
    assert data["name"] == "hotproj"
    assert data["repobrief_version"] == __version__
    assert data["git"]["branch"] == "main"
    assert data["hot_files"][0]["path"] == "src/hotproj/core.py"
    assert data["totals"]["files"] == brief.total_files
    # sort_keys=True means the serialization itself is deterministic.
    assert render_json(brief) == render_json(build(str(git_repo), Options(now=float(NOW))))


def test_pipe_characters_in_table_cells_are_escaped(tmp_path):
    # A pipe in a directory name would otherwise break the layout table.
    write(tmp_path, "weird|dir/mod.py", "x = 1\n")
    md = render_markdown(build(str(tmp_path), Options(now=float(NOW), use_git=False)))
    assert "`weird\\|dir/`" in md
    assert "\n| `weird|dir/`" not in md
