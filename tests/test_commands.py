"""Command extraction from manifests, Makefiles, justfiles, and scripts/."""

from repobrief.commands import find_commands, parse_justfile, parse_makefile
from repobrief.fswalk import walk
from repobrief.manifest import load

from conftest import write


def find(root):
    files = {f.path for f in walk(str(root))}
    return find_commands(str(root), files, load(str(root)))


def test_npm_scripts_use_run_except_start_and_test(sample_repo):
    cmds = {c.name: c for c in find(sample_repo) if c.source == "package.json"}
    assert cmds["start"].run == "npm start"
    assert cmds["test"].run == "npm test"
    assert cmds["lint"].run == "npm run lint"
    assert cmds["lint"].description == "eslint ."


def test_makefile_descriptions_from_double_hash_and_preceding_comment():
    cmds = parse_makefile(
        [
            "build: ## compile the thing",
            "\tgcc -o out main.c",
            "# rebuild everything from scratch",
            "all: build test",
            "\techo done",
        ]
    )
    assert [(c.name, c.description) for c in cmds] == [
        ("build", "compile the thing"),
        ("all", "rebuild everything from scratch"),
    ]
    assert cmds[0].run == "make build"


def test_makefile_skips_specials_patterns_assignments_and_recipes():
    lines = [
        ".PHONY: build test",
        "%.o: %.c",
        "\tcc -c $<",
        "CFLAGS := -O2",
        "VERSION = 1.0",
        "$(TARGET): deps",
        "deploy:",
        "\tscp out host:",  # recipe line with a colon must not become a target
    ]
    assert [c.name for c in parse_makefile(lines)] == ["deploy"]


def test_justfile_recipes_with_comments_and_settings():
    lines = [
        'set shell := ["bash", "-c"]',
        "version := '1.0'",
        "# run the local server",
        "serve port:",
        "    server --port {{port}}",
        "lint:",
        "    ruff check .",
    ]
    cmds = parse_justfile(lines)
    assert [(c.name, c.run) for c in cmds] == [("serve", "just serve"), ("lint", "just lint")]
    assert cmds[0].description == "run the local server"


def test_scripts_directory_shell_files_with_first_comment(sample_repo):
    (cmd,) = [c for c in find(sample_repo) if c.source == "scripts/"]
    assert cmd.run == "bash scripts/deploy.sh"
    assert cmd.description == "Deploy to the staging box"


def test_inferred_toolchain_commands(tmp_path):
    write(tmp_path, "Cargo.toml", '[package]\nname = "r"\n')
    write(tmp_path, "go.mod", "module example.test/g\n")
    runs = {c.run for c in find(tmp_path) if c.source == "inferred"}
    assert runs == {"cargo build", "cargo test", "go build ./...", "go test ./..."}


def test_pytest_inferred_only_with_tests_signal(tmp_path):
    write(tmp_path, "pyproject.toml", '[project]\nname = "p"\n')
    assert all(c.run != "pytest" for c in find(tmp_path))
    write(tmp_path, "tests/test_x.py", "def test_a(): pass\n")
    assert any(c.run == "pytest" for c in find(tmp_path))


def test_deduplication_collapses_identical_run_strings(tmp_path):
    # `npm test` from package.json and `make test` differ (both kept), but a
    # second source producing the SAME run string collapses to the first.
    write(tmp_path, "package.json", '{"name": "x", "scripts": {"test": "vitest run"}}')
    write(tmp_path, "Makefile", "test:\n\tnpm test\n")
    cmds = [c for c in find(tmp_path) if c.name == "test"]
    assert [(c.run, c.source) for c in cmds] == [
        ("npm test", "package.json"),
        ("make test", "Makefile"),
    ]


def test_long_descriptions_are_truncated_with_ellipsis(tmp_path):
    body = "x" * 200
    write(tmp_path, "package.json", '{"name": "x", "scripts": {"gen": "%s"}}' % body)
    (cmd,) = [c for c in find(tmp_path) if c.name == "gen"]
    assert len(cmd.description) <= 72 and cmd.description.endswith("…")
