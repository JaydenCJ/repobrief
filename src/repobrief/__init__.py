"""repobrief: a one-page orientation brief for any repository.

Public API::

    from repobrief import build, Options, render_markdown, render_json

    brief = build("/path/to/repo", Options(top=5))
    print(render_markdown(brief))

Everything below re-exports the stable surface; the submodules
(:mod:`repobrief.churn`, :mod:`repobrief.entrypoints`, ...) are importable
for advanced use but their internals may move between minor versions.
"""

from .brief import Brief, Options, build
from .churn import HotFile, rank
from .commands import Command
from .entrypoints import EntryPoint
from .fswalk import FileStat, walk
from .gitinfo import Commit, GitSummary, parse_log
from .health import Health
from .languages import LanguageShare
from .layout import LayoutEntry
from .render import render_json, render_markdown
from .version import __version__

__all__ = [
    "Brief",
    "Options",
    "build",
    "HotFile",
    "rank",
    "Command",
    "EntryPoint",
    "FileStat",
    "walk",
    "Commit",
    "GitSummary",
    "parse_log",
    "Health",
    "LanguageShare",
    "LayoutEntry",
    "render_json",
    "render_markdown",
    "__version__",
]
