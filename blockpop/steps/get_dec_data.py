import ast

import pandas as pd

from blockpop.util.census_api import CensusAPI, build_variables_by_group, build_totals_variables_dict, check_totals, columns_to_int
from blockpop.util.pipeline import Pipeline


def block_marginals_data(pipeline, totals_df):
    census_api = CensusAPI(pipeline.CENSUS_KEY, timeout=300)
    pipeline.create_directory(path=str(pipeline._get_intermediate_dir() / 'dec_data'))
    groups = build_variables_by_group(pipeline.dec_config_dir, 'block_marginals_expressions.csv')
    for group_name, variables_dict in groups.items():
        print(f'Downloading decennial block marginals group: {group_name}')
        try:
            dfs = []
            for state_id, county_ids in pipeline.state_county_fips.items():
                state_df = census_api.get_dec_data(
                    variables_dict=variables_dict,
                    year=pipeline.base_year,
                    geog='block',
                    dataset='dhc',
                    county_ids=county_ids,
                    state_id=state_id,
                )
                dfs.append(state_df)
            group_df = pd.concat(dfs, ignore_index=True)
        except Exception as e:
            raise RuntimeError(f"Failed to download decennial block marginals group '{group_name}': {e}") from e
        group_df = columns_to_int(group_df)
        pipeline.save_table(f'dec_data/{group_name}', group_df, fmt='csv')
        check_totals(totals_df, group_name, group_df, pipeline.dec_config_dir / 'block_marginals_expressions.csv')
        

def county_data(pipeline):
    census_api = CensusAPI(pipeline.CENSUS_KEY, timeout=300)
    pipeline.create_directory(path=str(pipeline._get_intermediate_dir() / 'dec_data'))
    config = pd.read_csv(pipeline.dec_config_dir / 'county_data.csv')

    # Separate rows with census variables from expression-only rows
    var_rows = config[config['variables'].notna() & (config['variables'].str.strip() != '')]
    expr_rows = config[config['expression'].notna() & (config['expression'].str.strip() != '')]

    # Build a single variables_dict from all variable rows
    variables_dict = {}
    for _, row in var_rows.iterrows():
        variables_dict[row['name']] = ast.literal_eval(str(row['variables']).strip())

    print('Downloading decennial county data')
    try:
        dfs = []
        for state_id, county_ids in pipeline.state_county_fips.items():
            state_df = census_api.get_dec_data(
                variables_dict=variables_dict,
                year=pipeline.base_year,
                geog='county',
                dataset='dhc',
                county_ids=county_ids,
                state_id=state_id,
            )
            dfs.append(state_df)
        df = pd.concat(dfs, ignore_index=True)
    except Exception as e:
        raise RuntimeError(f"Failed to download decennial county data: {e}") from e

    df = columns_to_int(df)

    pipeline.save_table('dec_data/county_data', df, fmt='csv')


def block_totals_data(pipeline):
    census_api = CensusAPI(pipeline.CENSUS_KEY, timeout=300)
    pipeline.create_directory(path=str(pipeline._get_intermediate_dir() / 'dec_data'))
    variables_dict = build_totals_variables_dict(pipeline.dec_config_dir)
    print('Downloading decennial block totals')
    try:
        dfs = []
        for state_id, county_ids in pipeline.state_county_fips.items():
            state_df = census_api.get_dec_data(
                variables_dict=variables_dict,
                year=pipeline.base_year,
                geog='block',
                dataset='dhc',
                county_ids=county_ids,
                state_id=state_id,
            )
            dfs.append(state_df)
        df = pd.concat(dfs, ignore_index=True)
    except Exception as e:
        raise RuntimeError(f"Failed to download decennial block totals: {e}") from e

    df = columns_to_int(df)
    pipeline.save_table('dec_data/dec_totals', df, fmt='csv')
    return df


def run_step(context):
    pipeline = Pipeline(context['configs_dir'])
    totals_df = block_totals_data(pipeline)
    block_marginals_data(pipeline, totals_df)
    county_data(pipeline)
    
