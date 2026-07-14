"""Entry-point detection: where does execution start.

"Where do I even run this?" is the first question in any handoff. This module
answers it across ecosystems by combining two signals: what the manifests
*declare* (console scripts, ``bin`` maps, ``[[bin]]`` targets) and what the
tree *contains* (``__main__.py``, ``src/main.rs``, ``cmd/*/main.go``,
``Dockerfile`` ENTRYPOINT). Every hit comes with a concrete ``run`` hint --
the command a newcomer can paste into a terminal.

Detection never executes anything and reads at most a few small files.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from .manifest import Manifests
from .minitoml import get_path

_GO_PACKAGE_MAIN_RE = re.compile(r"^\s*package\s+main\s*(//.*)?$", re.MULTILINE)
_DOCKER_EXEC_RE = re.compile(r"^\s*(ENTRYPOINT|CMD)\s+(.+)$", re.IGNORECASE | re.MULTILINE)


@dataclass(frozen=True)
class EntryPoint:
    """One way into the program."""

    kind: str  # e.g. "console-script", "python -m", "go main", "docker"
    name: str
    path: str  # repo-relative file backing it, or the manifest that declares it
    run: str  # copy-pasteable command


def _read_text(root: str, rel: str, limit: int = 65536) -> Optional[str]:
    try:
        with open(os.path.join(root, rel), "r", encoding="utf-8", errors="replace") as fh:
            return fh.read(limit)
    except OSError:
        return None


def _python_entrypoints(root: str, files: Set[str], manifests: Manifests) -> List[EntryPoint]:
    out: List[EntryPoint] = []
    scripts = get_path(manifests.pyproject or {}, "project", "scripts")
    if isinstance(scripts, dict):
        for name in sorted(scripts):
            target = scripts[name]
            if isinstance(target, str):
                out.append(
                    EntryPoint(
                        kind="console-script",
                        name=name,
                        path="pyproject.toml",
                        run=name,
                    )
                )
    for rel in sorted(files):
        parts = rel.split("/")
        if parts[-1] != "__main__.py" or len(parts) < 2:
            continue
        pkg_parts = parts[:-1]
        if pkg_parts and pkg_parts[0] in ("src", "lib"):
            pkg_parts = pkg_parts[1:]
        if not pkg_parts:
            continue
        module = ".".join(pkg_parts)
        out.append(
            EntryPoint(kind="python -m", name=module, path=rel, run=f"python -m {module}")
        )
    for candidate in ("main.py", "app.py", "manage.py"):
        if candidate in files:
            out.append(
                EntryPoint(
                    kind="python script",
                    name=candidate,
                    path=candidate,
                    run=f"python {candidate}",
                )
            )
    return out


def _node_entrypoints(files: Set[str], manifests: Manifests) -> List[EntryPoint]:
    out: List[EntryPoint] = []
    pkg = manifests.package_json or {}
    bin_field = pkg.get("bin")
    if isinstance(bin_field, str):
        name = pkg.get("name") if isinstance(pkg.get("name"), str) else "cli"
        out.append(EntryPoint(kind="node bin", name=name, path=bin_field, run=f"node {bin_field}"))
    elif isinstance(bin_field, dict):
        for name in sorted(bin_field):
            target = bin_field[name]
            if isinstance(target, str):
                out.append(EntryPoint(kind="node bin", name=name, path=target, run=f"node {target}"))
    main_field = pkg.get("main")
    if isinstance(main_field, str) and main_field.strip():
        rel = main_field.lstrip("./")
        out.append(EntryPoint(kind="node main", name=rel, path=rel, run=f"node {rel}"))
    if manifests.package_json is not None and not out:
        for candidate in ("server.js", "index.js", "src/index.js", "src/index.ts", "src/server.js"):
            if candidate in files:
                out.append(
                    EntryPoint(
                        kind="node script",
                        name=candidate.rsplit("/", 1)[-1],
                        path=candidate,
                        run=f"node {candidate}",
                    )
                )
                break
    return out


def _rust_entrypoints(files: Set[str], manifests: Manifests) -> List[EntryPoint]:
    out: List[EntryPoint] = []
    declared_paths = set()
    bins = (manifests.cargo or {}).get("bin")
    if isinstance(bins, list):
        for entry in bins:
            if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
                continue
            name = entry["name"]
            path = entry.get("path") if isinstance(entry.get("path"), str) else "Cargo.toml"
            declared_paths.add(path)
            out.append(
                EntryPoint(kind="cargo bin", name=name, path=path, run=f"cargo run --bin {name}")
            )
    if manifests.cargo is not None:
        if "src/main.rs" in files and "src/main.rs" not in declared_paths:
            name = get_path(manifests.cargo, "package", "name") or "main"
            out.append(EntryPoint(kind="cargo bin", name=str(name), path="src/main.rs", run="cargo run"))
        for rel in sorted(files):
            if rel.startswith("src/bin/") and rel.endswith(".rs") and rel not in declared_paths:
                name = rel[len("src/bin/") : -3]
                out.append(
                    EntryPoint(kind="cargo bin", name=name, path=rel, run=f"cargo run --bin {name}")
                )
    return out


def _go_entrypoints(root: str, files: Set[str], manifests: Manifests) -> List[EntryPoint]:
    if manifests.gomod_module is None:
        return []
    out: List[EntryPoint] = []
    candidates = ["main.go"] + sorted(
        rel for rel in files if rel.startswith("cmd/") and rel.endswith("/main.go")
    )
    for rel in candidates:
        if rel not in files:
            continue
        text = _read_text(root, rel, limit=4096)
        if text is None or not _GO_PACKAGE_MAIN_RE.search(text):
            continue  # a main.go that is not `package main` is not runnable
        if rel == "main.go":
            out.append(EntryPoint(kind="go main", name=manifests.name, path=rel, run="go run ."))
        else:
            pkg_dir = rel.rsplit("/", 1)[0]
            out.append(
                EntryPoint(
                    kind="go main",
                    name=pkg_dir.split("/")[-1],
                    path=rel,
                    run=f"go run ./{pkg_dir}",
                )
            )
    return out


def _docker_entrypoints(root: str, files: Set[str]) -> List[EntryPoint]:
    out: List[EntryPoint] = []
    for dockerfile in ("Dockerfile", "Containerfile"):
        if dockerfile not in files:
            continue
        text = _read_text(root, dockerfile)
        if text is None:
            continue
        last: Optional[str] = None
        for m in _DOCKER_EXEC_RE.finditer(text):
            last = f"{m.group(1).upper()} {m.group(2).strip()}"
        if last:
            out.append(
                EntryPoint(kind="docker", name=last, path=dockerfile, run="docker build -t app . && docker run app")
            )
    return out


def _procfile_entrypoints(root: str, files: Set[str]) -> List[EntryPoint]:
    if "Procfile" not in files:
        return []
    text = _read_text(root, "Procfile") or ""
    out: List[EntryPoint] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        name, _, cmd = line.partition(":")
        name, cmd = name.strip(), cmd.strip()
        if name and cmd:
            out.append(EntryPoint(kind="procfile", name=name, path="Procfile", run=cmd))
    return out


def find_entrypoints(root: str, files: Set[str], manifests: Manifests) -> List[EntryPoint]:
    """All detected entry points, deduplicated, in ecosystem order.

    Order is deliberate: declared entry points (console scripts, bins) come
    before inferred ones, and language runtimes before container wrappers,
    because that is the order a newcomer should try them in.
    """
    found: List[EntryPoint] = []
    found.extend(_python_entrypoints(root, files, manifests))
    found.extend(_node_entrypoints(files, manifests))
    found.extend(_rust_entrypoints(files, manifests))
    found.extend(_go_entrypoints(root, files, manifests))
    found.extend(_procfile_entrypoints(root, files))
    found.extend(_docker_entrypoints(root, files))

    seen: Set[tuple] = set()
    unique: List[EntryPoint] = []
    for ep in found:
        key = (ep.kind, ep.name, ep.path)
        if key not in seen:
            seen.add(key)
            unique.append(ep)
    return unique
