"""Layout grouping and directory-purpose labeling."""

from repobrief.fswalk import walk
from repobrief.layout import ROOT_LABEL, build_layout, purpose_for

from conftest import write


def entries_by_path(entries):
    return {e.path: e for e in entries}


def test_root_files_group_first_under_root_label(sample_repo):
    entries = build_layout(walk(str(sample_repo)))
    assert entries[0].path == ROOT_LABEL
    assert entries[0].files >= 4  # package.json, Makefile, README, LICENSE, .gitignore


def test_conventional_directories_get_purpose_labels(sample_repo):
    by_path = entries_by_path(build_layout(walk(str(sample_repo))))
    assert by_path["src"].purpose == "Source code"
    assert by_path["tests"].purpose == "Tests"
    assert by_path["docs"].purpose == "Documentation"
    assert by_path["scripts"].purpose == "Scripts / tooling"


def test_depth_caps_directory_granularity(tmp_path):
    write(tmp_path, "src/pkg/sub/deep.py", "x\n")
    shallow = entries_by_path(build_layout(walk(str(tmp_path)), depth=1))
    deep = entries_by_path(build_layout(walk(str(tmp_path)), depth=3))
    assert "src" in shallow and "src/pkg/sub" not in shallow
    assert "src/pkg/sub" in deep


def test_main_language_is_dominant_by_lines(sample_repo):
    by_path = entries_by_path(build_layout(walk(str(sample_repo))))
    # src/ holds 5 lines of JS vs 2 of Python in the fixture.
    assert by_path["src"].main_language == "JavaScript"


def test_purpose_rules_deepest_segment_then_language_fallback():
    # src/tests is about the tests, not the source.
    assert purpose_for("src/tests", "Python", "code") == "Tests"
    assert purpose_for("wrangler", "Go", "code") == "Go code"
    assert purpose_for("wrangler", "YAML", "config") == "YAML files"
    assert purpose_for("wrangler", None, None) == "Files"


def test_binary_files_count_but_add_no_lines(tmp_path):
    write(tmp_path, "assets/app.py", "x = 1\n")
    (tmp_path / "assets" / "logo.bin").write_bytes(b"\x00\x01")
    by_path = entries_by_path(build_layout(walk(str(tmp_path))))
    assert by_path["assets"].files == 2
    assert by_path["assets"].lines == 1
