import pandas as pd
import numpy as np
import os
from pathlib import Path
import argparse
import logging
import sys

def setup_logging():
    """Configures logging for the script."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )

def summarize_batch_results(batch_results_dir, output_summary_file):
    """
    Summarizes results from batch simulations.

    Args:
        batch_results_dir (str): Directory containing the batch simulation run folders.
        output_summary_file (str): Path to save the summary CSV file.
    """
    setup_logging()
    logging.info(f"Starting batch results summarization from: {batch_results_dir}")

    batch_path = Path(batch_results_dir)
    summary_data = []

    run_dirs = sorted([d for d in batch_path.iterdir() if d.is_dir() and d.name.startswith('run_')])

    if not run_dirs:
        logging.warning(f"No run directories found in {batch_results_dir}. Exiting.")
        return

    for run_dir in run_dirs:
        run_id_str = run_dir.name
        logging.info(f"Processing {run_id_str}...")

        renewable_gen_file = run_dir / "renewable_generation.csv"
        system_metrics_file = run_dir / "system_metrics.csv"

        mean_renewable_gen = np.nan
        std_renewable_gen = np.nan
        sum_total_cost = np.nan

        # 1. Process renewable_generation.csv
        if renewable_gen_file.exists():
            try:
                df_renewable = pd.read_csv(renewable_gen_file)
                if 'generation' in df_renewable.columns:
                    mean_renewable_gen = df_renewable['generation'].mean()
                    std_renewable_gen = df_renewable['generation'].std()
                    logging.debug(f"{run_id_str}: Mean Gen={mean_renewable_gen:.2f}, Std Gen={std_renewable_gen:.2f}")
                else:
                    logging.warning(f"'generation' column not found in {renewable_gen_file} for {run_id_str}.")
            except Exception as e:
                logging.error(f"Error processing {renewable_gen_file} for {run_id_str}: {e}")
        else:
            logging.warning(f"{renewable_gen_file} not found for {run_id_str}.")

        # 2. Process system_metrics.csv
        if system_metrics_file.exists():
            try:
                df_metrics = pd.read_csv(system_metrics_file, index_col=0)
                
                scenario_cols = ['1', '2', '3', '4', '5'] 
                actual_scenario_cols = [col for col in scenario_cols if col in df_metrics.columns]

                if 'total cost' in df_metrics.index and actual_scenario_cols:
                    cost_values = pd.to_numeric(df_metrics.loc['total cost', actual_scenario_cols], errors='coerce')
                    sum_total_cost = cost_values.sum()
                    logging.debug(f"{run_id_str}: Sum Total Cost={sum_total_cost}")
                elif 'total cost' not in df_metrics.index:
                    logging.warning(f"'total cost' row not found in {system_metrics_file} for {run_id_str}.")
                else:
                    logging.warning(f"Scenario columns {scenario_cols} not found in {system_metrics_file} for {run_id_str}.")

            except Exception as e:
                logging.error(f"Error processing {system_metrics_file} for {run_id_str}: {e}")
        else:
            logging.warning(f"{system_metrics_file} not found for {run_id_str}.")

        summary_data.append({
            'run_id': run_id_str,
            'mean_renewable_generation': mean_renewable_gen,
            'std_renewable_generation': std_renewable_gen,
            'sum_total_cost': sum_total_cost
        })

    if not summary_data:
        logging.info("No data processed. Summary will be empty.")
        return

    df_summary = pd.DataFrame(summary_data)
    
    Path(output_summary_file).parent.mkdir(parents=True, exist_ok=True)
    
    df_summary.to_csv(output_summary_file, index=False)
    logging.info(f"Batch results summary saved to: {output_summary_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Summarize batch simulation results.")
    parser.add_argument(
        "--batch-results-dir",
        default="results/batch_simulations",
        help="Directory containing the batch simulation run folders."
    )
    parser.add_argument(
        "--output-summary-file",
        default="results/batch_summary.csv",
        help="Path to save the summary CSV file."
    )
    args = parser.parse_args()
    
    summarize_batch_results(args.batch_results_dir, args.output_summary_file) 