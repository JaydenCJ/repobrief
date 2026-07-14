"""The fallback TOML reader (used where tomllib is unavailable, < 3.11)."""

from repobrief.minitoml import get_path, parse


def test_top_level_and_nested_tables():
    data = parse('[package]\nname = "demo"\n\n[tool.pytest.ini_options]\naddopts = "-q"\n')
    assert data["package"]["name"] == "demo"
    assert data["tool"]["pytest"]["ini_options"]["addopts"] == "-q"


def test_array_of_tables_matches_cargo_bin_layout():
    text = '[[bin]]\nname = "alpha"\npath = "src/bin/alpha.rs"\n\n[[bin]]\nname = "beta"\n'
    data = parse(text)
    assert [b["name"] for b in data["bin"]] == ["alpha", "beta"]
    assert data["bin"][0]["path"] == "src/bin/alpha.rs"


def test_scalar_values_strings_numbers_booleans():
    data = parse(
        'a = "line\\nbreak"\nb = \'literal\\n\'\nn = 1_000\nf = 2.5\nyes = true\nno = false\n'
    )
    assert data["a"] == "line\nbreak"
    assert data["b"] == "literal\\n"  # literal strings keep backslashes
    assert data["n"] == 1000 and data["f"] == 2.5
    assert data["yes"] is True and data["no"] is False


def test_single_and_multi_line_arrays():
    text = 'tags = ["a", "b"]\ndeps = [\n  "x",\n  "y",  # trailing comment\n]\n'
    data = parse(text)
    assert data["tags"] == ["a", "b"]
    assert data["deps"] == ["x", "y"]


def test_comments_are_stripped_but_hash_in_string_survives():
    data = parse('title = "issue #42"  # the comment\n')
    assert data["title"] == "issue #42"


def test_unsupported_constructs_are_skipped_not_mangled():
    # Inline tables and dotted LHS keys are out of scope: the parser must
    # skip them silently and still read everything else correctly.
    text = 'point = { x = 1, y = 2 }\na.b = "dotted"\nname = "kept"\n'
    data = parse(text)
    assert data["name"] == "kept"
    assert "point" not in data


def test_quoted_keys_are_accepted():
    data = parse('[project.scripts]\n"my-tool" = "pkg.cli:main"\n')
    assert data["project"]["scripts"]["my-tool"] == "pkg.cli:main"


def test_get_path_walks_and_misses_safely():
    data = parse('[project]\nname = "x"\n')
    assert get_path(data, "project", "name") == "x"
    assert get_path(data, "project", "missing") is None
    assert get_path(data, "nope", "name") is None
