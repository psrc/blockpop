"""County Selection tab for the project GUI.

Reads state_county_fips.csv from the package configs and lets the user
pick states then counties via multiselect widgets.  Selections are saved
back to the project's settings.yaml as a flat list of FIPS codes.

This module exposes ``render(project_dir)`` which is called by the
shared app shell.
"""

from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_PKG_DIR = Path(__file__).resolve().parent.parent
_CSV_PATH = _PKG_DIR / "configs" / "state_county_fips.csv"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_fips_lookup() -> pd.DataFrame:
    return pd.read_csv(_CSV_PATH)


def _load_fips_codes(project_dir: Path) -> list[int]:
    fips_path = project_dir / "configs" / "state_county_fips.yaml"
    if fips_path.exists():
        with open(fips_path, "r") as f:
            data = yaml.safe_load(f)
        if isinstance(data, list):
            return data
    return []


def _save_fips_codes(project_dir: Path, fips_codes: list[int]):
    fips_path = project_dir / "configs" / "state_county_fips.yaml"
    with open(fips_path, "w") as f:
        yaml.dump(fips_codes, f, default_flow_style=True)


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------


def render(project_dir: Path):
    st.header("County Selection")

    fips_df = _load_fips_lookup()
    current_codes = _load_fips_codes(project_dir)

    all_states = sorted(fips_df["state"].unique().tolist())

    # Determine currently-selected states from saved codes
    saved_states = (
        fips_df.loc[fips_df["state_county_fips"].isin(current_codes), "state"]
        .unique()
        .tolist()
    )

    # Session-state list of active states
    if "county_sel_states" not in st.session_state:
        st.session_state.county_sel_states = saved_states if saved_states else []

    # --- Add-state control ---------------------------------------------------
    available_to_add = [s for s in all_states if s not in st.session_state.county_sel_states]
    col_add, col_btn = st.columns([3, 1])
    with col_add:
        new_state = st.selectbox(
            "Add a state",
            options=[""] + available_to_add,
            index=0,
            label_visibility="collapsed",
            placeholder="Add a state…",
        )
    with col_btn:
        if st.button("Add State") and new_state:
            st.session_state.county_sel_states.append(new_state)
            st.rerun()

    # --- Per-state county selectors ------------------------------------------
    selected_codes: list[int] = []

    for state_name in list(st.session_state.county_sel_states):
        state_counties = fips_df.loc[fips_df["state"] == state_name]
        county_options = sorted(state_counties["county"].tolist())

        # Pre-select counties already in settings
        saved_county_names = (
            state_counties.loc[
                state_counties["state_county_fips"].isin(current_codes), "county"
            ]
            .tolist()
        )

        col_label, col_remove = st.columns([6, 1])
        with col_label:
            st.subheader(state_name)
        with col_remove:
            if st.button("Remove", key=f"remove_{state_name}"):
                st.session_state.county_sel_states.remove(state_name)
                st.rerun()

        chosen = st.multiselect(
            f"Counties in {state_name}",
            options=county_options,
            default=saved_county_names,
            key=f"counties_{state_name}",
            label_visibility="collapsed",
        )

        codes = (
            state_counties.loc[
                state_counties["county"].isin(chosen), "state_county_fips"
            ]
            .tolist()
        )
        selected_codes.extend(codes)

    selected_codes.sort()
    st.caption(f"{len(selected_codes)} counties selected")

    if st.button("Save"):
        _save_fips_codes(project_dir, selected_codes)
        st.toast("County selection saved!", icon="✅")
