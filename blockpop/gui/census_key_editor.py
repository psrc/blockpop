"""Census API Key tab for the project GUI.

Lets the user supply a Census API key in one of two ways:

1. **Paste a key** — the key is saved to the project's git-ignored
   ``.env`` file under an environment-variable name (default
   ``CENSUS_KEY``, editable) and that name is recorded in the project's
   ``configs/settings.yaml`` under ``census_key``.
2. **Use an existing env var** — the user simply records the name of an
   environment variable they have already created.

In both cases ``settings.yaml`` stores only the *name* of the environment
variable, never the key itself.  The pipeline resolves the actual key at
runtime via ``os.getenv(name)`` (loading the ``.env`` file first).

This module exposes ``render(project_dir)`` which is called by the shared
app shell.
"""

import os
import re
from pathlib import Path

import streamlit as st

from blockpop.util.env import (
    dotenv_path,
    load_dotenv,
    read_dotenv,
    write_dotenv_var,
)

# Census API key signup page
_SIGNUP_URL = "https://api.census.gov/data/key_signup.html"

# Default environment variable name when the user pastes a raw key
_DEFAULT_VAR_NAME = "CENSUS_KEY"

# Valid environment variable name (POSIX-portable identifier)
_VAR_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


# ---------------------------------------------------------------------------
# settings.yaml helpers
# ---------------------------------------------------------------------------


def _settings_path(project_dir: Path) -> Path:
    return project_dir / "configs" / "settings.yaml"


def _read_settings_census_key(project_dir: Path) -> str | None:
    """Return the current ``census_key`` value from settings.yaml, if any."""
    path = _settings_path(project_dir)
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^census_key:\s*(.*?)\s*$", line)
        if match:
            value = match.group(1).strip().strip("'\"")
            return value or None
    return None


def _write_settings_census_key(project_dir: Path, var_name: str):
    """Write ``census_key: <var_name>`` to settings.yaml.

    Replaces an existing ``census_key:`` line in place to preserve comments
    and the ``steps:`` list; appends the key if it is not present.
    """
    path = _settings_path(project_dir)
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = text.splitlines()

    new_line = f"census_key: {var_name}"
    replaced = False
    for i, line in enumerate(lines):
        if re.match(r"^census_key:\s*", line):
            lines[i] = new_line
            replaced = True
            break

    if not replaced:
        lines.append(new_line)

    # Preserve a trailing newline
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Key persistence (.env file)
# ---------------------------------------------------------------------------


def _save_key(project_dir: Path, name: str, value: str) -> Path:
    """Persist the key to the project's ``.env`` file and current process.

    Writing to a git-ignored ``.env`` file (rather than an OS-level
    environment variable) works reliably across local machines and cloud
    environments such as GitHub Codespaces, where variables set from a GUI
    do not propagate to the running process or to new terminals.
    """
    env_path = write_dotenv_var(dotenv_path(project_dir), name, value)
    # Make it available to the running process (and pipeline) immediately
    os.environ[name] = value
    return env_path


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------


def render(project_dir: Path):
    st.header("Census API Key")

    # Load any key saved to the project's .env so the status below (and the
    # pipeline, which runs in this same process) can see it after a restart.
    load_dotenv(dotenv_path(project_dir))

    # Show feedback carried over from a previous run. st.rerun() discards
    # anything rendered before it, so success messages must survive via
    # session_state rather than being shown immediately before the rerun.
    flash = st.session_state.pop("census_key_flash", None)
    if flash:
        st.success(flash)

    st.markdown(
        "A Census API key is required to download ACS and Decennial data. "
        f"Don't have one yet? [Sign up for a free key]({_SIGNUP_URL})."
    )

    # --- current status ------------------------------------------------------
    current_name = _read_settings_census_key(project_dir)
    if current_name:
        env_values = read_dotenv(dotenv_path(project_dir))
        is_set = bool(os.environ.get(current_name) or env_values.get(current_name))
        status = "✅ set" if is_set else "⚠️ not found in this environment"
        st.caption(
            f"Current setting — `census_key: {current_name}` ({status})"
        )
    else:
        st.caption("No `census_key` is configured for this project yet.")

    st.divider()

    mode = st.radio(
        "How would you like to provide your key?",
        options=[
            "Paste my Census API key",
            "Use an existing environment variable",
        ],
        key="census_key_mode",
    )

    # --- mode 1: paste a key -------------------------------------------------
    if mode == "Paste my Census API key":
        key_value = st.text_input(
            "Census API key",
            type="password",
            help="Stored in the project's git-ignored .env file; "
            "it is not written to settings.yaml.",
        )
        var_name = st.text_input(
            "Environment variable name",
            value=current_name or _DEFAULT_VAR_NAME,
            help="The key will be stored under this name in the .env file.",
        )

        if st.button("Save key", type="primary"):
            if not key_value.strip():
                st.error("Please paste your Census API key.")
                return
            if not _VAR_NAME_RE.match(var_name.strip()):
                st.error(
                    "Variable name must start with a letter or underscore and "
                    "contain only letters, digits, and underscores."
                )
                return

            var_name = var_name.strip()
            try:
                env_path = _save_key(project_dir, var_name, key_value.strip())
            except Exception as exc:  # noqa: BLE001 - surface any write failure
                st.error(f"Failed to save key: {exc}")
                return

            _write_settings_census_key(project_dir, var_name)
            st.session_state["census_key_flash"] = (
                f"Saved key to `{var_name}` in `{env_path}` and recorded "
                f"`census_key: {var_name}` in settings.yaml."
            )
            st.rerun()

    # --- mode 2: existing env var --------------------------------------------
    else:
        var_name = st.text_input(
            "Existing environment variable name",
            value=current_name or _DEFAULT_VAR_NAME,
            help="The name of an environment variable you've already set to "
            "your Census API key.",
        )

        if var_name.strip():
            if os.environ.get(var_name.strip()):
                st.info(f"`{var_name.strip()}` is set in this environment.")
            else:
                st.warning(
                    f"`{var_name.strip()}` is not set in this environment. "
                    "Make sure to create it before running the pipeline."
                )

        if st.button("Save name", type="primary"):
            if not _VAR_NAME_RE.match(var_name.strip()):
                st.error(
                    "Variable name must start with a letter or underscore and "
                    "contain only letters, digits, and underscores."
                )
                return

            _write_settings_census_key(project_dir, var_name.strip())
            st.session_state["census_key_flash"] = (
                f"Recorded `census_key: {var_name.strip()}` in settings.yaml."
            )
            st.rerun()
