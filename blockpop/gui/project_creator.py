"""Projects tab for the GUI.

Lets the user name a new project and copies the default template into
a fresh folder under the ``projects/`` directory, or switch to an
existing project.  After creation the active session is switched to the
new project so that subsequent tab edits target the correct configs.

This module exposes ``render(project_dir)`` which is called by the
app shell; ``project_dir`` is ``None`` when no project is active yet.
"""

import re
import shutil
from pathlib import Path

import streamlit as st

from blockpop.gui.projects import list_projects, projects_root, template_dir

# Characters allowed in project names (filesystem-safe)
_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clear_tab_session_state():
    """Remove session-state keys owned by other tabs.

    This ensures the County Selection and Marginals Groups tabs re-read
    their configs from the new project directory instead of showing
    stale data from the previous project.
    """
    # County selector
    st.session_state.pop("county_sel_states", None)

    # Marginals editor — fixed keys
    st.session_state.pop("marginals__loaded", None)
    st.session_state.pop("selected_groups", None)

    # Marginals editor — per-group dynamic keys (mode__<group>, bins__<group>)
    for key in list(st.session_state.keys()):
        if key.startswith("mode__") or key.startswith("bins__"):
            del st.session_state[key]

    # Controls editor — fixed keys
    st.session_state.pop("controls__loaded", None)
    st.session_state.pop("ctrl_individual_selected", None)

    # Controls editor — per-group / per-variable dynamic keys
    for key in list(st.session_state.keys()):
        if key.startswith("ctrl_geog__") or key.startswith("ctrl_imp__") or key.startswith("ctrl_var_"):
            del st.session_state[key]


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

def render(project_dir: Path | None):
    st.header("Projects")

    projects = list_projects()

    # --- form ---
    st.subheader("Create new project")
    name = st.text_input(
        "New project name",
        help="Letters, digits, hyphens, and underscores only.",
    )

    if st.button("Create", type="primary"):
        # Validation
        if not name:
            st.error("Please enter a project name.")
            return

        if not _NAME_RE.match(name):
            st.error(
                "Name must start with a letter or digit and contain only "
                "letters, digits, hyphens, or underscores."
            )
            return

        dest = projects_root() / name
        if dest.exists():
            st.error(f"A project named **{name}** already exists.")
            return

        template = template_dir()
        if not template.exists():
            st.error("Default template folder not found.")
            return

        # Copy template → new project
        shutil.copytree(template, dest)

        # Switch the active session to the new project
        st.session_state["active_project_dir"] = str(dest.resolve())
        _clear_tab_session_state()
        st.rerun()

    st.divider()

    # --- existing projects list ---
    if projects:
        st.markdown("**Existing projects:** " + ", ".join(f"`{p}`" for p in projects))
    else:
        st.info("No projects created yet.")

    # --- switch to an existing project ---
    if projects:
        active_name = project_dir.name if project_dir else None
        st.subheader("Open project")
        if active_name:
            st.caption(f"Active project: `{active_name}`")
        selected = st.selectbox(
            "Existing project",
            options=projects,
            index=projects.index(active_name) if active_name in projects else 0,
            key="switch_project_select",
        )
        if st.button("Open", disabled=selected == active_name):
            dest = projects_root() / selected
            st.session_state["active_project_dir"] = str(dest.resolve())
            _clear_tab_session_state()
            st.rerun()
