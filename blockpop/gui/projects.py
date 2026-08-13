"""Location helpers for blockpop projects.

Kept separate from the app shell so that tab modules can import them
without creating a circular import.
"""

import os
from pathlib import Path

# repo root: <repo>/blockpop/gui/projects.py -> <repo>
_REPO_ROOT = Path(__file__).resolve().parents[2]

TEMPLATE_NAME = "default_template"


def projects_root() -> Path:
    """Return the directory that holds all projects, creating it if needed."""
    override = os.environ.get("BLOCKPOP_PROJECTS_DIR")
    root = Path(override).expanduser().resolve() if override else _REPO_ROOT / "projects"
    root.mkdir(parents=True, exist_ok=True)
    return root


def template_dir() -> Path:
    """Return the default project template shipped with the repo."""
    return _REPO_ROOT / "projects" / TEMPLATE_NAME


def list_projects() -> list[str]:
    """Return sorted names of existing project folders (excluding the template)."""
    return sorted(
        d.name
        for d in projects_root().iterdir()
        if d.is_dir() and d.name != TEMPLATE_NAME
    )
