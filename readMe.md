# Flexibility Options Modeling Project

## Overview

This project implements and analyzes energy market models focused on managing imbalance risk using Flexibility Options (FO). It includes two primary optimization models:

1.  **Day-Ahead Flexibility Option (DAFO) Model:** Determines optimal day-ahead energy schedules, storage operation, and flexibility option procurement considering forecasted conditions.
2.  **Real-Time Simulation (RTSim) Model:** Simulates real-time market operations based on the day-ahead decisions and various real-time scenarios (e.g., renewable energy fluctuations) to assess the effectiveness of the flexibility options.

The goal is to evaluate the economic and operational impacts of introducing flexibility options in power systems.

## Reference

The modeling approach is based on the concepts presented in:
*   `Flexibility Options_ A Proposed Product for Managing Imbalance Risk.pdf` (Included in the repository)

## File Structure

```
.
├── config/
│   └── model_config.yaml       # Main configuration (paths, model params, solver)
├── data/
│   ├── FO_input_sectionV.csv   # Original Paper input data
│   ├── processed/
│   │   └── renewable.csv       # Processed renewable energy data
│   └── raw/
│       ├── gen.csv             # Generator parameters
│       ├── demand/             # Directory for demand profiles (structure inferred)
│       ├── renewable/          # Directory for raw renewable scenarios/files (structure inferred)
│       └── storage.csv         # Storage parameters
├── results/                    # Output files and results
├── src/
│   ├── data_utils/
│   │   ├── DataProcessor.py        # Loads and preprocesses input data
│   │   ├── scenario_generation.py  # Generates scenarios, possibly for renewable energy or demand
│   │   ├── extract_da.py           # Extracts results from Day-Ahead model for Real-Time model input
│   │   ├── results_processing.py   # Functions for calculating metrics from model results
│   │   └── util_plotting.py        # Plotting utility functions
│   └── models/
│       ├── DAFOModel.py            # Pyomo definition for the Day-Ahead Flexibility Option (DAFO) model
│       └── RTSimModel.py           # Pyomo definition for the Real-Time Simulation (RTSim) model
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
*   **`original_paper.ipynb`:** Analysis and code performed in the reference paper.
*   **`src/` Directory:** Contains the core modular Python code:
    *   `data_utils/`: Scripts for data handling.
        *   `DataProcessor.py`: Loads CSV data and prepares it in a dictionary format for Pyomo models.
        *   `scenario_generation.py`: Creates different renewable generation scenarios for simulation.
        *   `extract_da.py`: Passes data from the day-ahead stage to the real-time stage.
        *   `results_processing.py`: Calculates financial and operational metrics.
        *   `util_plotting.py`: Helper functions for plotting.
    *   `models/`: Contains the optimization model definitions.
        *   `DAFOModel.py`: Defines the Day-Ahead Flexibility Option optimization model.
        *   `RTSimModel.py`: Defines the Real-Time Simulation optimization model.
*   **`config/model_config.yaml`:** Central configuration file for setting data paths, model parameters, and solver settings.
*   **`data/`:** Contains all input data.
    *   `data/raw/`: Raw input files (generators, storage, demand, renewables).
    *   `data/processed/`: Processed data, like aggregated renewable scenarios.
*   **`results/`:** Intended directory for output files.

## Setup & Usage

1.  **Environment:** Ensure you have a Python environment (e.g., using `conda` or `venv`) with the necessary packages installed (Pyomo, Pandas, NumPy, PyYAML, a compatible solver like GLPK, Gurobi, CPLEX, etc.). You might need to install dependencies listed in a `requirements.txt` file (if provided) or install them manually.
2.  **Configuration:** Update `config/model_config.yaml` with the correct paths to your data files and specify your desired solver and its options.
3.  **Run Analysis (Notebook):** Open and run the cells in `main_analysis.ipynb`.
4.  **Run Analysis (Script):** Execute `python main.py` from the terminal. You can specify a different config file or results directory using flags (see `--help`).
<!-- 5.  **Visualize:** After running the analysis, open and run `vis.ipynb` to generate plots. -->
