# The brief format

A brief is produced in two shapes from the same underlying data: a one-page
markdown document (`repobrief PATH`) and a JSON document (`--json`). Given
identical inputs and a pinned `--now`, both are byte-for-byte reproducible.

## Markdown sections

| Section | Content | Empty behavior |
|---|---|---|
| Header | H1 with the manifest name, blockquoted description, file/line/size totals, primary language, git facts | Description line omitted when no manifest declares one |
| Languages | Per-language files/lines/share, top 6 rows plus an aggregated `_N more_` row | Section omitted for an empty tree |
| Layout | One row per directory (to `--depth`), with file/line counts, dominant language, and a purpose label | `(root)` row always lists loose top-level files |
| Entry points | Kind, name, backing path, copy-pasteable run command | Explanatory placeholder line |
| Commands | Run string, source (`package.json` / `Makefile` / `justfile` / `scripts/` / `inferred`), one-line description; capped at 20 rows | Explanatory placeholder line |
| Hot files | Rank, path, commit count, distinct authors, last-touched age, proportional heat bar | Explains that git history is missing or the scan window is empty |
| Health | Task-list checkboxes: README, license (with identified family), contributing guide, changelog, tests, CI, lockfiles | Never empty |

## Churn scoring

Every commit that touched a file contributes `0.5 ** (age_days / half_life)`
to its score, where `age_days` is measured against `--now` and `half_life`
defaults to 30 days. Ties break on raw commit count, then path. Files that no
longer exist in the work tree are excluded, so the table never points a
newcomer at a deleted or renamed-away path. Merge commits are skipped and the
scan is capped at `--max-commits` (default 400) recent commits.

## JSON schema (v0.1)

Top-level keys, all always present:

| Key | Type | Notes |
|---|---|---|
| `repobrief_version` | string | version of the generator |
| `name` | string | resolved from manifests, else the directory name |
| `description` | string or null | from the winning manifest |
| `generated_at` | integer | unix seconds; equals `--now` when pinned |
| `totals` | object | `files`, `lines`, `bytes` |
| `primary_language` | string or null | largest *code* language |
| `languages` | array | `name`, `category`, `files`, `lines`, `percent` |
| `layout` | array | `path`, `files`, `lines`, `main_language`, `purpose` |
| `entry_points` | array | `kind`, `name`, `path`, `run` |
| `commands` | array | `name`, `run`, `source`, `description` |
| `git` | object or null | `branch`, `total_commits`, `last_commit_ts`, `scanned_commits`, `authors`; null when no history |
| `hot_files` | array | `path`, `commits`, `authors`, `last_commit_ts`, `score` (rounded to 4 decimals) |
| `health` | object | `readme`, `license`, `contributing`, `changelog`, `code_of_conduct`, `ci`, `has_tests`, `lockfiles` |

Serialization uses `sort_keys=True`, two-space indentation, and UTF-8 without
ASCII escaping. Fields will only be added, never renamed or removed, within
the 0.x line; consumers should ignore unknown keys.
