"""Repository tree walking: ignore rules, binary sniffing, line counting.

The walker is the data source for everything else in repobrief, so it has to
be predictable: results are sorted, symlinks are never followed, and the same
tree always produces the same list. Two layers of ignoring are applied:

1. A built-in set of directories that are never interesting in a brief
   (``.git``, ``node_modules``, build outputs, virtualenvs, caches).
2. A pragmatic subset of the repository's root ``.gitignore``.

The ``.gitignore`` subset covers the patterns that appear in real ignore
files: comments, directory patterns (``dist/``), root-anchored patterns
(``/local.cfg``), glob patterns (``*.log``), and path patterns
(``docs/_build``). Negation (``!pattern``) is intentionally not supported --
un-ignoring is rare and half-supporting it would be worse than skipping it.
"""

from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass
from typing import List, Optional, Tuple

#: Directories that never belong in an orientation brief.
DEFAULT_IGNORE_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        ".tox",
        ".nox",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        ".cache",
        ".eggs",
        "dist",
        "build",
        "target",
        ".next",
        ".nuxt",
        ".idea",
        ".vscode",
        ".DS_Store",
        "vendor",
        "coverage",
        "htmlcov",
    }
)

_BINARY_SNIFF_BYTES = 8192
_CHUNK = 1 << 16


@dataclass(frozen=True)
class FileStat:
    """One regular file inside the repository."""

    path: str  # repo-relative, posix separators
    size: int  # bytes
    lines: int  # text lines; 0 for binary files
    binary: bool
    language: str
    category: str


class IgnoreRules:
    """A parsed subset of a root ``.gitignore``."""

    def __init__(self, patterns: Optional[List[str]] = None) -> None:
        self._rules: List[Tuple[str, bool, bool]] = []  # (pattern, dir_only, anchored)
        for raw in patterns or []:
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith("!"):
                continue  # blank, comment, or unsupported negation
            dir_only = line.endswith("/")
            line = line.rstrip("/")
            anchored = line.startswith("/")
            line = line.lstrip("/")
            if line:
                self._rules.append((line, dir_only, anchored))

    @classmethod
    def load(cls, root: str) -> "IgnoreRules":
        path = os.path.join(root, ".gitignore")
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                return cls(fh.read().splitlines())
        except OSError:
            return cls([])

    def matches(self, relpath: str, is_dir: bool) -> bool:
        """True when ``relpath`` (posix, repo-relative) should be skipped."""
        base = relpath.rsplit("/", 1)[-1]
        for pattern, dir_only, anchored in self._rules:
            if dir_only and not is_dir:
                continue
            if "/" in pattern or anchored:
                if fnmatch.fnmatchcase(relpath, pattern):
                    return True
            elif fnmatch.fnmatchcase(base, pattern):
                return True
        return False


def sniff_binary(path: str) -> bool:
    """Heuristic binary check: a NUL byte in the first 8 KiB."""
    try:
        with open(path, "rb") as fh:
            return b"\x00" in fh.read(_BINARY_SNIFF_BYTES)
    except OSError:
        return True  # unreadable files are treated as opaque


def count_lines(path: str) -> int:
    """Count text lines the way editors do.

    A trailing byte sequence without a final newline still counts as a line,
    so ``b"a\\nb"`` is 2 lines and ``b""`` is 0.
    """
    lines = 0
    last = b"\n"
    try:
        with open(path, "rb") as fh:
            while True:
                chunk = fh.read(_CHUNK)
                if not chunk:
                    break
                lines += chunk.count(b"\n")
                last = chunk[-1:]
    except OSError:
        return 0
    if last != b"\n":
        lines += 1
    return lines


def walk(root: str, ignore: Optional[IgnoreRules] = None) -> List[FileStat]:
    """Collect :class:`FileStat` for every interesting file under ``root``.

    Results are sorted by path so every downstream table and JSON export is
    deterministic. Symlinks (both directory and file) are skipped: they can
    point outside the repository or create cycles.
    """
    from . import languages  # local import: avoid a hard cycle at module load

    rules = ignore if ignore is not None else IgnoreRules.load(root)
    out: List[FileStat] = []
    root = os.path.abspath(root)

    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        rel_dir = os.path.relpath(dirpath, root).replace(os.sep, "/")
        if rel_dir == ".":
            rel_dir = ""
        keep = []
        for d in sorted(dirnames):
            rel = f"{rel_dir}/{d}" if rel_dir else d
            if d in DEFAULT_IGNORE_DIRS or rules.matches(rel, is_dir=True):
                continue
            if os.path.islink(os.path.join(dirpath, d)):
                continue
            keep.append(d)
        dirnames[:] = keep

        for name in sorted(filenames):
            rel = f"{rel_dir}/{name}" if rel_dir else name
            full = os.path.join(dirpath, name)
            if os.path.islink(full) or rules.matches(rel, is_dir=False):
                continue
            try:
                size = os.stat(full).st_size
            except OSError:
                continue
            binary = sniff_binary(full) if size else False
            lines = 0 if binary else count_lines(full)
            lang, cat = languages.detect(rel)
            out.append(
                FileStat(
                    path=rel,
                    size=size,
                    lines=lines,
                    binary=binary,
                    language=lang,
                    category=cat,
                )
            )

    out.sort(key=lambda f: f.path)
    return out
