"""Command extraction: what can you actually run here.

Collects the repository's runnable commands from the places developers
declare them -- ``package.json`` scripts, ``Makefile`` targets, ``justfile``
recipes, shell scripts under ``scripts/`` -- plus the standard toolchain
commands implied by the manifests present (``cargo test``, ``go test ./...``,
``pytest``). Each command keeps its source and, when the author wrote one, a
one-line description, so the brief's command table doubles as a tiny task
runner cheat sheet.

Parsers are line-based and intentionally conservative: a target we cannot
classify is dropped, never mangled.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import List, Optional, Set

from .manifest import Manifests
from .minitoml import get_path

_MAKE_TARGET_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9_./-]*)\s*::?\s*([^=].*)?$")
_JUST_RECIPE_RE = re.compile(r"^(@?)([A-Za-z_][A-Za-z0-9_-]*)(\s+[A-Za-z_][^:=]*)?:(?!=)(.*)$")
_MAX_DESC = 72


@dataclass(frozen=True)
class Command:
    """One runnable command with its provenance."""

    name: str
    run: str  # what to type
    source: str  # package.json / Makefile / justfile / scripts/ / inferred
    description: str  # may be empty


def _truncate(text: str) -> str:
    text = " ".join(text.split())
    if len(text) > _MAX_DESC:
        return text[: _MAX_DESC - 1].rstrip() + "…"
    return text


def _read_lines(root: str, rel: str) -> Optional[List[str]]:
    try:
        with open(os.path.join(root, rel), "r", encoding="utf-8", errors="replace") as fh:
            return fh.read().splitlines()
    except OSError:
        return None


def npm_commands(manifests: Manifests) -> List[Command]:
    scripts = (manifests.package_json or {}).get("scripts")
    if not isinstance(scripts, dict):
        return []
    out: List[Command] = []
    for name in sorted(scripts):
        body = scripts[name]
        if not isinstance(body, str):
            continue
        run = f"npm run {name}" if name not in ("start", "test") else f"npm {name}"
        out.append(Command(name=name, run=run, source="package.json", description=_truncate(body)))
    return out


def parse_makefile(lines: List[str]) -> List[Command]:
    """Extract targets from Makefile text.

    Skips special targets (leading ``.``), pattern rules (``%``), targets
    computed from variables (``$``), and variable assignments (``FOO := x``,
    which the regex rejects because the part after ``:`` starts with ``=``).
    A description is taken from a same-line ``## comment`` (the widespread
    self-documenting-Makefile convention) or the ``#`` comment line directly
    above the target.
    """
    out: List[Command] = []
    seen: Set[str] = set()
    prev_comment = ""
    for line in lines:
        stripped = line.rstrip()
        if stripped.startswith("#"):
            prev_comment = stripped.lstrip("#").strip()
            continue
        m = _MAKE_TARGET_RE.match(stripped)
        if not m or line[:1] in (" ", "\t"):
            if stripped:
                prev_comment = ""
            continue
        target, rest = m.group(1), m.group(2) or ""
        if "%" in target or "$" in target or target in seen:
            prev_comment = ""
            continue
        desc = ""
        if "##" in rest:
            desc = rest.split("##", 1)[1].strip()
        elif prev_comment:
            desc = prev_comment
        seen.add(target)
        out.append(
            Command(name=target, run=f"make {target}", source="Makefile", description=_truncate(desc))
        )
        prev_comment = ""
    return out


def make_commands(root: str) -> List[Command]:
    for name in ("Makefile", "makefile", "GNUmakefile"):
        lines = _read_lines(root, name)
        if lines is not None:
            return parse_makefile(lines)
    return []


def parse_justfile(lines: List[str]) -> List[Command]:
    """Extract recipes from justfile text (same conventions as Makefiles)."""
    out: List[Command] = []
    seen: Set[str] = set()
    prev_comment = ""
    for line in lines:
        stripped = line.rstrip()
        if stripped.startswith("#"):
            prev_comment = stripped.lstrip("#").strip()
            continue
        if line[:1] in (" ", "\t") or ":=" in stripped.split("#")[0]:
            if stripped:
                prev_comment = ""
            continue
        m = _JUST_RECIPE_RE.match(stripped)
        if not m:
            if stripped:
                prev_comment = ""
            continue
        name = m.group(2)
        if name in seen or name in ("set", "import", "export", "alias", "mod"):
            prev_comment = ""
            continue
        seen.add(name)
        out.append(
            Command(name=name, run=f"just {name}", source="justfile", description=_truncate(prev_comment))
        )
        prev_comment = ""
    return out


def just_commands(root: str) -> List[Command]:
    for name in ("justfile", "Justfile", ".justfile"):
        lines = _read_lines(root, name)
        if lines is not None:
            return parse_justfile(lines)
    return []


def script_commands(root: str, files: Set[str]) -> List[Command]:
    """Shell scripts under ``scripts/``: run hint plus first comment line."""
    out: List[Command] = []
    for rel in sorted(files):
        if not rel.startswith("scripts/") or not rel.endswith(".sh") or rel.count("/") != 1:
            continue
        desc = ""
        lines = _read_lines(root, rel) or []
        for line in lines[:10]:
            line = line.strip()
            if line.startswith("#!"):
                continue
            if line.startswith("#"):
                desc = line.lstrip("#").strip()
                break
            if line:
                break
        name = rel.rsplit("/", 1)[-1]
        out.append(
            Command(name=name, run=f"bash {rel}", source="scripts/", description=_truncate(desc))
        )
    return out


def inferred_commands(root: str, files: Set[str], manifests: Manifests) -> List[Command]:
    """Toolchain commands the manifests imply but nobody had to declare."""
    out: List[Command] = []
    if manifests.cargo is not None:
        out.append(Command("build", "cargo build", "inferred", "Compile the Rust workspace"))
        out.append(Command("test", "cargo test", "inferred", "Run the Rust test suite"))
    if manifests.gomod_module is not None:
        out.append(Command("build", "go build ./...", "inferred", "Compile all Go packages"))
        out.append(Command("test", "go test ./...", "inferred", "Run the Go test suite"))
    if manifests.pyproject is not None:
        has_pytest_cfg = get_path(manifests.pyproject, "tool", "pytest") is not None
        has_tests_dir = any(f.startswith("tests/") for f in files)
        if has_pytest_cfg or has_tests_dir:
            out.append(Command("test", "pytest", "inferred", "Run the Python test suite"))
    return out


def find_commands(root: str, files: Set[str], manifests: Manifests) -> List[Command]:
    """All commands, deduplicated by what they run, in source order.

    Declared commands win over inferred ones: if ``package.json`` already has
    a ``test`` script there is no point suggesting a second test command.
    """
    combined = (
        npm_commands(manifests)
        + make_commands(root)
        + just_commands(root)
        + script_commands(root, files)
        + inferred_commands(root, files, manifests)
    )
    seen: Set[str] = set()
    out: List[Command] = []
    for cmd in combined:
        if cmd.run in seen:
            continue
        seen.add(cmd.run)
        out.append(cmd)
    return out
