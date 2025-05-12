import pandas as pd
import numpy as np
import os
import yaml
import logging
from datetime import datetime
from pathlib import Path
import pyomo.environ as pyo
import sys
import multiprocessing # Added for parallelization
import copy # Added for deepcopying config
import argparse

sys.path.append('./src')

from models.DAFOModel import DAFOModel
from models.RTSimModel import RTSimModel
from data_utils.DataProcessor import DataProcessor
from data_utils.extract_da import extract_da
from data_utils.results_processing import (
    calculate_rt_margins,
    calculate_rt_payoffs,
    calculate_system_metrics,
    calculate_premium_convergence,
    calculate_total_margins
)
from data_utils.scenario_generation import scenario_generation

def setup_logging():
    """Configures logging for the script."""
    # Ensure logging is configured only once, even if called by multiple processes
    # if not logging.getLogger().hasHandlers(): # This might be too simplistic for multiprocessing
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(processName)s - %(levelname)s - %(message)s', # Added processName
        handlers=[logging.StreamHandler(sys.stdout)]
    )

def load_config(config_path):
    """Load configuration from YAML file."""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def run_single_simulation(config, pyomo_system_data, run_id):
    """Run a single simulation and return results."""
    # Create and solve DAFO model
    dafo_model = DAFOModel(config)
    da_instance = dafo_model.create_instance(pyomo_system_data)
    
    solver_cfg = config['solver']
    solver_name = solver_cfg['name']
    solver_exec = solver_cfg.get('executable')
    solver_options = solver_cfg.get('options', {})
    
    opt = pyo.SolverFactory(solver_name, executable=solver_exec)
    for key, value in solver_options.items():
        if key != 'tee':
            opt.options[key] = value
    
    try:
        result = opt.solve(da_instance, tee=solver_options.get('tee', False))
        if (result.solver.status != pyo.SolverStatus.ok) or \
           (result.solver.termination_condition != pyo.TerminationCondition.optimal):
            logging.warning(f"Run {run_id}: DAFO model solved with non-optimal status: {result.solver.status}, {result.solver.termination_condition}")
            return None
    except Exception as e:
        logging.error(f"Run {run_id}: Error solving DAFO model: {e}")
        return None

    # Extract data for RT model
    dataRT, total_da, df, demand, Energy, Prices, Gross_margins = extract_da(da_instance, pyomo_system_data)
    
    if dataRT is None:
        logging.error(f"Run {run_id}: Failed to extract data for RT model")
        return None

    # Create and solve RT model
    rt_sim_model = RTSimModel(config)
    rt_instance = rt_sim_model.create_instance(dataRT)
    
    try:
        result = opt.solve(rt_instance, tee=solver_options.get('tee', False))
        if (result.solver.status != pyo.SolverStatus.ok) or \
           (result.solver.termination_condition != pyo.TerminationCondition.optimal):
            logging.warning(f"Run {run_id}: RTSim model solved with non-optimal status: {result.solver.status}, {result.solver.termination_condition}")
            return None
    except Exception as e:
        logging.error(f"Run {run_id}: Error solving RTSim model: {e}")
        return None

    # Calculate metrics
    RTmargins = calculate_rt_margins(rt_instance, dataRT)
    RTpayoffs = calculate_rt_payoffs(rt_instance, dataRT, df)
    Total = calculate_system_metrics(rt_instance, dataRT, total_da)
    premium_convergence = calculate_premium_convergence(Gross_margins, RTpayoffs)
    Total_margin = calculate_total_margins(rt_instance, dataRT, Gross_margins, RTmargins, RTpayoffs, premium_convergence, total_da)

    # Store results
    results = {
        'run_id': run_id,
        # We only need Total and renewable_scenarios for saving in the worker
        'Total': Total,
        'renewable_scenarios': pyomo_system_data[None]['RE']
    }
    
    return results

def convert_renewable_data_to_df(re_data, num_scenarios=5, num_periods=24):
    """Convert renewable data dictionary to a pandas DataFrame."""
    # Create a multi-index DataFrame with scenarios and time periods
    data = []
    for g in range(1, num_scenarios + 1):
        for t in range(1, num_periods + 1):
            data.append({
                'scenario': g,
                'time_period': t,
                'generation': re_data.get((g, t), 0)
            })
    return pd.DataFrame(data)

