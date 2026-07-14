"""Manifest discovery: what is this project called and what does it say it is.

Reads the four manifest formats that cover the overwhelming majority of
repositories -- ``pyproject.toml``, ``package.json``, ``Cargo.toml``,
``go.mod`` -- and resolves a single project identity from them. Parsed
manifests are kept on the returned :class:`Manifests` bundle so entry-point
and command detection can reuse them without touching the disk again.

A broken manifest never aborts the brief: parse errors degrade to "manifest
absent" and the directory name becomes the project name.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from . import minitoml

_GO_MODULE_RE = re.compile(r"^module\s+(\S+)", re.MULTILINE)


def load_toml(path: str) -> Optional[Dict[str, Any]]:
    """Parse a TOML file with ``tomllib`` when available, minitoml otherwise."""
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError:
        return None
    try:
        import tomllib  # Python >= 3.11

        try:
            return tomllib.loads(raw.decode("utf-8", errors="replace"))
        except Exception:
            return None
    except ImportError:
        try:
            return minitoml.parse(raw.decode("utf-8", errors="replace"))
        except Exception:
            return None


def _load_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


@dataclass
class Manifests:
    """Everything repobrief learned from the project's manifests."""

    name: str
    description: Optional[str] = None
    version: Optional[str] = None
    source: str = "directory name"  # which manifest won
    pyproject: Optional[Dict[str, Any]] = field(default=None, repr=False)
    package_json: Optional[Dict[str, Any]] = field(default=None, repr=False)
    cargo: Optional[Dict[str, Any]] = field(default=None, repr=False)
    gomod_module: Optional[str] = None


def _from_pyproject(data: Dict[str, Any]) -> tuple:
    project = data.get("project")
    if not isinstance(project, dict):
        return (None, None, None)
    name = project.get("name")
    return (
        name if isinstance(name, str) else None,
        project.get("description") if isinstance(project.get("description"), str) else None,
        project.get("version") if isinstance(project.get("version"), str) else None,
    )


def _from_package_json(data: Dict[str, Any]) -> tuple:
    name = data.get("name")
    return (
        name if isinstance(name, str) else None,
        data.get("description") if isinstance(data.get("description"), str) else None,
        data.get("version") if isinstance(data.get("version"), str) else None,
    )


def _from_cargo(data: Dict[str, Any]) -> tuple:
    pkg = data.get("package")
    if not isinstance(pkg, dict):
        return (None, None, None)
    name = pkg.get("name")
    return (
        name if isinstance(name, str) else None,
        pkg.get("description") if isinstance(pkg.get("description"), str) else None,
        pkg.get("version") if isinstance(pkg.get("version"), str) else None,
    )


def load(root: str) -> Manifests:
    """Discover manifests under ``root`` and resolve the project identity.

    Identity priority: ``pyproject.toml`` -> ``package.json`` ->
    ``Cargo.toml`` -> ``go.mod`` -> directory name. The first manifest that
    declares a name wins; description and version come from the same winner
    so the header never mixes two manifests' stories.
    """
    pyproject = load_toml(os.path.join(root, "pyproject.toml"))
    package_json = _load_json(os.path.join(root, "package.json"))
    cargo = load_toml(os.path.join(root, "Cargo.toml"))

    gomod_module: Optional[str] = None
    try:
        with open(os.path.join(root, "go.mod"), "r", encoding="utf-8", errors="replace") as fh:
            m = _GO_MODULE_RE.search(fh.read())
            if m:
                gomod_module = m.group(1)
    except OSError:
        pass

    candidates = []
    if pyproject is not None:
        candidates.append(("pyproject.toml",) + _from_pyproject(pyproject))
    if package_json is not None:
        candidates.append(("package.json",) + _from_package_json(package_json))
    if cargo is not None:
        candidates.append(("Cargo.toml",) + _from_cargo(cargo))
    if gomod_module:
        candidates.append(("go.mod", gomod_module.rsplit("/", 1)[-1], None, None))

    name = os.path.basename(os.path.abspath(root)) or "repository"
    description = version = None
    source = "directory name"
    for src, cand_name, cand_desc, cand_version in candidates:
        if cand_name:
            name, description, version, source = cand_name, cand_desc, cand_version, src
            break

    return Manifests(
        name=name,
        description=description,
        version=version,
        source=source,
        pyproject=pyproject,
        package_json=package_json,
        cargo=cargo,
        gomod_module=gomod_module,
    )
