"""Repository health signals: docs, license, CI, tests, lockfiles.

A handoff brief should end with "what safety nets exist": is there a README
worth reading, which license applies, does CI run anything, are there tests
at all. Everything here is detected from file names plus a light content
sniff for the license -- LICENSE files rarely say their SPDX id, so the type
is recognized from the phrases each license family always contains.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional, Set

_LICENSE_FILENAMES = ("LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE", "COPYING")

_TEST_DIR_NAMES = {"tests", "test", "spec", "__tests__"}

_LOCKFILES = (
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "uv.lock",
    "Pipfile.lock",
    "Cargo.lock",
    "go.sum",
    "Gemfile.lock",
    "composer.lock",
)


@dataclass(frozen=True)
class Health:
    """The health checklist rendered at the bottom of a brief."""

    readme: Optional[str]  # filename, or None
    license: Optional[str]  # recognized license name, or None
    contributing: bool
    changelog: bool
    code_of_conduct: bool
    ci: List[str] = field(default_factory=list)  # human descriptions
    has_tests: bool = False
    lockfiles: List[str] = field(default_factory=list)


def identify_license(text: str) -> str:
    """Classify license text by its always-present phrases."""
    head = " ".join(text[:4096].split()).lower()
    if "mit license" in head or "permission is hereby granted, free of charge" in head:
        return "MIT"
    if "apache license" in head and "version 2.0" in head:
        return "Apache-2.0"
    if "gnu affero general public license" in head:
        return "AGPL-3.0"
    if "gnu lesser general public license" in head:
        return "LGPL-3.0" if "version 3" in head else "LGPL-2.1"
    if "gnu general public license" in head:
        return "GPL-3.0" if "version 3" in head else "GPL-2.0"
    if "mozilla public license" in head and "2.0" in head:
        return "MPL-2.0"
    if "redistribution and use in source and binary forms" in head:
        return "BSD"
    if "this is free and unencumbered software released into the public domain" in head:
        return "Unlicense"
    return "present (unrecognized)"


def _detect_license(root: str, files: Set[str]) -> Optional[str]:
    for name in _LICENSE_FILENAMES:
        if name not in files:
            continue
        try:
            with open(os.path.join(root, name), "r", encoding="utf-8", errors="replace") as fh:
                return identify_license(fh.read(4096))
        except OSError:
            return "present (unrecognized)"
    return None


def _detect_ci(files: Set[str]) -> List[str]:
    out: List[str] = []
    workflows = [
        f
        for f in files
        if f.startswith(".github/workflows/") and f.endswith((".yml", ".yaml"))
    ]
    if workflows:
        n = len(workflows)
        out.append(f"GitHub Actions ({n} workflow{'s' if n != 1 else ''})")
    if ".gitlab-ci.yml" in files:
        out.append("GitLab CI")
    if any(f.startswith(".circleci/") for f in files):
        out.append("CircleCI")
    if "Jenkinsfile" in files:
        out.append("Jenkins")
    if ".travis.yml" in files:
        out.append("Travis CI")
    return out


def _detect_tests(files: Set[str]) -> bool:
    for rel in files:
        parts = rel.split("/")
        if any(p in _TEST_DIR_NAMES for p in parts[:-1]):
            return True
        base = parts[-1]
        if base.startswith("test_") and base.endswith(".py"):
            return True
        if base.endswith(("_test.go", "_test.py", ".test.ts", ".test.js", ".spec.ts", ".spec.js")):
            return True
    return False


def _find_doc(files: Set[str], stem: str) -> Optional[str]:
    for suffix in ("", ".md", ".rst", ".txt"):
        for candidate in (stem + suffix, (stem + suffix).lower()):
            if candidate in files:
                return candidate
    return None


def assess(root: str, files: Set[str]) -> Health:
    """Compute the full health checklist from the walked file set."""
    return Health(
        readme=_find_doc(files, "README"),
        license=_detect_license(root, files),
        contributing=_find_doc(files, "CONTRIBUTING") is not None,
        changelog=_find_doc(files, "CHANGELOG") is not None,
        code_of_conduct=_find_doc(files, "CODE_OF_CONDUCT") is not None,
        ci=_detect_ci(files),
        has_tests=_detect_tests(files),
        lockfiles=[name for name in _LOCKFILES if name in files],
    )
