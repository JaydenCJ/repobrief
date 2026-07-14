"""Brief assembly: run every analyzer and combine the results.

:func:`build` is the single public pipeline -- the CLI, the smoke test, and
library users all go through it. Given the same tree, the same git history,
and the same ``now``, it returns an identical :class:`Brief`, which is what
makes repobrief usable in scripts and snapshot tests.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from . import churn, commands, entrypoints, fswalk, gitinfo, health, languages, layout, manifest
from .version import __version__


@dataclass(frozen=True)
class Options:
    """Knobs for a brief; every field has a sane default."""

    top: int = 10  # hot files to show
    depth: int = 2  # directory depth in the layout table
    use_git: bool = True
    now: Optional[float] = None  # pin for reproducible output; None = wall clock
    max_commits: int = 400  # churn scan window
    half_life_days: float = churn.DEFAULT_HALF_LIFE_DAYS


@dataclass
class Brief:
    """Everything a one-page orientation brief contains."""

    name: str
    description: Optional[str]
    root: str
    generated_at: float
    total_files: int
    total_lines: int
    total_bytes: int
    languages: List[languages.LanguageShare]
    primary_language: Optional[languages.LanguageShare]
    layout: List[layout.LayoutEntry]
    entry_points: List[entrypoints.EntryPoint]
    commands: List[commands.Command]
    git: Optional[gitinfo.GitSummary]
    hot_files: List[churn.HotFile]
    health: health.Health
    options: Options = field(default_factory=Options)

    def to_dict(self) -> Dict[str, Any]:
        """A JSON-safe dict mirroring the markdown brief, field for field."""
        return {
            "repobrief_version": __version__,
            "name": self.name,
            "description": self.description,
            "generated_at": int(self.generated_at),
            "totals": {
                "files": self.total_files,
                "lines": self.total_lines,
                "bytes": self.total_bytes,
            },
            "primary_language": self.primary_language.name if self.primary_language else None,
            "languages": [
                {
                    "name": s.name,
                    "category": s.category,
                    "files": s.files,
                    "lines": s.lines,
                    "percent": round(s.percent, 1),
                }
                for s in self.languages
            ],
            "layout": [
                {
                    "path": e.path,
                    "files": e.files,
                    "lines": e.lines,
                    "main_language": e.main_language,
                    "purpose": e.purpose,
                }
                for e in self.layout
            ],
            "entry_points": [
                {"kind": e.kind, "name": e.name, "path": e.path, "run": e.run}
                for e in self.entry_points
            ],
            "commands": [
                {
                    "name": c.name,
                    "run": c.run,
                    "source": c.source,
                    "description": c.description,
                }
                for c in self.commands
            ],
            "git": (
                {
                    "branch": self.git.branch,
                    "total_commits": self.git.total_commits,
                    "last_commit_ts": self.git.last_commit_ts,
                    "scanned_commits": self.git.scanned_commits,
                    "authors": self.git.authors,
                }
                if self.git
                else None
            ),
            "hot_files": [
                {
                    "path": h.path,
                    "commits": h.commits,
                    "authors": h.authors,
                    "last_commit_ts": h.last_ts,
                    "score": round(h.score, 4),
                }
                for h in self.hot_files
            ],
            "health": {
                "readme": self.health.readme,
                "license": self.health.license,
                "contributing": self.health.contributing,
                "changelog": self.health.changelog,
                "code_of_conduct": self.health.code_of_conduct,
                "ci": list(self.health.ci),
                "has_tests": self.health.has_tests,
                "lockfiles": list(self.health.lockfiles),
            },
        }


def build(root: str, options: Optional[Options] = None) -> Brief:
    """Analyze ``root`` and return the assembled :class:`Brief`."""
    opts = options or Options()
    now = opts.now if opts.now is not None else time.time()

    files = fswalk.walk(root)
    file_set = {f.path for f in files}
    shares = languages.breakdown(files)
    manifests = manifest.load(root)

    git_summary: Optional[gitinfo.GitSummary] = None
    hot: List[churn.HotFile] = []
    if opts.use_git:
        collected = gitinfo.collect(root, max_commits=opts.max_commits)
        if collected is not None:
            git_summary, recent = collected
            hot = churn.rank(
                recent,
                now=now,
                half_life_days=opts.half_life_days,
                existing=file_set,
                top=opts.top,
            )

    return Brief(
        name=manifests.name,
        description=manifests.description,
        root=root,
        generated_at=now,
        total_files=len(files),
        total_lines=sum(f.lines for f in files),
        total_bytes=sum(f.size for f in files),
        languages=shares,
        primary_language=languages.primary_language(shares),
        layout=layout.build_layout(files, depth=opts.depth),
        entry_points=entrypoints.find_entrypoints(root, file_set, manifests),
        commands=commands.find_commands(root, file_set, manifests),
        git=git_summary,
        hot_files=hot,
        health=health.assess(root, file_set),
        options=opts,
    )