# New worker function for parallel execution
def run_simulation_worker(args_tuple):
    run_id, base_config, output_dir_base_path_str = args_tuple
    # Ensure logging is setup for this worker process
    # setup_logging() # setup_logging() might be better called once in main or carefully in worker
    
    logging.info(f"Worker starting for run_id: {run_id}")
    
    current_config = copy.deepcopy(base_config) # Deepcopy to avoid issues with shared config objects
    output_dir_base_path = Path(output_dir_base_path_str)

    # Ensure data/processed directory exists
    processed_data_dir = Path("data/processed")
    processed_data_dir.mkdir(parents=True, exist_ok=True)
    
    temp_renewable_csv = processed_data_dir / f"temp_renewable_run_{run_id}.csv"

    try:
        # generate unique scenarios for this run
        logging.debug(f"Run {run_id}: Generating scenarios to {temp_renewable_csv}")
        scenario_generation(
            input_dir="data/raw/renewable",
            output_file=str(temp_renewable_csv),
            config=current_config
        )

        if not temp_renewable_csv.exists():
            logging.error(f"Run {run_id}: scenario_generation failed to create {temp_renewable_csv}. Check 'data/raw/renewable/' contents and scenario_generation.py logic.")
            return run_id, f"scenario_generation failed for {temp_renewable_csv}"

        # update config to use the temporary renewable CSV
        current_config['data_paths']['renewable_csv'] = str(temp_renewable_csv)
        
        # initialize DataProcessor with the unique renewable CSV
        logging.debug(f"Run {run_id}: Initializing DataProcessor with {temp_renewable_csv}")
        data_processor = DataProcessor(
            current_config['data_paths']['generator_csv'],
            current_config['data_paths']['storage_csv'],
            current_config['data_paths']['demand_csv'],
            current_config['data_paths']['renewable_csv']
        )
        
        pyomo_system_data = data_processor.prepare_pyomo_data(current_config)
        if pyomo_system_data is None:
            logging.error(f"Run {run_id}: Failed to prepare Pyomo data.")
            return run_id, "Pyomo data prep failed"

        # single simulation
        logging.debug(f"Run {run_id}: Calling run_single_simulation")
        results = run_single_simulation(current_config, pyomo_system_data, run_id)
        
        if results is None:
            logging.warning(f"Run {run_id}: Simulation failed or returned None.")
            return run_id, "Simulation failed"
            
        # save resykts
        run_dir = output_dir_base_path / f"run_{run_id:03d}"
        run_dir.mkdir(parents=True, exist_ok=True)
        
        re_data = results['renewable_scenarios']
        re_df = convert_renewable_data_to_df(re_data, current_config['general']['num_scenarios'], current_config['general']['num_periods'])
        re_df.to_csv(run_dir / "renewable_generation.csv", index=False)
        
        results['Total'].to_csv(run_dir / "system_metrics.csv")
        logging.info(f"Run {run_id}: Successfully completed and results saved to {run_dir}")
        return run_id, "Success"

    except Exception as e:
        logging.error(f"Run {run_id}: CRITICAL ERROR in worker: {e}", exc_info=True)
        return run_id, f"Critical error: {e}"
    finally:
        # clean up temp renewable CSV
        if temp_renewable_csv.exists():
            try:
                os.remove(temp_renewable_csv)
                logging.debug(f"Run {run_id}: Cleaned up {temp_renewable_csv}")
            except OSError as e:
                logging.error(f"Run {run_id}: Error cleaning up {temp_renewable_csv}: {e}")

def run_batch_simulations(config_path, num_runs=100, output_dir="results/batch_simulations"):
    """Run multiple simulations and store results in parallel."""
    # Setup logging for the main process first.
    # Child processes will inherit this or reconfigure if setup_logging is called in worker.
    # For Pool, it's often better to let children inherit or use a logging queue.
    # The current setup_logging basicConfig might be okay if called early in main.
    if multiprocessing.get_start_method(allow_none=True) is None:
        multiprocessing.set_start_method("spawn", force=True) # Or "fork" on Unix if safe, "spawn" is safer for cross-platform
        
    setup_logging() # Call it once in the main process

    config = load_config(config_path)
    
    config.setdefault('scenario_selection', {})['criteria'] = "random"
    logging.info(f"Batch simulations will use 'random' scenario selection criteria.")
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # determine number of processes - leave one core free for now
    num_processes = max(1, os.cpu_count() - 1 if os.cpu_count() else 1) 
    logging.info(f"Starting batch simulations with {num_runs} runs using up to {num_processes} parallel processes.")

    tasks = [(i, config, str(output_path)) for i in range(num_runs)]

    results_summary = []
    with multiprocessing.Pool(processes=num_processes) as pool:
        # Using map, so worker function takes a single argument (the tuple)
        # starmap would unpack the tuple into arguments for the worker
        for result in pool.map(run_simulation_worker, tasks):
            results_summary.append(result)
            run_id, status = result
            if status == "Success":
                logging.info(f"Main: Noted success for run {run_id}")
            else:
                logging.warning(f"Main: Noted failure for run {run_id}: {status}")


    successful_runs = sum(1 for _, status in results_summary if status == "Success")
    failed_runs = num_runs - successful_runs
    logging.info(f"Completed all {num_runs} simulation tasks.")
    logging.info(f"Successful runs: {successful_runs}")
    logging.info(f"Failed runs: {failed_runs}")
    if failed_runs > 0:
        logging.warning("Some runs failed. Check logs for details.")

    logging.info(f"Per-run data saved to {output_path}")


if __name__ == "__main__":
    # Important for multiprocessing, especially on Windows, to protect the entry point.
    # This ensures that child processes spawned don't re-execute the main script's top-level code.

    parser = argparse.ArgumentParser(description="Run batch simulations")
    parser.add_argument("--config", default="config/model_config.yaml",
                      help="Path to configuration file")
    parser.add_argument("--num-runs", type=int, default=5,
                      help="Number of simulation runs")
    parser.add_argument("--output-dir", default="results/batch_simulations",
                      help="Output directory for results")
    args = parser.parse_args()
    
    run_batch_simulations(args.config, args.num_runs, args.output_dir) 