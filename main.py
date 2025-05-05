import pyomo.environ as pyo
import pandas as pd
import numpy as np
import yaml
import sys
import os
import argparse
import logging

# Add src directory to Python path
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
from data_utils.aggregate_renewable_generation import aggregate_renewable_generation

def setup_logging():
    """Configures logging for the script."""
    logging.basicConfig(level=logging.INFO, 
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        handlers=[logging.StreamHandler(sys.stdout)]) # Log to stdout

def load_config(config_path):
    """Loads the YAML configuration file."""
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        logging.info(f"Configuration loaded from {config_path}")
        return config
    except FileNotFoundError:
        logging.error(f"Configuration file not found: {config_path}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error loading configuration: {e}")
        sys.exit(1)

def ensure_dir_exists(path):
    """Creates a directory if it doesn't exist."""
    os.makedirs(path, exist_ok=True)
    logging.debug(f"Ensured directory exists: {path}")

def preprocess_data(config):
    """Loads and preprocesses data using DataProcessor."""
    paths = config['data_paths']
    general_cfg = config['general']
    
    # Ensure processed data directory exists
    processed_data_dir = os.path.dirname(paths['renewable_csv'])
    ensure_dir_exists(processed_data_dir)

    # Aggregate renewable generation if needed
    renewable_output_file = paths['renewable_csv']
    if not os.path.exists(renewable_output_file):
        logging.info("Aggregating renewable generation data...")
        # Assuming raw renewable data is in a dir relative to the CSV paths
        raw_renewable_dir = os.path.join(os.path.dirname(paths['generator_csv']), 'renewable') 
        aggregate_renewable_generation(
            input_dir=raw_renewable_dir, # Adjust if raw path is different
            output_file=renewable_output_file,
            num_scenarios=general_cfg['num_scenarios']
        )
        logging.info(f"Aggregated renewable data saved to {renewable_output_file}")
    else:
        logging.info(f"Using existing aggregated renewable data: {renewable_output_file}")

    # Prepare data for Pyomo
    logging.info("Processing system data...")
    system_data = DataProcessor(
        paths['generator_csv'], 
        paths['storage_csv'], 
        paths['demand_csv'], 
        paths['renewable_csv']
    )
    
    # DataProcessor.load_data is called within prepare_pyomo_data if needed
    pyomo_system_data = system_data.prepare_pyomo_data(config)
    
    if pyomo_system_data is None:
        logging.error("Failed to prepare Pyomo data.")
        sys.exit(1)
        
    logging.info("System data processed successfully.")
    return pyomo_system_data, system_data # Return system_data if needed later

def run_da_model(config, pyomo_system_data):
    """Instantiates and solves the DAFO model."""
    logging.info("Setting up and solving Day-Ahead (DAFO) model...")
    dafo_model = DAFOModel(config)
    da_instance = dafo_model.create_instance(pyomo_system_data)

    solver_cfg = config['solver']
    solver_name = solver_cfg['name']
    solver_exec = solver_cfg.get('executable')
    solver_options = solver_cfg.get('options', {})
    
    opt = pyo.SolverFactory(solver_name, executable=solver_exec)
    
    # Add options if provided
    for key, value in solver_options.items():
        if key != 'tee': # tee handled separately
            opt.options[key] = value
            
    result = opt.solve(da_instance, tee=solver_options.get('tee', False))

    # Basic check of solver status
    if (result.solver.status == pyo.SolverStatus.ok) and \
       (result.solver.termination_condition == pyo.TerminationCondition.optimal):
        logging.info("DAFO model solved successfully.")
    else:
        logging.warning(f"DAFO model solved with status: {result.solver.status}, condition: {result.solver.termination_condition}")
        # Optionally exit or handle non-optimal solutions
        # sys.exit(1) 

    return da_instance, opt # Return solver for reuse

