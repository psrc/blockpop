"""Population Synthesis tab for the project GUI.

Marginals generation runs as a detached subprocess that logs to a file, so a
browser disconnect can't interrupt it or corrupt partial pipeline output.
PopulationSim is not launched from here — the panel renders the exact command
to run in a terminal, since regional runs outlive any browser session.

This module exposes ``render(project_dir)`` which is called by the
shared app shell.
"""

import os
import shlex
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import streamlit as st

from blockpop.util.populationsim import get_command, prepare_run
from blockpop.util.pipeline import Pipeline

# Keyed by configs dir. Module-level so it outlives the Streamlit session,
# which is torn down whenever the browser disconnects.
_RUNS: dict[str, dict] = {}

_POLL_SECONDS = 2
_LOG_NAME = "marginals_run.log"
_STATUS_NAME = "marginals_run.status"


def render(project_dir: Path):
    configs_dir = (Path(project_dir) / "configs").resolve()

    try:
        pipeline = Pipeline(str(configs_dir))
    except Exception as e:  # surface config errors clearly
        st.error(f"Could not load project settings: {e}")
        return

    output_dir = Path(pipeline.output_dir)

    _render_marginals(configs_dir, output_dir)
    st.divider()
    _render_populationsim(pipeline, output_dir)


# --------------------------------------------------------------------------
# Marginals
# --------------------------------------------------------------------------

def _tail(path: Path, n: int = 200) -> str:
    try:
        return "\n".join(
            path.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]
        )
    except OSError:
        return ""


def _start_marginals(configs_dir: Path, log_path: Path):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    (log_path.parent / _STATUS_NAME).unlink(missing_ok=True)

    # Detach from this process group so a Ctrl-C in the Streamlit terminal
    # doesn't take the pipeline down with it.
    detach = (
        {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        if os.name == "nt"
        else {"start_new_session": True}
    )
    log_file = open(log_path, "w", encoding="utf-8", errors="replace")
    try:
        proc = subprocess.Popen(
            [sys.executable, "-u", "-m", "blockpop.util.run", "-c", str(configs_dir)],
            cwd=str(configs_dir.parent),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            **detach,
        )
    finally:
        log_file.close()  # the child holds its own inherited handle

    _RUNS[str(configs_dir)] = {"proc": proc, "log": log_path}


def _finish_marginals(configs_dir: Path, run: dict, returncode: int):
    (run["log"].parent / _STATUS_NAME).write_text(str(returncode), encoding="utf-8")
    _RUNS.pop(str(configs_dir), None)


def _render_marginals(configs_dir: Path, output_dir: Path):
    st.subheader("Generate Marginals")
    st.caption(
        "Runs the full marginals pipeline to download census data and "
        "build the block, tract, and region marginals. The run continues "
        "even if you close this tab."
    )

    log_path = output_dir / _LOG_NAME
    status_path = output_dir / _STATUS_NAME
    run = _RUNS.get(str(configs_dir))

    if run is not None:
        returncode = run["proc"].poll()
        if returncode is None:
            st.info("Pipeline running… this page polls the log file.")
            st.code(_tail(log_path) or "(waiting for output)")
            if st.button("Stop", key="marginals_stop"):
                run["proc"].terminate()
                _finish_marginals(configs_dir, run, -1)
                st.rerun()
            time.sleep(_POLL_SECONDS)
            st.rerun()
            return
        _finish_marginals(configs_dir, run, returncode)

    if status_path.exists():
        code = status_path.read_text(encoding="utf-8").strip()
        if code == "0":
            st.success("Marginals generated. See the project data directory.")
        elif code == "-1":
            st.warning("Last run was stopped.")
        else:
            st.error(f"Marginals generation failed (exit code {code}).")
        with st.expander("Last run log", expanded=code not in ("0", "-1")):
            st.code(_tail(log_path) or "(no output)")

    if st.button("Generate Marginals", type="primary", key="marginals_start"):
        _start_marginals(configs_dir, log_path)
        st.rerun()


# --------------------------------------------------------------------------
# PopulationSim
# --------------------------------------------------------------------------

def _quote(command: list[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(command)
    return shlex.join(command)


def _render_populationsim(pipeline: Pipeline, output_dir: Path):
    st.subheader("Run PopulationSim")
    st.caption(
        "Regional runs take hours, so PopulationSim is launched from a "
        "terminal rather than the browser. Copy the command below."
    )

    try:
        config_dir, data_dir, output_dir = prepare_run(pipeline)
    except FileNotFoundError as e:
        st.warning(f"Inputs incomplete — {e}")
        config_dir = pipeline.base_dir / "popsim_configs"
        data_dir = Path(pipeline.data_dir)

    st.markdown("**Run from this directory**")
    st.code(str(pipeline.base_dir), language="text")

    st.markdown("**Command**")
    st.code(
        _quote(get_command(pipeline, config_dir, data_dir, output_dir)),
        language="bash",
    )

    _render_output_browser(output_dir)


def _render_output_browser(output_dir: Path):
    st.markdown("**Output files**")
    if not output_dir.exists():
        st.caption("No output directory yet.")
        return

    include_sub = st.checkbox("Include subfolders", value=False, key="popsim_out_sub")
    paths = output_dir.rglob("*") if include_sub else output_dir.glob("*")
    files = sorted((p for p in paths if p.is_file()), key=lambda p: p.name)
    if not files:
        st.caption("No files in the output directory yet.")
        return

    rows = [
        {
            "file": str(p.relative_to(output_dir)),
            "size (MB)": round(p.stat().st_size / 1e6, 3),
            "modified": datetime.fromtimestamp(p.stat().st_mtime).strftime(
                "%Y-%m-%d %H:%M"
            ),
        }
        for p in files
    ]
    st.dataframe(rows, width="stretch", hide_index=True)

    choice = st.selectbox(
        "Download a file", [r["file"] for r in rows], key="popsim_out_pick"
    )
    target = output_dir / choice
    size_mb = target.stat().st_size / 1e6
    if size_mb > 200:
        st.caption(f"{choice} is {size_mb:.0f} MB — copy it from `{target}` instead.")
    elif st.button(f"Prepare {choice} for download", key="popsim_out_prep"):
        st.download_button(
            f"Download {choice}",
            data=target.read_bytes(),
            file_name=target.name,
            mime="text/csv" if target.suffix == ".csv" else "application/octet-stream",
            key="popsim_out_dl",
        )
