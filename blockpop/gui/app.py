"""Streamlit app shell for blockpop.

A single entry point (``app.py`` at the repo root) launches this shell.
The shell resolves the active project from session state — the
``Projects`` tab creates or switches projects — and renders one tab per
tool.

To add a new tab, import the module and add it to the ``_TABS`` list.
"""

from pathlib import Path

import streamlit as st

from blockpop.gui import (
    census_key_editor,
    county_selector,
    controls_editor,
    marginals_editor,
    population_synthesis,
    project_creator,
)
from blockpop.gui.projects import list_projects, projects_root

_ACTIVE_KEY = "active_project_dir"

# (label, render_function) — extend this list for future tabs
_TABS = [
    ("Census API Key", census_key_editor.render),
    ("County Selection", county_selector.render),
    ("Marginals Groups", marginals_editor.render),
    ("Controls", controls_editor.render),
    ("Population Synthesis", population_synthesis.render),
]


def active_project_dir() -> Path | None:
    """Return the project directory selected in this session, if any."""
    value = st.session_state.get(_ACTIVE_KEY)
    return Path(value) if value else None


def set_active_project_dir(path: Path):
    st.session_state[_ACTIVE_KEY] = str(Path(path).resolve())


def run(project_dir: Path | None = None):
    """Launch the GUI.

    Parameters
    ----------
    project_dir : Path, optional
        Project to open on first load.  When omitted, the project chosen
        earlier in this session is reopened; otherwise the user creates
        or picks one in the Projects tab.
    """
    st.set_page_config(page_title="blockpop", layout="wide")

    if _ACTIVE_KEY not in st.session_state:
        if project_dir is not None:
            set_active_project_dir(project_dir)
        else:
            existing = list_projects()
            # Only one project exists — open it so the user can start right away.
            if len(existing) == 1:
                set_active_project_dir(projects_root() / existing[0])

    active = active_project_dir()
    st.title(f"🧱 {active.name}" if active else "🧱 blockpop")

    if active is None:
        st.info("Create a new project to get started.")
        project_creator.render(None)
        return

    tabs = st.tabs(["Projects"] + [label for label, _ in _TABS])
    with tabs[0]:
        project_creator.render(active)
    for tab, (_, render_fn) in zip(tabs[1:], _TABS):
        with tab:
            render_fn(active)
