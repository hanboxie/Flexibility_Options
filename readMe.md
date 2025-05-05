# Flexibility Options Modeling Project

## Overview

This project implements and analyzes energy market models focused on managing imbalance risk using Flexibility Options (FO). It includes two primary optimization models:

1.  **Day-Ahead Flexibility Option (DAFO) Model:** Determines optimal day-ahead energy schedules, storage operation, and flexibility option procurement considering forecasted conditions.
2.  **Real-Time Simulation (RTSim) Model:** Simulates real-time market operations based on the day-ahead decisions and various real-time scenarios (e.g., renewable energy fluctuations) to assess the effectiveness of the flexibility options.

The goal is to evaluate the economic and operational impacts of introducing flexibility options in power systems.

## Reference

The modeling approach is based on or inspired by the concepts presented in:
*   `Flexibility Options_ A Proposed Product for Managing Imbalance Risk.pdf` (Included in the repository)

## File Structure

```
.
├── config/                     # Configuration files
│   └── model_config.yaml       # Main configuration (paths, model params, solver)
├── data/                       # Input data (CSV format expected)
│   ├── generator.csv           # Generator parameters
│   ├── storage.csv             # Storage parameters
│   ├── demand.csv              # Demand profiles
│   └── renewable/              # Directory for raw renewable scenarios/files
│   └── renewable_aggregated.csv # Processed/aggregated renewable data (output of preprocessing)
├── docs/                       # Project documentation (reports, etc.)
├── results/                    # Output files and results
│   └── results.xlsx            # Main results spreadsheet (margins, payoffs, metrics)
├── src/                        # Source code for models and processing
│   ├── DataProcessor.py        # Loads and preprocesses input data
│   ├── DAFOModel.py            # Pyomo definition for the Day-Ahead FO model
│   ├── RTSimModel.py           # Pyomo definition for the Real-Time Simulation model
│   ├── extract_da.py           # Extracts results from DA model for RT model input
│   ├── results_processing.py   # Functions for calculating metrics from model results
│   ├── aggregate_renewable_generation.py # Script to aggregate raw renewable data
│   └── util_plotting.py        # Plotting utility functions
├── .venv/                      # Python virtual environment files
├── .vscode/                    # VS Code editor settings
├── main_analysis.ipynb         # Jupyter Notebook orchestrating the main analysis workflow
├── vis.ipynb                   # Jupyter Notebook for visualizing results
├── original_paper.ipynb        # Jupyter Notebook related to the original paper's analysis/replication
├── main.py                     # Command-line script alternative for running the workflow
├── Flexibility Options_ A Proposed Product for Managing Imbalance Risk.pdf # Reference paper
├── .gitignore                  # Specifies intentionally untracked files that Git should ignore
├── .gitattributes              # Defines attributes per path for Git
└── readMe.md                   # This file
```

### Key Components:

*   **`main_analysis.ipynb`:** The primary Jupyter Notebook to run the full workflow: data loading, DAFO model run, RT model run, results processing, and saving.
*   **`main.py`:** A command-line script that performs the same workflow as `main_analysis.ipynb`. Useful for running the analysis without a notebook interface. Usage: `python main.py --config path/to/config.yaml --results-dir path/to/output`
<!-- *   **`vis.ipynb`:** Notebook dedicated to creating visualizations from the data in `results/results.xlsx`. -->
*   **`original_paper.ipynb`:** Notebook likely containing analysis or code related to the reference paper.
*   **`src/` Directory:** Contains modular Python code:
    *   `DataProcessor.py`: Loads CSV data and prepares it in a dictionary format for Pyomo models.
    *   `DAFOModel.py`: Defines the Pyomo `AbstractModel` for the DAFO optimization.
    *   `RTSimModel.py`: Defines the Pyomo `AbstractModel` for the RTSim optimization.
    *   `extract_da.py`: Extracts relevant data from the solved DA model instance.
    *   `results_processing.py`: Calculates various financial and operational metrics.
    *   `aggregate_renewable_generation.py`: Preprocesses renewable energy data.
    *   `util_plotting.py`: Plotting helper functions (if used).
*   **`config/model_config.yaml`:** Central configuration file for setting data paths, model parameters (periods, scenarios), and solver settings.
*   **`data/`:** Location for all input CSV files. Raw renewable data might reside in a subdirectory (`data/renewable/`) before being processed by `aggregate_renewable_generation.py`.
*   **`results/`:** Default directory where output files, especially `results.xlsx`, are saved.

## Setup & Usage

1.  **Environment:** Ensure you have a Python environment (e.g., using `conda` or `venv`) with the necessary packages installed (Pyomo, Pandas, NumPy, PyYAML, a compatible solver like GLPK, Gurobi, CPLEX, etc.). You might need to install dependencies listed in a `requirements.txt` file (if provided) or install them manually.
2.  **Configuration:** Update `config/model_config.yaml` with the correct paths to your data files and specify your desired solver and its options.
3.  **Run Analysis (Notebook):** Open and run the cells in `main_analysis.ipynb`.
4.  **Run Analysis (Script):** Execute `python main.py` from the terminal. You can specify a different config file or results directory using flags (see `--help`).
<!-- 5.  **Visualize:** After running the analysis, open and run `vis.ipynb` to generate plots. -->
