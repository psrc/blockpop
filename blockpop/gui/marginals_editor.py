"""Marginals Groups editor tab for the project GUI.

Reads marginals_expressions.csv from the package configs, auto-loads
configs/marginals_groups.yaml from the active project directory, and
provides a UI to build custom aggregation bins per group.

This module exposes ``render(project_dir)`` which is called by the
shared app shell.
"""

from collections import OrderedDict
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_PKG_DIR = Path(__file__).resolve().parent.parent
_CSV_PATH = _PKG_DIR / "configs" / "acs_2024" / "marginals_expressions.csv"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_expressions(csv_path: Path) -> pd.DataFrame:
    return pd.read_csv(csv_path)


def get_group_columns(df: pd.DataFrame) -> dict[str, list[str]]:
    """Return {group_name: [column, ...]} preserving CSV order."""
    groups: dict[str, list[str]] = OrderedDict()
    for _, row in df.iterrows():
        g = row["group"]
        groups.setdefault(g, []).append(str(row["name"]))
    return groups


# ---------------------------------------------------------------------------
# YAML generation
# ---------------------------------------------------------------------------


class _FlowList(list):
    """Marker for PyYAML to render this list in flow (inline) style."""
    pass


class _FlowDict(OrderedDict):
    """Marker for PyYAML to render this dict in flow style."""
    pass


def _flow_list_representer(dumper, data):
    return dumper.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=True)


def _flow_dict_representer(dumper, data):
    return dumper.represent_mapping("tag:yaml.org,2002:map", data.items(), flow_style=True)


def _ordered_dict_representer(dumper, data):
    return dumper.represent_mapping("tag:yaml.org,2002:map", data.items())


def _none_representer(dumper, _data):
    return dumper.represent_scalar("tag:yaml.org,2002:null", "")


def _setup_yaml():
    yaml.add_representer(_FlowList, _flow_list_representer)
    yaml.add_representer(_FlowDict, _flow_dict_representer)
    yaml.add_representer(OrderedDict, _ordered_dict_representer)
    yaml.add_representer(type(None), _none_representer)


_setup_yaml()


def build_yaml_dict(
    selected_groups: list[str],
    config: dict,
    suffix_maps: dict[str, dict[str, str]],
) -> OrderedDict:
    """Build an OrderedDict ready for yaml.dump().

    config keys are group names. Each value is either:
      - "passthrough"  (auto-generate 1:1 bins from suffixes)
      - list of (bin_name, [suffix, ...]) tuples  (custom aggregation)
    """
    out = OrderedDict()
    for g in selected_groups:
        group_cfg = config.get(g)
        if group_cfg == "passthrough":
            # Auto-generate one bin per column: {suffix: [suffix]}
            smap = suffix_maps.get(g, {})
            bins_list = []
            for suffix in smap.values():
                bins_list.append(_FlowDict([(suffix, _FlowList([suffix]))]))
            out[g] = bins_list
        else:
            bins_list = []
            for bin_name, suffixes in group_cfg:
                bins_list.append(_FlowDict([(bin_name, _FlowList(suffixes))]))
            out[g] = bins_list
    return out


def dump_yaml(data: OrderedDict) -> str:
    return yaml.dump(data, default_flow_style=False, allow_unicode=True)


# ---------------------------------------------------------------------------
# YAML loading
# ---------------------------------------------------------------------------


