import os
from importlib import resources
from pathlib import Path
import re
import warnings
import pandas as pd
import yaml

from blockpop.util.env import dotenv_path, load_dotenv

class Pipeline:
    def __init__(self, settings_path='configs'):
        """
        Initialize Pipeline with settings loaded from a YAML file.
        """
        self.settings_path = Path(settings_path).resolve()
        self.base_dir = self.settings_path.parent

        with open(self.settings_path / 'settings.yaml', 'r') as file:
            self.settings = yaml.safe_load(file)

        # create data and output directories if they don't exist
        self.create_directory(path=self.get_data_dir())
        self.create_directory(path=self.get_output_dir())

        self.state_county_fips = self.get_state_county_fips()
        self.data_dir = self.get_data_dir()
        self.output_dir = self.get_output_dir()
        self.CENSUS_KEY = self.get_census_key()
        self.acs_config_dir = self.get_acs_config_dir()
        self.dec_config_dir = self.get_dec_config_dir()
        self.acs_year = self.settings.get('acs_year')
        self.base_year = self.settings.get('base_year')

    def _resolve_workspace_path(self, configured_path, default_name):
        path = Path(configured_path or default_name)
        if not path.is_absolute():
            path = self.base_dir / path
        return path

    def get_data_dir(self):
        # Returns the data directory path from settings.yaml
        return str(self._resolve_workspace_path(self.settings.get('data_dir'), 'data'))
    
    def get_output_dir(self):
        # Returns the output directory path from settings.yaml
        return str(self._resolve_workspace_path(self.settings.get('output_dir'), 'output'))

    def _get_intermediate_dir(self):
        intermediate = Path(self.get_output_dir()) / 'intermediate'
        self.create_directory(path=str(intermediate))
        return intermediate

    def save_table(self, table_name, df, fmt='parquet'):
        print(f"Saving table '{table_name}' to output/intermediate directory")
        path = self._get_intermediate_dir() / f'{table_name}.{fmt}'
        if fmt == 'parquet':
            df.to_parquet(path)
        elif fmt == 'csv':
            df.to_csv(path, index=False)
        else:
            raise ValueError(f"Unsupported format: {fmt}")

    def get_table(self, table_name):
        parquet_path = self._get_intermediate_dir() / f'{table_name}.parquet'
        if parquet_path.exists():
            return pd.read_parquet(parquet_path)
        csv_path = self._get_intermediate_dir() / f'{table_name}.csv'
        if csv_path.exists():
            return pd.read_csv(csv_path)
        raise FileNotFoundError(f"No parquet or csv file found for table '{table_name}'")

    def get_acs_config_dir(self):
        acs_year = self.settings.get('acs_year')
        if acs_year is None:
            raise ValueError("'acs_year' not found in settings.yaml")
        acs_package = f'blockpop.configs.acs_{acs_year}'
        try:
            acs_dir = resources.files(acs_package)
            return Path(str(acs_dir))
        except ModuleNotFoundError:
            pass

        # Exact year not found — find the most recent available acs config
        configs_dir = Path(str(resources.files('blockpop.configs')))
        available = sorted(
            (int(m.group(1)), d)
            for d in configs_dir.iterdir()
            if d.is_dir() and (m := re.match(r'^acs_(\d+)$', d.name))
        )
        if not available:
            raise FileNotFoundError(
                "No acs_* config directories found in blockpop.configs"
            )
        fallback_year, fallback_dir = available[-1]
        warnings.warn(
            f"ACS config for {acs_year} not found. "
            f"Falling back to acs_{fallback_year}. "
            f"Some ACS variables may have changed and downloading data from the API may fail."
        )
        return fallback_dir

    def get_dec_config_dir(self):
        base_year = self.settings.get('base_year')
        if base_year is None:
            raise ValueError("'base_year' not found in settings.yaml")
        dec_package = f'blockpop.configs.dec_{base_year}'
        try:
            dec_dir = resources.files(dec_package)
            return Path(str(dec_dir))
        except ModuleNotFoundError:
            pass

        configs_dir = Path(str(resources.files('blockpop.configs')))
        available = sorted(
            (int(m.group(1)), d)
            for d in configs_dir.iterdir()
            if d.is_dir() and (m := re.match(r'^dec_(\d+)$', d.name))
        )
        if not available:
            raise FileNotFoundError(
                "No dec_* config directories found in blockpop.configs"
            )
        fallback_year, fallback_dir = available[-1]
        warnings.warn(
            f"Decennial config for {base_year} not found. "
            f"Falling back to dec_{fallback_year}. "
            f"Some census variables may have changed and downloading data from the API may fail."
        )
        return fallback_dir

    def get_state_county_fips(self):
        fips_path = self.settings_path / 'state_county_fips.yaml'
        if fips_path.exists():
            with open(fips_path, 'r') as f:
                scf = yaml.safe_load(f)
            if not isinstance(scf, list):
                scf = []
        else:
            scf = []
        result = {}
        for code in scf:
            code_str = f'{int(code):06d}'
            state_str = code_str[1:3]
            county_id = int(code_str)
            result.setdefault(state_str, []).append(county_id)
        return result
    
    def get_census_key(self):
        key = self.settings.get('census_key')
        if key is None:
            raise ValueError("'census_key' not found in settings.yaml")
        # Load the project's git-ignored .env so the key set via the GUI is
        # available even in environments (e.g. Codespaces) where OS-level
        # environment variables don't propagate to this process.
        load_dotenv(dotenv_path(self.base_dir))
        return os.getenv(key, key)

    def create_directory(self, path_parts: list=None, path: str=None) -> Path:
        """Create a directory if it doesn't exist."""
        if path_parts:
            path = Path(os.path.join(*path_parts))
        else:
            path_parts = path
        if not os.path.exists(path):
            os.makedirs(path)
            print(f"Directory {path} created.")
        return path