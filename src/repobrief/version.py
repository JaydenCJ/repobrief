"""Single source of truth for the package version.

Kept in its own module so low-level modules can import it without pulling in
the whole package via ``repobrief/__init__.py``.
"""

__version__ = "0.1.0"