def parse_existing_yaml(yaml_text: str, group_columns: dict[str, list[str]]) -> dict:
    """Parse an existing marginals_groups.yaml and return a dict suitable
    for populating session_state.

    Returns: {
        'selected_groups': [str, ...],
        'modes': {group: 'passthrough' | 'aggregate'},
        'bins': {group: [(bin_name, [suffix, ...]), ...]},
    }
    """
    raw = yaml.safe_load(yaml_text)
    if not isinstance(raw, dict):
        return None

    selected = []
    modes = {}
    bins = {}

    for group_name, value in raw.items():
        if group_name not in group_columns:
            continue
        selected.append(group_name)
        if value is None:
            # Null in YAML means passthrough
            modes[group_name] = "passthrough"
        else:
            group_bins = []
            for item in value:
                if isinstance(item, dict):
                    for k, v in item.items():
                        suffixes = [str(s) for s in (v if isinstance(v, list) else [v])]
                        group_bins.append((str(k), suffixes))

            # Detect passthrough: every bin has exactly one suffix == bin name
            is_passthrough = all(
                len(suffs) == 1 and suffs[0] == name
                for name, suffs in group_bins
            )

            if is_passthrough:
                modes[group_name] = "passthrough"
            else:
                modes[group_name] = "aggregate"
                bins[group_name] = group_bins

    return {"selected_groups": selected, "modes": modes, "bins": bins}


# ---------------------------------------------------------------------------
# Session state helpers
# ---------------------------------------------------------------------------


def _key(group: str, prefix: str) -> str:
    return f"{prefix}__{group}"


def init_group_state(group: str):
    """Ensure session_state has entries for a group."""
    mode_key = _key(group, "mode")
    bins_key = _key(group, "bins")
    if mode_key not in st.session_state:
        st.session_state[mode_key] = "passthrough"
    if bins_key not in st.session_state:
        st.session_state[bins_key] = []  # list of (bin_name, [suffix, ...])


def get_bins(group: str) -> list[tuple[str, list[str]]]:
    return st.session_state[_key(group, "bins")]


def set_bins(group: str, bins: list[tuple[str, list[str]]]):
    st.session_state[_key(group, "bins")] = bins


# ---------------------------------------------------------------------------
# Streamlit UI — called as a tab from the project app shell
# ---------------------------------------------------------------------------


def _auto_load_yaml(yaml_path: Path, group_columns: dict[str, list[str]]):
    """Load existing marginals_groups.yaml into session state on first run."""
    if st.session_state.get("marginals__loaded"):
        return
    if not yaml_path.exists():
        st.session_state["marginals__loaded"] = True
        return

    yaml_text = yaml_path.read_text(encoding="utf-8")
    parsed = parse_existing_yaml(yaml_text, group_columns)
    if parsed:
        st.session_state["selected_groups"] = parsed["selected_groups"]
        for g in parsed["selected_groups"]:
            init_group_state(g)
            st.session_state[_key(g, "mode")] = parsed["modes"].get(g, "passthrough")
            if g in parsed.get("bins", {}):
                set_bins(g, parsed["bins"][g])
    st.session_state["marginals__loaded"] = True


