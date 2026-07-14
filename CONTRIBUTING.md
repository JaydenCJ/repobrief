# Contributing to repobrief

Thanks for your interest in contributing. Issues, discussions, and pull
requests are all welcome.

## Getting started

Prerequisites: Python 3.9+ and git (git is only needed for the churn features
and the smoke test; the analyzers themselves are pure standard library).

```bash
git clone https://github.com/JaydenCJ/repobrief
cd repobrief
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest                 # 90 deterministic, offline tests
bash scripts/smoke.sh  # end-to-end: playground repo -> brief -> assertions
```

`scripts/smoke.sh` builds a pinned-history example repository and drives the
real CLI against it; it must print `SMOKE OK`.

## Before you open a pull request

1. `pytest` — the whole suite must pass, offline, with no flakiness.
2. `bash scripts/smoke.sh` — must print `SMOKE OK`.
3. Add tests for behavior changes; keep logic in pure, unit-testable
   functions (the parsers in `gitinfo`, `commands`, and `minitoml` take
   plain text precisely so they can be tested without fixtures).
4. Keep the three READMEs aligned: `README.md`, `README.zh.md`, and
   `README.ja.md` are line-for-line translations — update all three when you
   change one (English is the authoritative version).

## Ground rules

- **No runtime dependencies.** The package is standard-library only; that is
  a feature. Test-only dependencies belong in the `dev` extra.
- **No network calls, ever.** repobrief reads the filesystem and shells out
  to local `git`; nothing else. No telemetry.
- **Determinism is part of the contract.** Any output that depends on the
  clock must respect `--now`; any ranking must have total, documented
  tie-breaking.
- Code comments and doc comments are written in English.

## Reporting bugs

Please include `repobrief --version`, the command you ran, and — since briefs
contain no secrets by construction — the generated brief itself plus a rough
sketch of the repository layout that produced it.

## Security

Please do not open public issues for suspected vulnerabilities; use GitHub's
private vulnerability reporting on this repository instead.
