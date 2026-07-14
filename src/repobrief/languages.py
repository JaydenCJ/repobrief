"""Language detection and per-language line statistics.

Detection is purely name-based (extension or well-known filename); repobrief
never inspects file *contents* to guess a language. That keeps the scan fast
and deterministic, and in practice extension mapping is right for the
languages that decide what a repository "is".

Every language carries a category so downstream consumers can tell code apart
from docs, data, and configuration: a repository whose biggest line count is
``package-lock.json`` is still a TypeScript project.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

# Categories, in order of "how much this counts as the project's language".
CODE = "code"
MARKUP = "markup"
CONFIG = "config"
DATA = "data"
DOCS = "docs"

OTHER = "Other"

#: extension (lowercase, without the dot) -> (language name, category)
EXT_MAP: Dict[str, tuple] = {
    "py": ("Python", CODE),
    "pyi": ("Python", CODE),
    "js": ("JavaScript", CODE),
    "mjs": ("JavaScript", CODE),
    "cjs": ("JavaScript", CODE),
    "jsx": ("JavaScript", CODE),
    "ts": ("TypeScript", CODE),
    "tsx": ("TypeScript", CODE),
    "go": ("Go", CODE),
    "rs": ("Rust", CODE),
    "java": ("Java", CODE),
    "kt": ("Kotlin", CODE),
    "kts": ("Kotlin", CODE),
    "swift": ("Swift", CODE),
    "c": ("C", CODE),
    "h": ("C", CODE),
    "cc": ("C++", CODE),
    "cpp": ("C++", CODE),
    "cxx": ("C++", CODE),
    "hpp": ("C++", CODE),
    "hxx": ("C++", CODE),
    "m": ("Objective-C", CODE),
    "mm": ("Objective-C", CODE),
    "cs": ("C#", CODE),
    "rb": ("Ruby", CODE),
    "php": ("PHP", CODE),
    "scala": ("Scala", CODE),
    "ex": ("Elixir", CODE),
    "exs": ("Elixir", CODE),
    "erl": ("Erlang", CODE),
    "hs": ("Haskell", CODE),
    "lua": ("Lua", CODE),
    "pl": ("Perl", CODE),
    "r": ("R", CODE),
    "zig": ("Zig", CODE),
    "dart": ("Dart", CODE),
    "sh": ("Shell", CODE),
    "bash": ("Shell", CODE),
    "zsh": ("Shell", CODE),
    "fish": ("Shell", CODE),
    "ps1": ("PowerShell", CODE),
    "bat": ("Batch", CODE),
    "sql": ("SQL", CODE),
    "proto": ("Protobuf", CODE),
    "graphql": ("GraphQL", CODE),
    "vue": ("Vue", CODE),
    "svelte": ("Svelte", CODE),
    "tf": ("Terraform", CONFIG),
    "html": ("HTML", MARKUP),
    "htm": ("HTML", MARKUP),
    "css": ("CSS", MARKUP),
    "scss": ("CSS", MARKUP),
    "sass": ("CSS", MARKUP),
    "less": ("CSS", MARKUP),
    "xml": ("XML", DATA),
    "json": ("JSON", DATA),
    "jsonl": ("JSON", DATA),
    "csv": ("CSV", DATA),
    "yaml": ("YAML", CONFIG),
    "yml": ("YAML", CONFIG),
    "toml": ("TOML", CONFIG),
    "ini": ("INI", CONFIG),
    "cfg": ("INI", CONFIG),
    "conf": ("INI", CONFIG),
    "env": ("Dotenv", CONFIG),
    "md": ("Markdown", DOCS),
    "markdown": ("Markdown", DOCS),
    "rst": ("reStructuredText", DOCS),
    "txt": ("Text", DOCS),
    "adoc": ("AsciiDoc", DOCS),
}

#: exact basename (case-sensitive first, lowercase fallback) -> (name, category)
FILENAME_MAP: Dict[str, tuple] = {
    "Makefile": ("Makefile", CODE),
    "makefile": ("Makefile", CODE),
    "GNUmakefile": ("Makefile", CODE),
    "Dockerfile": ("Dockerfile", CONFIG),
    "Containerfile": ("Dockerfile", CONFIG),
    "justfile": ("Just", CODE),
    "Justfile": ("Just", CODE),
    "CMakeLists.txt": ("CMake", CODE),
    "Gemfile": ("Ruby", CODE),
    "Rakefile": ("Ruby", CODE),
    "Procfile": ("Procfile", CONFIG),
    ".gitignore": ("Gitignore", CONFIG),
    ".gitattributes": ("Gitignore", CONFIG),
    ".editorconfig": ("INI", CONFIG),
    "LICENSE": ("Text", DOCS),
    "COPYING": ("Text", DOCS),
}


def detect(relpath: str) -> tuple:
    """Return ``(language, category)`` for a repo-relative posix path."""
    base = relpath.rsplit("/", 1)[-1]
    if base in FILENAME_MAP:
        return FILENAME_MAP[base]
    if "." in base[1:]:
        ext = base.rsplit(".", 1)[-1].lower()
        if ext in EXT_MAP:
            return EXT_MAP[ext]
    return (OTHER, DATA)


@dataclass(frozen=True)
class LanguageShare:
    """One language's slice of the repository, measured in text lines."""

    name: str
    category: str
    files: int
    lines: int
    percent: float  # of all counted text lines, 0.0-100.0


def breakdown(files: Iterable) -> List[LanguageShare]:
    """Aggregate ``FileStat``-like objects into per-language shares.

    Binary files are excluded (their ``lines`` is meaningless). Shares are
    sorted by lines descending, then name, so output is stable even when two
    languages tie.
    """
    lines: Dict[str, int] = {}
    counts: Dict[str, int] = {}
    cats: Dict[str, str] = {}
    total = 0
    for f in files:
        if f.binary:
            continue
        lines[f.language] = lines.get(f.language, 0) + f.lines
        counts[f.language] = counts.get(f.language, 0) + 1
        cats[f.language] = f.category
        total += f.lines
    shares = [
        LanguageShare(
            name=name,
            category=cats[name],
            files=counts[name],
            lines=n,
            percent=(100.0 * n / total) if total else 0.0,
        )
        for name, n in lines.items()
    ]
    shares.sort(key=lambda s: (-s.lines, s.name))
    return shares


def primary_language(shares: List[LanguageShare]) -> Optional[LanguageShare]:
    """The language the project is "written in".

    Prefers the largest *code* language so that a JavaScript service with a
    huge ``CHANGELOG.md`` is still reported as JavaScript. Falls back to the
    largest share of any category, or ``None`` for an empty repository.
    """
    for share in shares:
        if share.category == CODE:
            return share
    return shares[0] if shares else None
