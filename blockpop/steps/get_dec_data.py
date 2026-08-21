import ast

import pandas as pd

from blockpop.util.census_api import CensusAPI, build_aggregated_variables_by_group, build_variables_by_group, build_totals_variables_dict, check_totals, columns_to_int
from blockpop.util.pipeline import Pipeline


def get_dec_dataset(pipeline):
    """Return the decennial dataset name for the pipeline's base_year."""
    return 'sf1' if pipeline.base_year == 2010 else 'dhc'


def get_selected_groups(pipeline):
    """Return the variables-by-group dict for the decennial groups to download.

    Honors ``marginals_groups.yaml`` (selected + ``always_download`` groups)
    when present, otherwise falls back to every group in the config CSV.
    """
    yaml_path = pipeline.settings_path / 'marginals_groups.yaml'
    if yaml_path.exists():
        return build_aggregated_variables_by_group(
            pipeline.dec_config_dir, 'block_marginals_expressions.csv', yaml_path
        )
    return build_variables_by_group(pipeline.dec_config_dir, 'block_marginals_expressions.csv')


def block_marginals_data(pipeline, totals_df):
    census_api = CensusAPI(pipeline.CENSUS_KEY, timeout=300)
    pipeline.create_directory(path=str(pipeline._get_intermediate_dir() / 'dec_data'))
    dataset = get_dec_dataset(pipeline)
    groups = get_selected_groups(pipeline)
    for group_name, variables_dict in groups.items():
        print(f'Downloading decennial block marginals group: {group_name}')
        try:
            dfs = []
            for state_id, county_ids in pipeline.state_county_fips.items():
                state_df = census_api.get_dec_data(
                    variables_dict=variables_dict,
                    year=pipeline.base_year,
                    geog='block',
                    dataset=dataset,
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
    config_path = pipeline.dec_config_dir / 'county_data.csv'
    if not config_path.exists():
        print('Skipping decennial county data: no county_data.csv for this base_year')
        return

    census_api = CensusAPI(pipeline.CENSUS_KEY, timeout=300)
    pipeline.create_directory(path=str(pipeline._get_intermediate_dir() / 'dec_data'))
    config = pd.read_csv(config_path)

    # Separate rows with census variables from expression-only rows
    var_rows = config[config['variables'].notna() & (config['variables'].str.strip() != '')]
    expr_rows = config[config['expression'].notna() & (config['expression'].str.strip() != '')]

    # Build a single variables_dict from all variable rows
    variables_dict = {}
    for _, row in var_rows.iterrows():
        variables_dict[row['name']] = ast.literal_eval(str(row['variables']).strip())

    print('Downloading decennial county data')
    dataset = get_dec_dataset(pipeline)
    try:
        dfs = []
        for state_id, county_ids in pipeline.state_county_fips.items():
            state_df = census_api.get_dec_data(
                variables_dict=variables_dict,
                year=pipeline.base_year,
                geog='county',
                dataset=dataset,
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
    dataset = get_dec_dataset(pipeline)
    try:
        dfs = []
        for state_id, county_ids in pipeline.state_county_fips.items():
            state_df = census_api.get_dec_data(
                variables_dict=variables_dict,
                year=pipeline.base_year,
                geog='block',
                dataset=dataset,
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
    if 'blockpop.steps.calculate_hhpop_age' in pipeline.settings.get('steps', []):
        county_data(pipeline)
    else:
        print('Skipping decennial county data: calculate_hhpop_age step not configured')
    
