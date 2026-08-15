import pandas as pd
import geopandas as gpd
import requests
import re

from blockpop.util.pipeline import Pipeline


def get_census_geography_year(pums_year):
    if pums_year >= 2023 and pums_year <= 2032:
        return 2020
    elif pums_year == 2022:
        raise ValueError(
            "PUMS data for 2022 is split between 2010 and 2020 PUMA geographies. "
            "Please choose either 2021 or 2023 for pums_year."
        )
    elif pums_year >= 2016 and pums_year <= 2021:
        return 2010
    elif pums_year >= 2012 and pums_year < 2016:
        raise ValueError(
            "PUMS data for 2012-2015 is split between 2000 and 2010 PUMA geographies. "
            "Please choose either 2011 or 2016 for pums_year."
        )
    elif pums_year >= 2009 and pums_year < 2012:
        return 2000
    else:
        raise ValueError("PUMS year out of range.")


def get_most_recent_tiger_year():
    response = requests.get("https://www2.census.gov/geo/tiger/")
    folders = re.findall(r'TIGER\d{4}/', response.text)
    folders = [f.rstrip('/') for f in folders]
    folders = list(set(folders))
    return max(int(f[5:]) for f in folders)


def create_puma_tract_lookup(pipeline):
    pums_year = pipeline.acs_year
    puma_geog_year = get_census_geography_year(pums_year)
    most_recent_year = get_most_recent_tiger_year()
    most_recent_folder = f"TIGER{most_recent_year}"
    puma_geog_year_two_digit = str(puma_geog_year)[-2:]
    geoid = 'GEOID' + puma_geog_year_two_digit

    all_results = []

    for state_str, county_ids in pipeline.state_county_fips.items():

        # download PUMAs for this state
        puma_url = (
            f"https://www2.census.gov/geo/tiger/{most_recent_folder}/"
            f"PUMA{puma_geog_year_two_digit}/"
            f"tl_{most_recent_year}_{state_str}_puma{puma_geog_year_two_digit}.zip"
        )
        puma = (
            gpd.read_file(puma_url)
            .assign(puma_id=lambda df: ('1' + df[geoid].str.zfill(7)).astype(int))
            [['puma_id', 'geometry']]
        )

        # download tracts for this state
        tract_url = (
            f"https://www2.census.gov/geo/tiger/{most_recent_folder}/"
            f"TRACT/"
            f"tl_{most_recent_year}_{state_str}_tract.zip"
        )
        tracts = (
            gpd.read_file(tract_url)
            .assign(
                tract_id=lambda df: ('1' + df['GEOID']).astype('int64'),
                county_id=lambda df: ('1' + df['GEOID'].str[:5]).astype(int),
            )
            .query('county_id.isin(@county_ids)')
            [['tract_id', 'geometry']]
        )

        # spatial join tract centroids to PUMAs
        tracts.geometry = tracts.representative_point()
        joined = tracts.sjoin(puma, how='left')
        joined['puma_id'] = joined['puma_id'].astype(int)

        joined['region'] = 1

        all_results.append(joined[['tract_id', 'puma_id','region']])

    result = pd.concat(all_results, ignore_index=True)
    result.to_csv(pipeline.data_dir + '/puma_tract_lookup.csv', index=False)


def run_step(context):
    print("Creating PUMA <-> tract lookup table...")
    pipeline = Pipeline(settings_path=context['configs_dir'])
    create_puma_tract_lookup(pipeline)
    return context
