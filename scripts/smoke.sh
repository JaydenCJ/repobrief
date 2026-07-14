#!/usr/bin/env bash
# Smoke test for repobrief: build the deterministic example playground, then
# exercise the real CLI end-to-end — markdown brief, hot-file ranking, JSON
# output, --out, --no-git, exit codes, --version.
# Self-contained: pure stdlib + git, no network, idempotent (clean tree OK).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [ -x "$ROOT/.venv/bin/python" ]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

# Zero runtime dependencies: running from src/ needs no install.
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/repobrief-smoke.XXXXXX")"
trap 'rm -rf "$WORKDIR"' EXIT

fail() { echo "SMOKE FAIL: $1" >&2; exit 1; }

echo "[smoke] python: $("$PYTHON" --version 2>&1)"
command -v git >/dev/null || fail "git is required for the smoke test"

# Fixed 'now' matching the playground's pinned history (see build_playground.py).
NOW=1751500800

# 1. Build the deterministic playground repository.
"$PYTHON" "$ROOT/examples/build_playground.py" "$WORKDIR/playground" >/dev/null \
  || fail "build_playground.py exited non-zero"
[ -d "$WORKDIR/playground/.git" ] || fail "playground has no git history"

# 2. Markdown brief: header, identity, and every section present.
md_out="$("$PYTHON" -m repobrief "$WORKDIR/playground" --now "$NOW" --top 5)"
echo "$md_out" | head -6 | sed 's/^/[md] /'
echo "$md_out" | grep -q "^# Repo brief: acme-relay" || fail "markdown missing H1 with manifest name"
for section in "## Languages" "## Layout" "## Entry points" "## Commands" \
               "## Hot files (churn-ranked)" "## Health"; do
  echo "$md_out" | grep -qF "$section" || fail "markdown missing section: $section"
done

# 3. Churn ranking: the recently-hammered relay core must be rank 1.
echo "$md_out" | grep -E '^\| 1 \| `src/relay\.js` \| 5 \| 3 ' >/dev/null \
  || fail "hot files rank 1 is not src/relay.js with 5 commits / 3 authors"
echo "$md_out" | grep -qF 'ENTRYPOINT ["node", "src/relay.js"]' \
  || fail "Dockerfile entry point not detected"
echo "$md_out" | grep -qF '`make check`' || fail "Makefile target not extracted"

# 4. Determinism: two runs with the same --now are byte-identical.
md_out2="$("$PYTHON" -m repobrief "$WORKDIR/playground" --now "$NOW" --top 5)"
[ "$md_out" = "$md_out2" ] || fail "same inputs produced different briefs"

# 5. JSON twin: parseable, same story as the markdown.
"$PYTHON" -m repobrief "$WORKDIR/playground" --json --now "$NOW" --top 5 \
  > "$WORKDIR/brief.json" || fail "--json run exited non-zero"
"$PYTHON" - "$WORKDIR/brief.json" <<'PYEOF' || fail "JSON brief failed validation"
import json, sys
data = json.load(open(sys.argv[1]))
assert data["name"] == "acme-relay", data["name"]
assert data["hot_files"][0]["path"] == "src/relay.js"
assert data["git"]["branch"] == "main" and data["git"]["total_commits"] == 8
assert any(c["run"] == "npm start" for c in data["commands"])
print("[json] name/hot_files/git/commands all match")
PYEOF

# 6. --out writes the brief to a file, stdout stays quiet.
out_file="$WORKDIR/BRIEF.md"
quiet="$("$PYTHON" -m repobrief "$WORKDIR/playground" --now "$NOW" --out "$out_file")"
[ -z "$quiet" ] || fail "--out should not print to stdout"
grep -q "^# Repo brief: acme-relay" "$out_file" || fail "--out file missing brief"

# 7. --no-git and plain directories degrade gracefully.
nogit_out="$("$PYTHON" -m repobrief "$WORKDIR/playground" --no-git --now "$NOW")"
echo "$nogit_out" | grep -q "no history available" || fail "--no-git still shows history"
mkdir -p "$WORKDIR/plain" && echo "x = 1" > "$WORKDIR/plain/a.py"
plain_out="$("$PYTHON" -m repobrief "$WORKDIR/plain" --now "$NOW")"
echo "$plain_out" | grep -q "no churn history to rank" \
  || fail "plain directory should explain the missing hot files"

# 8. Exit codes: missing path is a usage error (2), not a crash.
set +e
"$PYTHON" -m repobrief "$WORKDIR/does-not-exist" 2>/dev/null
rc=$?
set -e
[ "$rc" -eq 2 ] || fail "missing path should exit 2, got $rc"

# 9. --version agrees with the package.
version_out="$("$PYTHON" -m repobrief --version)"
pkg_version="$("$PYTHON" -c 'import repobrief; print(repobrief.__version__)')"
[ "$version_out" = "repobrief $pkg_version" ] \
  || fail "--version mismatch: '$version_out' vs package '$pkg_version'"

echo "SMOKE OK"
