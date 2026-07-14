# Changelog

All notable changes to this project are documented in this file. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-07-13

### Added

- One-page markdown orientation brief: header (identity, totals, git facts),
  language breakdown, annotated layout table, entry points, commands,
  churn-ranked hot files, and a health checklist.
- Churn-ranked hot files with exponential recency decay (configurable
  `--half-life`), distinct-author counts, last-touched ages, and proportional
  heat bars; deleted and renamed-away paths are filtered out so the table
  never points at files that no longer exist.
- Entry-point detection across ecosystems: `pyproject.toml` console scripts,
  `__main__.py` packages (src and flat layouts), root Python scripts,
  `package.json` `bin`/`main` plus conventional server files, Cargo `[[bin]]`
  and `src/main.rs`/`src/bin/`, Go `main.go` and `cmd/*/main.go` (verified
  `package main`), Dockerfile `ENTRYPOINT`/`CMD`, and Procfile processes.
- Command extraction with provenance and one-line descriptions:
  `package.json` scripts, Makefile targets (`## desc` and preceding-comment
  conventions), justfile recipes, `scripts/*.sh`, and inferred toolchain
  commands (`cargo test`, `go test ./...`, `pytest`).
- Annotated layout: directories grouped to a configurable `--depth`, labeled
  from a curated purpose table with dominant-language fallback.
- Repository walking with built-in noise filtering (VCS dirs, virtualenvs,
  build outputs, caches), a practical root-`.gitignore` subset, NUL-byte
  binary sniffing, and symlink skipping.
- Manifest identity resolution (`pyproject.toml` → `package.json` →
  `Cargo.toml` → `go.mod` → directory name) including a minimal TOML fallback
  parser for Python 3.9/3.10 where `tomllib` is unavailable.
- Health checklist: README/CONTRIBUTING/CHANGELOG detection, license family
  identification from text, CI configuration, test presence, lockfiles.
- `--json` machine-readable twin of the brief (sorted keys, stable schema,
  documented in `docs/brief-format.md`), `--out`, `--top`, `--depth`,
  `--max-commits`, `--half-life`, `--no-git`, and `--now` for byte-for-byte
  reproducible output.
- Deterministic example playground (`examples/build_playground.py`) with
  pinned three-author git history.
- 90 offline deterministic tests and `scripts/smoke.sh`.

### Notes

- The repository ships no CI workflow; verification is local —
  `pip install -e '.[dev]' && pytest && bash scripts/smoke.sh`.

[0.1.0]: https://github.com/JaydenCJ/repobrief/releases/tag/v0.1.0
