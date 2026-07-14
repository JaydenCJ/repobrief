"""Rendering: one markdown page or one JSON document per brief.

The markdown renderer is opinionated about being *one page*: compact tables,
a hard cap on rows per section, and relative timestamps ("3 days ago")
instead of walls of ISO dates. The JSON renderer is the opposite -- complete,
sorted keys, stable field names -- because its consumers are scripts and
agents, not eyeballs.
"""

from __future__ import annotations

import json
from typing import List, Optional

from .brief import Brief
from .churn import HotFile
from .version import __version__

_HEAT_WIDTH = 8
_MAX_COMMAND_ROWS = 20
_MAX_LANG_ROWS = 6


def fmt_int(n: int) -> str:
    """1234567 -> '1,234,567'."""
    return f"{n:,}"


def fmt_bytes(n: int) -> str:
    """Human-friendly size with one decimal above KiB."""
    value = float(n)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024 or unit == "GiB":
            if unit == "B":
                return f"{int(value)} B"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{int(n)} B"  # unreachable, keeps type-checkers calm


def humanize_age(now: float, ts: int) -> str:
    """Coarse relative time; coarse on purpose -- briefs are not audit logs."""
    if ts <= 0:
        return "unknown"
    days = max(0, int((now - ts) // 86400))
    if days == 0:
        return "today"
    if days == 1:
        return "yesterday"
    if days < 14:
        return f"{days} days ago"
    if days < 60:
        return f"{days // 7} weeks ago"
    if days < 730:
        return f"{days // 30} months ago"
    return f"{days // 365} years ago"


def heat_bar(score: float, max_score: float, width: int = _HEAT_WIDTH) -> str:
    """A proportional block bar; the hottest file always fills the width."""
    if max_score <= 0 or score <= 0:
        return ""
    filled = max(1, round(width * score / max_score))
    return "█" * min(width, filled)


def _md_escape(text: str) -> str:
    return text.replace("|", "\\|")


def _check(flag: bool) -> str:
    return "[x]" if flag else "[ ]"


def _hot_files_section(hot: List[HotFile], now: float, git_available: bool) -> List[str]:
    lines: List[str] = ["## Hot files (churn-ranked)", ""]
    if not git_available:
        lines.append("_Not a git repository (or git is unavailable) — no churn history to rank._")
        lines.append("")
        return lines
    if not hot:
        lines.append("_No commits touch the current files within the scan window._")
        lines.append("")
        return lines
    max_score = hot[0].score
    lines.append("| # | File | Commits | Authors | Last touched | Heat |")
    lines.append("|---|------|--------:|--------:|--------------|------|")
    for i, h in enumerate(hot, 1):
        lines.append(
            f"| {i} | `{_md_escape(h.path)}` | {h.commits} | {h.authors} "
            f"| {humanize_age(now, h.last_ts)} | {heat_bar(h.score, max_score)} |"
        )
    lines.append("")
    return lines


def render_markdown(brief: Brief) -> str:
    """The one-page orientation brief."""
    now = brief.generated_at
    out: List[str] = [f"# Repo brief: {brief.name}", ""]
    if brief.description:
        out.append(f"> {brief.description}")
        out.append("")

    primary = (
        f"{brief.primary_language.name} ({brief.primary_language.percent:.0f}%)"
        if brief.primary_language
        else "n/a"
    )
    out.append(
        f"- **Files:** {fmt_int(brief.total_files)} · **Lines:** {fmt_int(brief.total_lines)}"
        f" · **Size:** {fmt_bytes(brief.total_bytes)} · **Primary language:** {primary}"
    )
    if brief.git:
        g = brief.git
        out.append(
            f"- **Git:** branch `{g.branch}` · {fmt_int(g.total_commits)}"
            f" commit{'s' if g.total_commits != 1 else ''}"
            f" · last commit {humanize_age(now, g.last_commit_ts)}"
            f" · {g.authors} author{'s' if g.authors != 1 else ''}"
            f" in the last {g.scanned_commits} commit{'s' if g.scanned_commits != 1 else ''}"
        )
    else:
        out.append("- **Git:** no history available")
    out.append("")

    if brief.languages:
        out.append("## Languages")
        out.append("")
        out.append("| Language | Files | Lines | Share |")
        out.append("|----------|------:|------:|------:|")
        for s in brief.languages[:_MAX_LANG_ROWS]:
            out.append(f"| {s.name} | {s.files} | {fmt_int(s.lines)} | {s.percent:.1f}% |")
        rest = brief.languages[_MAX_LANG_ROWS:]
        if rest:
            out.append(
                f"| _{len(rest)} more_ | {sum(s.files for s in rest)}"
                f" | {fmt_int(sum(s.lines for s in rest))}"
                f" | {sum(s.percent for s in rest):.1f}% |"
            )
        out.append("")

    out.append("## Layout")
    out.append("")
    out.append("| Path | Files | Lines | Main language | Looks like |")
    out.append("|------|------:|------:|---------------|------------|")
    for e in brief.layout:
        path = e.path if e.path == "(root)" else f"`{_md_escape(e.path)}/`"
        out.append(
            f"| {path} | {e.files} | {fmt_int(e.lines)}"
            f" | {e.main_language or '—'} | {_md_escape(e.purpose)} |"
        )
    out.append("")

    out.append("## Entry points")
    out.append("")
    if brief.entry_points:
        out.append("| Kind | Name | Where | Run |")
        out.append("|------|------|-------|-----|")
        for ep in brief.entry_points:
            out.append(
                f"| {ep.kind} | `{_md_escape(ep.name)}` | `{_md_escape(ep.path)}`"
                f" | `{_md_escape(ep.run)}` |"
            )
    else:
        out.append("_None detected — check the README for run instructions._")
    out.append("")

    out.append("## Commands")
    out.append("")
    if brief.commands:
        out.append("| Run | Source | What it does |")
        out.append("|-----|--------|--------------|")
        for c in brief.commands[:_MAX_COMMAND_ROWS]:
            out.append(
                f"| `{_md_escape(c.run)}` | {c.source} | {_md_escape(c.description) or '—'} |"
            )
        if len(brief.commands) > _MAX_COMMAND_ROWS:
            out.append(f"| _… {len(brief.commands) - _MAX_COMMAND_ROWS} more_ | | |")
    else:
        out.append("_No declared commands found (no scripts, Makefile, or justfile)._")
    out.append("")

    out.extend(_hot_files_section(brief.hot_files, now, brief.git is not None))

    h = brief.health
    out.append("## Health")
    out.append("")
    out.append(f"- {_check(h.readme is not None)} README" + (f" (`{h.readme}`)" if h.readme else ""))
    out.append(f"- {_check(h.license is not None)} License" + (f": {h.license}" if h.license else ""))
    out.append(f"- {_check(h.contributing)} Contributing guide")
    out.append(f"- {_check(h.changelog)} Changelog")
    out.append(f"- {_check(h.has_tests)} Tests")
    ci_desc = ", ".join(h.ci) if h.ci else ""
    out.append(f"- {_check(bool(h.ci))} CI" + (f": {ci_desc}" if ci_desc else ""))
    if h.lockfiles:
        out.append(f"- [x] Lockfiles: {', '.join(f'`{lf}`' for lf in h.lockfiles)}")
    out.append("")
    out.append("---")
    out.append("")
    out.append(f"_Generated by [repobrief](https://github.com/JaydenCJ/repobrief) v{__version__}._")
    out.append("")
    return "\n".join(out)


def render_json(brief: Brief) -> str:
    """The machine-readable twin of the markdown brief."""
    return json.dumps(brief.to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
