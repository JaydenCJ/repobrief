#!/usr/bin/env python3
"""Build a small, fully deterministic playground repository.

Creates a realistic multi-file Node project with three authors' worth of
pinned-date git history, so ``repobrief`` has something honest to rank:
``src/relay.js`` receives the most recent commits and should come out on top.

Usage::

    python examples/build_playground.py /tmp/playground
    repobrief /tmp/playground --now 1751500800

Every commit date is fixed (late June / early July 2026), so combined with
``--now`` the generated brief is byte-for-byte reproducible. This script is
what ``scripts/smoke.sh`` runs; it needs only Python and git, no network.
"""

from __future__ import annotations

import os
import subprocess
import sys

#: 2026-06-03T00:00:00Z — anchor for the playground's history.
T0 = 1_748_908_800
DAY = 86_400

#: pass this to ``repobrief --now`` for reproducible relative dates
#: (2026-07-03T00:00:00Z, thirty days after the anchor).
SUGGESTED_NOW = T0 + 30 * DAY

FILES = {
    "package.json": (
        '{\n'
        '  "name": "acme-relay",\n'
        '  "version": "1.4.2",\n'
        '  "description": "Webhook relay that fans events out to local consumers",\n'
        '  "main": "src/relay.js",\n'
        '  "scripts": {\n'
        '    "start": "node src/relay.js",\n'
        '    "test": "node --test",\n'
        '    "lint": "eslint src test"\n'
        '  }\n'
        '}\n'
    ),
    "src/relay.js": (
        "// Core relay loop: receives webhooks on 127.0.0.1 and fans them out.\n"
        "const http = require('http');\n"
        "const { route } = require('./routes');\n"
        "\n"
        "function createRelay(port) {\n"
        "  return http.createServer((req, res) => route(req, res));\n"
        "}\n"
        "\n"
        "module.exports = { createRelay };\n"
    ),
    "src/routes.js": (
        "// Maps webhook topics to consumer queues.\n"
        "function route(req, res) {\n"
        "  res.end('ok');\n"
        "}\n"
        "module.exports = { route };\n"
    ),
    "src/queue.js": (
        "// In-memory delivery queue with at-least-once semantics.\n"
        "class Queue {\n"
        "  constructor() { this.items = []; }\n"
        "  push(item) { this.items.push(item); }\n"
        "}\n"
        "module.exports = { Queue };\n"
    ),
    "test/relay.test.js": (
        "const test = require('node:test');\n"
        "test('relay boots', () => {});\n"
    ),
    "docs/protocol.md": "# Relay protocol\n\nEvents are JSON over HTTP, loopback only.\n",
    "scripts/release.sh": "#!/usr/bin/env bash\n# Tag and package a release build\necho release\n",
    "Makefile": (
        "build: ## bundle src/ into dist/\n"
        "\tnode scripts/bundle.js\n"
        "\n"
        "check: ## lint + unit tests\n"
        "\tnpm run lint && npm test\n"
    ),
    "Dockerfile": (
        "FROM node:22-alpine\n"
        "COPY . /app\n"
        "WORKDIR /app\n"
        'ENTRYPOINT ["node", "src/relay.js"]\n'
    ),
    "README.md": "# acme-relay\n\nA demo project for repobrief. Not a real product.\n",
    "LICENSE": (
        "MIT License\n\nCopyright (c) 2026 Acme Examples\n\n"
        "Permission is hereby granted, free of charge, to any person obtaining a copy\n"
        "of this software and associated documentation files.\n"
    ),
    ".gitignore": "node_modules/\n*.log\n",
}


def _write(root: str, rel: str, content: str) -> None:
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path) or root, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def _git(root: str, *args: str, ts: int = T0, author: str = "Ada Example") -> None:
    env = dict(
        os.environ,
        LC_ALL="C",
        GIT_CONFIG_GLOBAL="/dev/null",
        GIT_CONFIG_SYSTEM="/dev/null",
        GIT_AUTHOR_DATE=f"{ts} +0000",
        GIT_COMMITTER_DATE=f"{ts} +0000",
        GIT_AUTHOR_NAME=author,
        GIT_AUTHOR_EMAIL=f"{author.split()[0].lower()}@example.test",
        GIT_COMMITTER_NAME=author,
        GIT_COMMITTER_EMAIL=f"{author.split()[0].lower()}@example.test",
    )
    subprocess.run(["git", *args], cwd=root, env=env, capture_output=True, check=True)


def _commit(root: str, message: str, ts: int, author: str) -> None:
    _git(root, "add", "-A", ts=ts, author=author)
    _git(root, "-c", "commit.gpgsign=false", "commit", "-m", message, ts=ts, author=author)


def build_playground(root: str) -> None:
    os.makedirs(root, exist_ok=True)
    for rel, content in FILES.items():
        _write(root, rel, content)

    _git(root, "init", "-q", "-b", "main")
    _commit(root, "initial import", T0, "Ada Example")

    # A burst of early work on routing (old enough to decay).
    _write(root, "src/routes.js", FILES["src/routes.js"] + "// v2 routing table\n")
    _commit(root, "routing table v2", T0 + 2 * DAY, "Ben Example")
    _write(root, "src/routes.js", FILES["src/routes.js"] + "// v3 routing table\n")
    _commit(root, "routing table v3", T0 + 3 * DAY, "Ben Example")

    # Recent, sustained work on the relay core: this should rank hottest.
    for i, (day, author) in enumerate([(24, "Ada Example"), (26, "Cy Example")]):
        _write(root, "src/relay.js", FILES["src/relay.js"] + f"// rev {i + 2}\n")
        _commit(root, f"relay core rev {i + 2}", T0 + day * DAY, author)

    # One recent touch on the queue.
    _write(root, "src/queue.js", FILES["src/queue.js"] + "// retry support\n")
    _commit(root, "queue retry support", T0 + 27 * DAY, "Cy Example")

    for i, (day, author) in enumerate([(28, "Ada Example"), (29, "Ben Example")]):
        _write(root, "src/relay.js", FILES["src/relay.js"] + f"// rev {i + 4}\n")
        _commit(root, f"relay core rev {i + 4}", T0 + day * DAY, author)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: build_playground.py <target-dir>", file=sys.stderr)
        return 2
    root = sys.argv[1]
    build_playground(root)
    print(f"playground ready: {root}")
    print(f"try: repobrief {root} --now {SUGGESTED_NOW}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
