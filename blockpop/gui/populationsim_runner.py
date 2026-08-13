"""Population Synthesis tab for the project GUI.

Provides buttons to generate the marginals (via the create_marginals
step) and to run PopulationSim, streaming logs into the page, then
offers the synthetic population outputs for download.

This module exposes ``render(project_dir)`` which is called by the
shared app shell.
"""

import subprocess
from pathlib import Path

import streamlit as st
from pypyr import pipelinerunner

from blockpop.util.populationsim import get_command, prepare_run
from blockpop.util.pipeline import Pipeline


class _StreamlitLog:
    """File-like object that mirrors writes into a Streamlit placeholder.

    Used to surface ``print``/logging output from in-process calls (e.g. the
    marginals pipeline) live in the page instead of only the terminal.
    """

    def __init__(self, placeholder, max_lines: int = 20):
        self._placeholder = placeholder
        self._max_lines = max_lines
        self._buffer = ""
        self.lines: list[str] = []

    def write(self, text: str) -> int:
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            self.lines.append(line)
        self._render()
        return len(text)

    def flush(self) -> None:
        if self._buffer:
            self.lines.append(self._buffer)
            self._buffer = ""
            self._render()

    def _render(self) -> None:
        display = self.lines + ([self._buffer] if self._buffer else [])
        if display:
            self._placeholder.code("\n".join(display[-self._max_lines :]))


def render(project_dir: Path):
    configs_dir = project_dir / "configs"

    _render_marginals(configs_dir)
    st.divider()
    _render_populationsim(configs_dir)


def _render_marginals(configs_dir: Path):
    import contextlib
    import logging

    st.subheader("Generate Marginals")
    st.caption(
        "Runs the full marginals pipeline to download census data and "
        "build the block, tract, and region marginals."
    )

    if not st.button("Generate Marginals", type="primary"):
        return

    configs_dir = str(Path(configs_dir).resolve())
    log_area = st.empty()
    stream = _StreamlitLog(log_area)
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)

    with st.spinner("Generating marginals… this can take a while."):
        try:
            with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
                pipelinerunner.run(
                    f"{configs_dir}/settings",
                    dict_in={"configs_dir": configs_dir},
                )
        except Exception as e:  # surface pipeline errors clearly
            stream.flush()
            st.error(f"Marginals generation failed: {e}")
            return
        finally:
            stream.flush()
            root_logger.removeHandler(handler)

    st.success("Marginals generated. See the project data directory.")


def _render_populationsim(configs_dir: Path):
    st.subheader("Run PopulationSim")
    st.caption(
        "Synthesizes the population from the marginals created above. "
        "Generate the marginals first if you haven't."
    )

    if not st.button("Run PopulationSim", type="primary"):
        return

    try:
        pipeline = Pipeline(str(configs_dir))
    except Exception as e:  # surface config errors clearly
        st.error(f"Could not load project settings: {e}")
        return

    try:
        config_dir, data_dir, output_dir = prepare_run(pipeline)
    except FileNotFoundError as e:
        st.error(str(e))
        return

    st.info(f"Config: `{config_dir}` · Data: `{data_dir}` · Output: `{output_dir}`")
    command = get_command(pipeline, config_dir, data_dir, output_dir)
    log_area = st.empty()
    lines: list[str] = []

    with st.spinner("Running PopulationSim… this can take a while."):
        proc = subprocess.Popen(
            command,
            cwd=str(pipeline.base_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        for line in proc.stdout:
            lines.append(line.rstrip())
            log_area.code("\n".join(lines[-200:]))
        proc.wait()

    if proc.returncode != 0:
        st.error(f"PopulationSim failed (exit code {proc.returncode}).")
        return

    st.success("PopulationSim complete.")
    for fname in ("synthetic_households.csv", "synthetic_persons.csv"):
        fpath = output_dir / fname
        if fpath.exists():
            st.download_button(
                label=f"Download {fname}",
                data=fpath.read_bytes(),
                file_name=fname,
                mime="text/csv",
            )
