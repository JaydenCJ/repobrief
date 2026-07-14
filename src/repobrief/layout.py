"""Annotated layout: turn a flat file list into an oriented directory map.

A raw ``tree`` dump tells a newcomer nothing; the questions that matter are
"where is the source", "where are the tests", "what can I ignore". This
module groups the walked files by directory (down to a configurable depth)
and attaches a purpose label to each group -- from a curated table of
conventional directory names first, falling back to the dominant language
when the name carries no signal.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from .fswalk import FileStat
from .languages import CODE

ROOT_LABEL = "(root)"

#: conventional directory basename -> what it almost always means
PURPOSE_MAP: Dict[str, str] = {
    "src": "Source code",
    "lib": "Library code",
    "app": "Application code",
    "apps": "Application code",
    "core": "Core logic",
    "test": "Tests",
    "tests": "Tests",
    "spec": "Tests",
    "__tests__": "Tests",
    "e2e": "End-to-end tests",
    "docs": "Documentation",
    "doc": "Documentation",
    "examples": "Examples",
    "example": "Examples",
    "demo": "Examples",
    "scripts": "Scripts / tooling",
    "script": "Scripts / tooling",
    "bin": "Executable scripts",
    "tools": "Developer tools",
    "cmd": "Command entry points (Go layout)",
    "internal": "Internal packages (Go layout)",
    "pkg": "Library packages (Go layout)",
    "assets": "Static assets",
    "static": "Static assets",
    "public": "Static assets",
    "images": "Static assets",
    "config": "Configuration",
    "configs": "Configuration",
    "conf": "Configuration",
    "etc": "Configuration",
    "migrations": "Database migrations",
    "benchmarks": "Benchmarks",
    "bench": "Benchmarks",
    "benches": "Benchmarks",
    "ui": "Frontend / UI",
    "web": "Frontend / UI",
    "frontend": "Frontend / UI",
    "client": "Frontend / UI",
    "server": "Backend / server",
    "backend": "Backend / server",
    "api": "API layer",
    "proto": "Protocol definitions",
    "schemas": "Schemas",
    "fixtures": "Test fixtures",
    "testdata": "Test fixtures",
    "data": "Data files",
    "locales": "Translations",
    "i18n": "Translations",
    ".github": "CI / repository meta",
    "deploy": "Deployment",
    "deployments": "Deployment",
    "infra": "Infrastructure",
    "charts": "Helm charts",
    "types": "Type definitions",
}


@dataclass(frozen=True)
class LayoutEntry:
    """One row of the layout table."""

    path: str  # directory path, or ROOT_LABEL for loose top-level files
    files: int
    lines: int
    main_language: Optional[str]
    purpose: str


def _group_key(path: str, depth: int) -> str:
    """Map a file path onto its layout row (its directory, capped at depth)."""
    parts = path.split("/")
    if len(parts) == 1:
        return ROOT_LABEL
    return "/".join(parts[:-1][:depth])


def purpose_for(dirpath: str, main_language: Optional[str], main_category: Optional[str]) -> str:
    """Choose the human label for a directory.

    Every path segment is checked against the convention table, most specific
    (deepest) first, so ``src/tests`` reads as tests rather than source. When
    no segment is conventional, the dominant language stands in.
    """
    for segment in reversed(dirpath.lower().split("/")):
        if segment in PURPOSE_MAP:
            return PURPOSE_MAP[segment]
    if main_language and main_category == CODE:
        return f"{main_language} code"
    if main_language:
        return f"{main_language} files"
    return "Files"


def build_layout(files: Iterable[FileStat], depth: int = 2) -> List[LayoutEntry]:
    """Group files into layout rows, sorted with root files first.

    ``depth`` caps how deep directories are shown: ``src/pkg/sub/x.py`` folds
    into ``src/pkg`` at the default depth of 2. Binary files count toward the
    file total but contribute no lines.
    """
    groups: Dict[str, List[FileStat]] = {}
    for f in files:
        groups.setdefault(_group_key(f.path, depth), []).append(f)

    entries: List[LayoutEntry] = []
    for key, members in groups.items():
        lang_lines: Dict[str, int] = {}
        lang_cat: Dict[str, str] = {}
        total_lines = 0
        for f in members:
            if f.binary:
                continue
            lang_lines[f.language] = lang_lines.get(f.language, 0) + f.lines
            lang_cat[f.language] = f.category
            total_lines += f.lines
        main_language = None
        if lang_lines:
            main_language = min(lang_lines, key=lambda k: (-lang_lines[k], k))
        if key == ROOT_LABEL:
            purpose = "Top-level files (manifest, docs, config)"
        else:
            purpose = purpose_for(key, main_language, lang_cat.get(main_language or ""))
        entries.append(
            LayoutEntry(
                path=key,
                files=len(members),
                lines=total_lines,
                main_language=main_language,
                purpose=purpose,
            )
        )

    entries.sort(key=lambda e: (e.path != ROOT_LABEL, e.path))
    return entries
