import us
import os
from zipfile import ZipFile
import io
from urllib.request import urlopen

from blockpop.util.pipeline import Pipeline


def get_data(census_year, pums_table, state_id_str, state_abbr, pipeline, overwrite=True):
    """
    Downloads PUMS data from the Census FTP and saves it as a CSV file in the data directory.
    If the file already exists, it will not download unless 'overwrite' is set to True.

    Args:
        census_year (int): Year of the PUMS data to download.
        pums_table (str): 'h' for household table, 'p' for person table.
        state_id_str (str): State FIPS code as a string.
        state_abbr (str): State abbreviation in lowercase.
        overwrite (bool): If True, delete existing file and download new one.
    """
    output_dir = pipeline.output_dir
    file_name = f"psam_{pums_table}{state_id_str}.csv"
    file_path = os.path.join(output_dir,"intermediate", file_name)

    if os.path.exists(file_path):
        if overwrite:
            os.remove(file_path)
            print(f"Deleted existing file: {file_path}")
        else:
            print(f"File already exists, skipping download: {file_path}")
            return

    pums_url = f"https://www2.census.gov/programs-surveys/acs/data/pums/{census_year}/5-Year/csv_{pums_table}{state_abbr}.zip"
    r = urlopen(pums_url).read()
    archive = ZipFile(io.BytesIO(r))
    archive.extract(file_name, os.path.join(output_dir, "intermediate"))
    print(f"Downloaded and extracted: {file_name} to {os.path.join(output_dir, 'intermediate')}")

def run_step(context):
    print("Downloading PUMS data...")
    pipeline = Pipeline(settings_path=context['configs_dir'])
    year = pipeline.acs_year
    for state_id_str in pipeline.state_county_fips:
        state_abbr = us.states.mapping('fips', 'abbr')[state_id_str].lower()
        get_data(year,'h',state_id_str,state_abbr,pipeline,overwrite=True)
        get_data(year,'p',state_id_str,state_abbr,pipeline,overwrite=True)
    return context