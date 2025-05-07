import pandas as pd
import os
import glob
from collections import defaultdict

def scenario_generation(input_dir, output_file, num_scenarios):
    """
    Aggregates simulation data from multiple CSV files, summing data for the
    same simulation index across all files for each time period.

    We can add parallelism processing here through multithreading if needed.

    Args:
        input_dir (str): The root directory containing renewable data CSVs.
        output_file (str): The path to save the aggregated CSV file.
        num_scenarios (int): Number of simulation scenarios to keep.
    """
    all_files = glob.glob(os.path.join(input_dir, '**', '*.csv'), recursive=True)

    # Define the correct hour order and mapping
    hour_columns_ordered = [
        '0800', '0900', '1000', '1100', '1200', '1300', '1400', '1500',
        '1600', '1700', '1800', '1900', '2000', '2100', '2200', '2300',
        '0000', '0100', '0200', '0300', '0400', '0500', '0600', '0700'
    ]
    column_mapping = {col: i + 1 for i, col in enumerate(hour_columns_ordered)}

    # Use defaultdict to accumulate sums
    simulation_sums = defaultdict(lambda: pd.Series(0.0, index=hour_columns_ordered))

    if not all_files:
        print(f"Warning: No CSV files found in {input_dir}")
        return

    for file_path in all_files:
        try:
            df = pd.read_csv(file_path, header=0)

            # Ensure required columns exist
            required_cols = ['Type', 'Index'] + hour_columns_ordered
            if not all(col in df.columns for col in required_cols):
                print(f"Warning: Skipping {file_path}. Missing one or more required columns (Type, Index, or hours).")
                continue

            # Filter for simulation rows
            sim_df = df[df['Type'] == 'Simulation'].copy()

            # Clean up types
            sim_df['Index'] = pd.to_numeric(sim_df['Index'], errors='coerce').astype('Int64')
            for col in hour_columns_ordered:
                sim_df[col] = pd.to_numeric(sim_df[col], errors='coerce').fillna(0)

            sim_df.dropna(subset=['Index'], inplace=True)

            # Aggregate by simulation index
            for _, row in sim_df.iterrows():
                sim_index = row['Index']
                hour_data = row[hour_columns_ordered]
                simulation_sums[sim_index] = simulation_sums[sim_index].add(hour_data, fill_value=0)

        except Exception as e:
            print(f"Error processing file {file_path}: {e}")

    if not simulation_sums:
        print("No simulation data found or aggregated.")
        return

    # Create DataFrame
    final_df = pd.DataFrame(simulation_sums)

    # Select scenarios
    final_df = select_scenarios(final_df, num_scenarios, criteria='first_n')

    final_df.index = [column_mapping.get(hour, hour) for hour in final_df.index]
    final_df.index.name = 'T'
    final_df.columns = final_df.columns.astype(int)

    final_df.to_csv(output_file)
    print(f"Aggregated data written to {output_file}")


def select_scenarios(df, num_scenarios, criteria='first_n', random_state=None):
    """
    Pick a subset of scenario‐columns from `df`.
    Can be expaneded to have custom scenario selection criteria.

    Args:
        df (pd.DataFrame): columns are different scenarios (e.g. simulation indices).
        num_scenarios (int): how many columns to keep.
        criteria (str): 'first_n' or 'random'
        random_state (int, optional): seed for reproducible random sampling.

    Returns:
        pd.DataFrame: with exactly `num_scenarios` columns.
    """
    total = df.shape[1]
    if num_scenarios > total:
        raise ValueError(f"Requested {num_scenarios} scenarios, but only {total} available")

    if criteria == 'first_n':
        return df.iloc[:, :num_scenarios]

    elif criteria == 'random':
        # sample columns, not rows!
        return df.sample(n=num_scenarios, axis=1, random_state=random_state)

    else:
        raise ValueError(f"Invalid criteria: {criteria!r}. Must be 'first_n' or 'random'.")

