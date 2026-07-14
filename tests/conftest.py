"""Shared fixtures: synthetic repositories with fully pinned git history.

Every timestamp is a fixed epoch in the past and every churn ranking pins
``now``, so the suite is deterministic regardless of wall clock, locale, or
machine. Nothing here touches the network.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

GIT = shutil.which("git")

#: 2023-11-14T22:13:20Z — an arbitrary but fixed anchor for all history.
T0 = 1_700_000_000
DAY = 86_400
#: "now" used by churn tests: 30 days after the anchor commit.
NOW = T0 + 30 * DAY

requires_git = pytest.mark.skipif(GIT is None, reason="git binary not available")


def write(root: Path, rel: str, content: str = "") -> Path:
    """Create a file (and parents) under ``root``; returns its path."""
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def git(root: Path, *args: str) -> str:
    """Run git in ``root`` with a locale-free, sign-free environment."""
    env = dict(
        os.environ,
        LC_ALL="C",
        GIT_CONFIG_GLOBAL="/dev/null",
        GIT_CONFIG_SYSTEM="/dev/null",
    )
    proc = subprocess.run(
        ["git", *args], cwd=str(root), env=env, capture_output=True, text=True, check=True
    )
    return proc.stdout


def commit_all(root: Path, ts: int, author: str, message: str) -> None:
    """Stage everything and commit with a pinned author/committer date."""
    env = dict(
        os.environ,
        LC_ALL="C",
        GIT_CONFIG_GLOBAL="/dev/null",
        GIT_CONFIG_SYSTEM="/dev/null",
        GIT_AUTHOR_DATE=f"{ts} +0000",
        GIT_COMMITTER_DATE=f"{ts} +0000",
        GIT_AUTHOR_NAME=author,
        GIT_AUTHOR_EMAIL=f"{author.replace(' ', '.').lower()}@example.test",
        GIT_COMMITTER_NAME=author,
        GIT_COMMITTER_EMAIL=f"{author.replace(' ', '.').lower()}@example.test",
    )
    subprocess.run(["git", "add", "-A"], cwd=str(root), env=env, capture_output=True, check=True)
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "commit", "-m", message],
        cwd=str(root),
        env=env,
        capture_output=True,
        check=True,
    )


@pytest.fixture
def sample_repo(tmp_path: Path) -> Path:
    """A small polyglot project WITHOUT git history."""
    root = tmp_path / "acme-relay"
    write(
        root,
        "package.json",
        '{"name": "acme-relay", "version": "1.2.0",\n'
        ' "description": "Tiny webhook relay for example.test",\n'
        ' "main": "src/server.js",\n'
        ' "scripts": {"start": "node src/server.js", "test": "node --test",\n'
        '             "lint": "eslint ."}}\n',
    )
    write(root, "src/server.js", 'const http = require("http");\n// listens on 127.0.0.1\n')
    write(root, "src/routes.js", "function a() {}\nfunction b() {}\nfunction c() {}\n")
    write(root, "src/util.py", "def helper():\n    return 1\n")
    write(root, "tests/server.test.js", 'test("ok", () => {});\n')
    write(root, "docs/api.md", "# API\n\nSee src/server.js.\n")
    write(root, "scripts/deploy.sh", "#!/usr/bin/env bash\n# Deploy to the staging box\necho hi\n")
    write(root, "Makefile", "# build things\nbuild: ## compile everything\n\techo b\n\nclean:\n\trm -rf out\n")
    write(root, "README.md", "# acme-relay\n\nHello.\n")
    write(root, "LICENSE", "MIT License\n\nCopyright (c) 2026 Acme\n")
    write(root, ".gitignore", "*.log\ndist/\n")
    return root


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """A python-ish project WITH three commits at pinned dates.

    History (all relative to T0):
      - T0        Ana Dev:  initial import (all files)
      - T0 + 10d  Bo Smith: touch core.py and cli.py
      - T0 + 25d  Ana Dev:  touch core.py only  -> core.py is hottest
    """
    if GIT is None:  # pragma: no cover - exercised only where git is missing
        pytest.skip("git binary not available")
    root = tmp_path / "hotproj"
    write(
        root,
        "pyproject.toml",
        "[project]\n"
        'name = "hotproj"\n'
        'version = "0.3.0"\n'
        'description = "History fixture project"\n'
        "\n"
        "[project.scripts]\n"
        'hotproj = "hotproj.cli:main"\n',
    )
    write(root, "src/hotproj/__init__.py", "VERSION = '0.3.0'\n")
    write(root, "src/hotproj/__main__.py", "print('hotproj')\n")
    write(root, "src/hotproj/core.py", "def run():\n    return 'ok'\n")
    write(root, "src/hotproj/cli.py", "def main():\n    return 0\n")
    write(root, "tests/test_core.py", "def test_ok():\n    assert True\n")
    write(root, "README.md", "# hotproj\n")
    git(root, "init", "-q", "-b", "main")
    commit_all(root, T0, "Ana Dev", "initial import")

    write(root, "src/hotproj/core.py", "def run():\n    return 'ok2'\n")
    write(root, "src/hotproj/cli.py", "def main():\n    return 1\n")
    commit_all(root, T0 + 10 * DAY, "Bo Smith", "rework core and cli")

    write(root, "src/hotproj/core.py", "def run():\n    return 'ok3'\n")
    commit_all(root, T0 + 25 * DAY, "Ana Dev", "fix core edge case")
    return root