def run_rt_model(config, dataRT, solver):
    """Instantiates and solves the RTSim model."""
    logging.info("Setting up and solving Real-Time (RTSim) model...")
    rt_sim_model = RTSimModel(config) 
    rt_instance = rt_sim_model.create_instance(dataRT)
    
    solver_options = config['solver'].get('options', {})
    result = solver.solve(rt_instance, tee=solver_options.get('tee', False))

    # Basic check of solver status
    if (result.solver.status == pyo.SolverStatus.ok) and \
       (result.solver.termination_condition == pyo.TerminationCondition.optimal):
        logging.info("RTSim model solved successfully.")
    else:
        logging.warning(f"RTSim model solved with status: {result.solver.status}, condition: {result.solver.termination_condition}")
        # sys.exit(1)

    return rt_instance

def process_and_save_results(da_instance, rt_instance, pyomo_system_data, dataRT, config, results_dir="results"):
    """Extracts results, calculates metrics, and saves to Excel."""
    logging.info("Processing and saving results...")
    ensure_dir_exists(results_dir)
    output_excel_path = os.path.join(results_dir, "results.xlsx")

    # Extract DA results needed for RT data prep and final results
    logging.debug("Extracting DA results...")
    # Note: dataRT was already created for run_rt_model input, but extract_da returns more.
    # We might need to adjust extract_da or how dataRT is handled if extract_da does more than just prepare dataRT.
    # For now, assume extract_da provides necessary outputs beyond just dataRT preparation.
    dataRT_extract, total_da, df, demand, Energy, Prices, Gross_margins = extract_da(da_instance, pyomo_system_data)
    
    # We passed `dataRT` (prepared outside) to run_rt_model. Ensure consistency or refactor extract_da.
    # If `dataRT_extract` is identical to the `dataRT` passed to `run_rt_model`, we can simplify.
    # Let's assume for now `dataRT` passed to `run_rt_model` was sufficient and generated by similar logic as in extract_da.

    logging.debug("Calculating RT metrics...")
    RTmargins = calculate_rt_margins(rt_instance, dataRT) 
    RTpayoffs = calculate_rt_payoffs(rt_instance, dataRT, df) 
    Total = calculate_system_metrics(rt_instance, dataRT, total_da) 
    premium_convergence = calculate_premium_convergence(Gross_margins, RTpayoffs)
    Total_margin = calculate_total_margins(rt_instance, dataRT, Gross_margins, RTmargins, RTpayoffs, premium_convergence, total_da)

    logging.info(f"Saving results to {output_excel_path}...")
    try:
        with pd.ExcelWriter(output_excel_path) as writer:
            RTmargins.to_excel(writer, sheet_name='RT Margins')
            RTpayoffs.to_excel(writer, sheet_name='RT Payoffs')
            Total.to_excel(writer, sheet_name='System Metrics')
            premium_convergence.to_excel(writer, sheet_name='Premium Convergence')
            Total_margin.to_excel(writer, sheet_name='Total Margins')
            df.to_excel(writer, sheet_name='FO Supply AWARDS')
            demand.to_excel(writer, sheet_name='FO Demand AWARDS')
            Energy.to_excel(writer, sheet_name='DA Energy')
            Prices.to_excel(writer, sheet_name='DA Prices')
        logging.info("Results saved successfully.")
    except Exception as e:
        logging.error(f"Error saving results to Excel: {e}")

def main():
    """Main execution function."""
    setup_logging()

    parser = argparse.ArgumentParser(description="Run DAFO and RTSim models.")
    parser.add_argument("--config", default="config/model_config.yaml", 
                        help="Path to the configuration YAML file.")
    parser.add_argument("--results-dir", default="results",
                        help="Directory to save output results.")
    args = parser.parse_args()

    config = load_config(args.config)
    
    pyomo_system_data, _ = preprocess_data(config) # system_data object ignored for now
    
    da_instance, solver = run_da_model(config, pyomo_system_data)
    
    # Prepare data for RT model (extract_da seems to do this)
    # This part might need refinement depending on exact role of extract_da
    # We need the specific `dataRT` structure required by RTSimModel.create_instance
    # Assuming extract_da also provides this as its first return value:
    dataRT, _, _, _, _, _, _ = extract_da(da_instance, pyomo_system_data) 
    
    rt_instance = run_rt_model(config, dataRT, solver)
    
    process_and_save_results(da_instance, rt_instance, pyomo_system_data, dataRT, config, args.results_dir)

    logging.info("Analysis complete.")

if __name__ == "__main__":
    main() 