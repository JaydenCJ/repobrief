"""A minimal TOML reader used as a fallback below Python 3.11.

``tomllib`` only landed in the standard library in 3.11, and repobrief
promises zero runtime dependencies down to Python 3.9. This module parses the
subset of TOML that real-world manifests (``pyproject.toml``, ``Cargo.toml``)
actually use for the keys repobrief reads:

- ``[table]`` and dotted ``[table.sub]`` headers
- ``[[array-of-tables]]`` headers (how Cargo declares ``[[bin]]``)
- ``key = value`` with basic/literal strings, ints, floats, booleans
- single- and multi-line arrays of scalars
- comments and blank lines

Deliberately unsupported (silently skipped rather than mis-parsed): inline
tables, dotted keys on the left-hand side, multi-line strings, and dates.
When ``tomllib`` is available it is always preferred; see
:func:`repobrief.manifest.load_toml`.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

_TABLE_RE = re.compile(r"^\[\s*([^\[\]]+?)\s*\]$")
_ARRAY_TABLE_RE = re.compile(r"^\[\[\s*([^\[\]]+?)\s*\]\]$")
_KEY_RE = re.compile(r'^\s*(?:"([^"]+)"|\'([^\']+)\'|([A-Za-z0-9_-]+))\s*=\s*(.+)$')
_BASIC_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}


def _strip_comment(line: str) -> str:
    """Remove a trailing comment, respecting quotes."""
    out = []
    quote = None
    i = 0
    while i < len(line):
        ch = line[i]
        if quote:
            if ch == "\\" and quote == '"':
                out.append(line[i : i + 2])
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in ('"', "'"):
            quote = ch
        elif ch == "#":
            break
        out.append(ch)
        i += 1
    return "".join(out).strip()


def _unescape(text: str) -> str:
    out = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text):
            out.append(_BASIC_ESCAPES.get(text[i + 1], text[i + 1]))
            i += 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _parse_scalar(token: str) -> Any:
    token = token.strip()
    if len(token) >= 2 and token[0] == '"' and token[-1] == '"':
        return _unescape(token[1:-1])
    if len(token) >= 2 and token[0] == "'" and token[-1] == "'":
        return token[1:-1]
    if token == "true":
        return True
    if token == "false":
        return False
    plain = token.replace("_", "")
    try:
        return int(plain)
    except ValueError:
        pass
    try:
        return float(plain)
    except ValueError:
        pass
    return token  # dates and anything exotic survive as raw text


def _split_array_items(body: str) -> List[str]:
    """Split the inside of ``[...]`` on top-level commas."""
    items, buf, depth, quote = [], [], 0, None
    for ch in body:
        if quote:
            if ch == quote:
                quote = None
            buf.append(ch)
            continue
        if ch in ('"', "'"):
            quote = ch
            buf.append(ch)
        elif ch == "[":
            depth += 1
            buf.append(ch)
        elif ch == "]":
            depth -= 1
            buf.append(ch)
        elif ch == "," and depth == 0:
            items.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        items.append(tail)
    return [i.strip() for i in items if i.strip()]


def _parse_value(token: str) -> Any:
    token = token.strip()
    if token.startswith("[") and token.endswith("]"):
        return [_parse_scalar(item) for item in _split_array_items(token[1:-1])]
    return _parse_scalar(token)


def _descend(root: Dict[str, Any], dotted: str) -> Dict[str, Any]:
    node = root
    for part in [p.strip().strip('"').strip("'") for p in dotted.split(".")]:
        nxt = node.get(part)
        if isinstance(nxt, list):  # descend into the latest array-of-tables entry
            node = nxt[-1]
            continue
        if not isinstance(nxt, dict):
            nxt = {}
            node[part] = nxt
        node = nxt
    return node


def parse(text: str) -> Dict[str, Any]:
    """Parse TOML text into nested dicts (array-of-tables become lists)."""
    root: Dict[str, Any] = {}
    current = root
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = _strip_comment(lines[i])
        i += 1
        if not line:
            continue

        m = _ARRAY_TABLE_RE.match(line)
        if m:
            dotted = m.group(1)
            parent_path, _, leaf = dotted.rpartition(".")
            parent = _descend(root, parent_path) if parent_path else root
            leaf = leaf.strip().strip('"').strip("'")
            bucket = parent.setdefault(leaf, [])
            if isinstance(bucket, list):
                entry: Dict[str, Any] = {}
                bucket.append(entry)
                current = entry
            continue

        m = _TABLE_RE.match(line)
        if m:
            current = _descend(root, m.group(1))
            continue

        m = _KEY_RE.match(line)
        if not m:
            continue  # unsupported construct: skip, never guess
        key = next(g for g in m.groups()[:3] if g is not None)
        value = m.group(4).strip()

        # Multi-line array: keep consuming lines until brackets balance.
        while value.count("[") > value.count("]") and i < len(lines):
            value += " " + _strip_comment(lines[i])
            i += 1

        if value.startswith("{"):
            continue  # inline tables are out of scope
        current[key] = _parse_value(value)

    return root


def get_path(data: Dict[str, Any], *keys: str) -> Optional[Any]:
    """``get_path(d, "project", "name")`` -> ``d["project"]["name"]`` or None."""
    node: Any = data
    for key in keys:
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node
