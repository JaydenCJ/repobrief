# repobrief examples

## `build_playground.py`

Builds a small, fully deterministic Node project with three authors' worth of
pinned-date git history — the same fixture `scripts/smoke.sh` uses. The relay
core (`src/relay.js`) receives the most recent commits, so it should always
come out as the number-one hot file.

```bash
python examples/build_playground.py /tmp/playground
repobrief /tmp/playground --now 1751500800 --top 5
```

Because every commit date is pinned and `--now` fixes the reference clock,
the generated brief is byte-for-byte reproducible — run it twice and diff.

## Handoff workflow

The intended real-world loop is a single command at handoff time:

```bash
repobrief . --out BRIEF.md         # commit alongside your README, or
repobrief . --json | your-tooling  # feed an agent / dashboard
```

`--top`, `--depth`, and `--half-life` tune how much history and structure the
one page spends its space on; see the reference table in the main README.
