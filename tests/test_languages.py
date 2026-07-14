"""Language detection and per-language breakdown."""

from repobrief.fswalk import FileStat
from repobrief.languages import CODE, DOCS, breakdown, detect, primary_language


def stat(path, lines, binary=False):
    lang, cat = detect(path)
    return FileStat(path=path, size=lines * 10, lines=lines, binary=binary, language=lang, category=cat)


def test_detect_maps_common_extensions():
    assert detect("src/app.py") == ("Python", CODE)
    assert detect("web/index.tsx") == ("TypeScript", CODE)
    assert detect("cmd/main.go") == ("Go", CODE)
    assert detect("lib.rs") == ("Rust", CODE)
    assert detect("styles/site.scss")[0] == "CSS"


def test_detect_special_filenames_and_dotfiles():
    # No extension, but the basename itself is the signal.
    assert detect("Makefile")[0] == "Makefile"
    assert detect("deploy/Dockerfile")[0] == "Dockerfile"
    assert detect("LICENSE") == ("Text", DOCS)
    # ".gitignore" must hit the filename map, not parse as extension "gitignore".
    assert detect(".gitignore")[0] == "Gitignore"


def test_detect_edge_cases():
    # Windows-born repos often carry uppercase extensions.
    assert detect("legacy/OLD.PY") == ("Python", CODE)
    assert detect("data/blob.xyzzy")[0] == "Other"
    assert detect("no_extension_at_all")[0] == "Other"


def test_breakdown_percentages_sum_to_100():
    shares = breakdown([stat("a.py", 60), stat("b.js", 30), stat("c.md", 10)])
    assert abs(sum(s.percent for s in shares) - 100.0) < 1e-9
    assert shares[0].name == "Python" and shares[0].percent == 60.0


def test_breakdown_excludes_binaries_and_orders_ties_by_name():
    shares = breakdown([stat("b.js", 10), stat("a.py", 10), stat("img.png", 999, binary=True)])
    # Binary lines are meaningless; equal line counts sort alphabetically.
    assert [s.name for s in shares] == ["JavaScript", "Python"]
    assert all(s.files == 1 for s in shares)


def test_primary_language_prefers_code_and_handles_empty():
    # A huge changelog must not make the project "a Markdown project".
    shares = breakdown([stat("CHANGELOG.md", 5000), stat("core.py", 100)])
    primary = primary_language(shares)
    assert primary is not None and primary.name == "Python"
    assert primary_language(breakdown([])) is None
