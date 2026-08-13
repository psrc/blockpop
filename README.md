## blockpop

Block-level synthetic population generation from Census data, driven by a
Streamlit GUI on top of [PopulationSim](https://activitysim.github.io/populationsim/).

### Requirements

- Python 3.11+
- A free [Census API key](https://api.census.gov/data/key_signup.html)

### Install

Using [uv](https://docs.astral.sh/uv/) (recommended):

```bash
uv sync
```

Or with pip:

```bash
python -m venv .venv
.venv\Scripts\activate      # macOS/Linux: source .venv/bin/activate
pip install -e .
```

### Launch the app

From the repository root:

```bash
streamlit run app.py
```

(with uv: `uv run streamlit run app.py`)

That is the only command you need — one entry point serves all projects. The
app opens in your browser at http://localhost:8501.

### Getting started

1. **Create a project.** On first launch only the **Projects** tab is shown.
   Enter a name (letters, digits, `-`, `_`) and click **Create**. This copies
   `projects/default_template` to `projects/<your-name>/` and makes it the
   active project — the remaining tabs appear immediately.
2. **Census API Key.** Paste your key. It is saved to a git-ignored `.env`
   file inside the project folder and referenced by name from
   `configs/settings.yaml`.
3. **County Selection.** Pick the states and counties to synthesize. Saved to
   `configs/state_county_fips.yaml`.
4. **Marginals Groups.** Choose which demographic variables to control and how
   to bin them. Saved to `configs/marginals_groups.yaml`.
5. **Controls.** Assign each marginal group to a geography and importance
   weight. Saved to `popsim_configs/controls.csv`.
6. **Population Synthesis.** Click **Generate Marginals** to download census
   data and build the block, tract, and region marginals, then **Run
   PopulationSim** to synthesize the population. Logs stream into the page and
   results are written to the project's `output/` folder.

Use the **Projects** tab at any time to create another project or open an
existing one. Configuration is stored per project, so switching projects
switches all settings.

### Project layout

```
projects/
  default_template/        # copied when you create a project (do not edit directly)
  <your-project>/
    .env                   # Census API key (git-ignored)
    configs/               # settings.yaml, county and marginals configuration
    popsim_configs/        # PopulationSim settings and controls.csv
    data/                  # downloaded census data and generated marginals
    output/                # synthetic population results
```

Projects live in `projects/` next to this README. Set the
`BLOCKPOP_PROJECTS_DIR` environment variable to store them elsewhere.
