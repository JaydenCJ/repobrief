"""Tree walking: ignore rules, binary sniffing, line counting."""

import os

from repobrief.fswalk import IgnoreRules, count_lines, sniff_binary, walk

from conftest import write


def paths(files):
    return [f.path for f in files]


def test_walk_collects_nested_files_sorted_with_stats(tmp_path):
    write(tmp_path, "b.py", "x = 1\ny = 2\n")
    write(tmp_path, "a/deep/mod.py", "y = 2\n")
    write(tmp_path, "a/first.py", "z = 3\n")
    files = walk(str(tmp_path))
    assert paths(files) == ["a/deep/mod.py", "a/first.py", "b.py"]
    top = files[-1]
    assert top.size == len("x = 1\ny = 2\n")
    assert top.language == "Python" and top.lines == 2 and not top.binary


def test_walk_skips_builtin_ignore_dirs_and_symlinks(tmp_path):
    write(tmp_path, "src/app.py", "ok\n")
    write(tmp_path, "node_modules/dep/index.js", "junk\n")
    write(tmp_path, ".git/config", "[core]\n")
    write(tmp_path, "__pycache__/app.cpython-311.pyc", "junk\n")
    os.symlink(str(tmp_path / "src" / "app.py"), str(tmp_path / "link.py"))
    assert paths(walk(str(tmp_path))) == ["src/app.py"]


def test_walk_honors_root_gitignore_patterns(tmp_path):
    write(tmp_path, ".gitignore", "generated/\n*.log\n")
    write(tmp_path, "generated/out.py", "x\n")
    write(tmp_path, "app.log", "noise\n")
    write(tmp_path, "sub/deep.log", "noise\n")  # basename globs apply at any depth
    write(tmp_path, "kept.py", "x\n")
    assert paths(walk(str(tmp_path))) == [".gitignore", "kept.py"]


def test_ignore_rules_anchoring_and_dir_only_semantics():
    rules = IgnoreRules(["/local.cfg", "build/"])
    assert rules.matches("local.cfg", is_dir=False)
    assert not rules.matches("sub/local.cfg", is_dir=False)  # anchored to root
    assert rules.matches("build", is_dir=True)
    assert not rules.matches("build", is_dir=False)  # trailing slash = dirs only


def test_ignore_rules_negation_and_comments_are_skipped_not_crashed():
    # Negation is unsupported by design: the "!keep.log" line is ignored,
    # so "*.log" still applies to everything.
    rules = IgnoreRules(["# comment", "", "!keep.log", "*.log"])
    assert rules.matches("keep.log", is_dir=False)
    assert not rules.matches("keep.txt", is_dir=False)


def test_binary_detection_via_nul_byte(tmp_path):
    binary = tmp_path / "blob.bin"
    binary.write_bytes(b"\x00\x01\x02")
    text = write(tmp_path, "ok.txt", "hello\n")
    assert sniff_binary(str(binary)) is True
    assert sniff_binary(str(text)) is False
    stats = {f.path: f for f in walk(str(tmp_path))}
    assert stats["blob.bin"].binary and stats["blob.bin"].lines == 0
    assert not stats["ok.txt"].binary and stats["ok.txt"].lines == 1


def test_count_lines_handles_missing_trailing_newline(tmp_path):
    p = tmp_path / "f.txt"
    p.write_bytes(b"a\nb")  # editor shows 2 lines
    assert count_lines(str(p)) == 2
    p.write_bytes(b"")
    assert count_lines(str(p)) == 0
    p.write_bytes(b"a\nb\n")
    assert count_lines(str(p)) == 2