def render(project_dir: Path):
    """Render the Marginals Groups editor tab.

    Parameters
    ----------
    project_dir : Path
        Root of the example project (e.g. ``projects/thurston_base_2020``).
        The YAML is read from / written to ``project_dir/configs/marginals_groups.yaml``.
    """
    yaml_path = project_dir / "configs" / "marginals_groups.yaml"

    # Load CSV data
    if not _CSV_PATH.exists():
        st.error(f"Cannot find marginals_expressions.csv at {_CSV_PATH}")
        return
    df = load_expressions(_CSV_PATH)
    group_columns = get_group_columns(df)
    # Exclude groups that should not be aggregated
    excluded_groups = {'total_pop_age'}
    for g in excluded_groups:
        group_columns.pop(g, None)
    all_groups = list(group_columns.keys())

    # Suffix maps: names are used directly (no group prefix stripping needed)
    suffix_maps: dict[str, dict[str, str]] = {}
    for g, cols in group_columns.items():
        suffix_maps[g] = {c: c for c in cols}

    # Auto-load existing YAML on first run
    _auto_load_yaml(yaml_path, group_columns)

    # ---- Layout: left pane (group selection) + main pane (config) ----
    left_pane, main_pane = st.columns([1, 3])

    with left_pane:
        st.header("Marginals Groups")
        default_selected = st.session_state.get("selected_groups", [])
        selected = st.multiselect(
            "Groups to include",
            options=all_groups,
            default=default_selected,
            key="group_selector",
        )
        st.session_state["selected_groups"] = selected

        # Ensure state exists for each selected group
        for g in selected:
            init_group_state(g)

    with main_pane:
        # ---- Per-group configuration ----
        if not selected:
            st.info("Select one or more groups on the left to begin.")
            return

        for group in selected:
            mode_key = _key(group, "mode")
            cols_in_group = group_columns[group]
            smap = suffix_maps[group]
            suffixes = [smap[c] for c in cols_in_group]

            with st.expander(f"**{group}** ({len(cols_in_group)} columns)", expanded=True):
                st.caption("Available columns: " + ", ".join(f"`{s}`" for s in suffixes))

                mode = st.radio(
                    "Mode",
                    ["passthrough", "aggregate"],
                    index=0 if st.session_state[mode_key] == "passthrough" else 1,
                    key=f"radio_{group}",
                    horizontal=True,
                )
                st.session_state[mode_key] = mode

                if mode == "aggregate":
                    bins = get_bins(group)

                    # Collect currently assigned suffixes
                    assigned = set()
                    for _, bin_suffixes in bins:
                        assigned.update(bin_suffixes)
                    unassigned = [s for s in suffixes if s not in assigned]

                    if unassigned:
                        st.warning(f"Unassigned columns: {', '.join(unassigned)}")

                    # --- Render existing bins ---
                    updated_bins = []
                    to_delete = set()

                    for i, (bin_name, bin_suffixes) in enumerate(bins):
                        c1, c2, c3 = st.columns([2, 6, 1])
                        with c1:
                            new_name = st.text_input(
                                "Bin name",
                                value=bin_name,
                                key=f"binname_{group}_{i}",
                                label_visibility="collapsed",
                                placeholder="Bin name",
                            )
                        with c2:
                            # Options = already assigned to this bin + unassigned
                            options = sorted(set(bin_suffixes) | set(unassigned), key=lambda x: suffixes.index(x) if x in suffixes else 999)
                            new_suffixes = st.multiselect(
                                "Columns",
                                options=options,
                                default=bin_suffixes,
                                key=f"bincols_{group}_{i}",
                                label_visibility="collapsed",
                            )
                        with c3:
                            if st.button("🗑️", key=f"bindel_{group}_{i}"):
                                to_delete.add(i)

                        if i not in to_delete:
                            updated_bins.append((new_name, new_suffixes))

                    # Update bins if anything changed
                    if updated_bins != bins or to_delete:
                        set_bins(group, updated_bins)
                        if to_delete:
                            st.rerun()

                    # --- Add new bin button ---
                    if st.button(f"➕ Add bin", key=f"addbin_{group}"):
                        current = get_bins(group)
                        current.append(("new_bin", []))
                        set_bins(group, current)
                        st.rerun()

        # ---- Bottom: YAML preview & save ----
        st.divider()
        st.subheader("YAML Output")

        # Build config dict from session state
        config = {}
        for g in selected:
            mode = st.session_state[_key(g, "mode")]
            if mode == "passthrough":
                config[g] = "passthrough"
            else:
                config[g] = get_bins(g)

        yaml_dict = build_yaml_dict(selected, config, suffix_maps)
        yaml_text = dump_yaml(yaml_dict)

        st.code(yaml_text, language="yaml")

        # Validation warnings
        for g in selected:
            if st.session_state[_key(g, "mode")] == "aggregate":
                bins = get_bins(g)
                names = [b[0] for b in bins]
                if len(names) != len(set(names)):
                    st.warning(f"⚠️ **{g}**: Duplicate bin names detected.")
                for name, suffs in bins:
                    if not suffs:
                        st.warning(f"⚠️ **{g}**: Bin '{name}' has no columns assigned.")

        if st.button("💾 Save", type="primary"):
            try:
                yaml_path.parent.mkdir(parents=True, exist_ok=True)
                yaml_path.write_text(yaml_text, encoding="utf-8")
                st.success(f"Saved to {yaml_path.relative_to(project_dir)}")
            except Exception as e:
                st.error(f"Failed to save: {e}")
