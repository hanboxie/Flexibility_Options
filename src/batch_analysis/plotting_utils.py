import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import logging
from pathlib import Path

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()] # Use StreamHandler without sys.stdout for notebooks
    )

def plot_generation_cost_scatter(
    summary_df_or_path,
    x_col='mean_renewable_generation',
    y_col='sum_total_cost',
    size_col='mean_scenario_std_renewable_generation',
    hue_col='mean_scenario_std_renewable_generation', # Can be different or None
    run_id_col='run_id',
    plot_title='System Cost vs. Mean Renewable Generation',
    xlabel='Mean Renewable Generation (MWh)',
    ylabel='Sum of Total Costs ($)',
    sizes=(50, 500),
    palette="viridis_r",
    figsize=(12, 8),
    annotate_points=False,
    save_path=None
):
    """
    Generates a scatter plot from summary data.

    Args:
        summary_df_or_path (pd.DataFrame or str): DataFrame containing the summary data or path to the CSV file.
        x_col (str): Column name for the x-axis.
        y_col (str): Column name for the y-axis.
        size_col (str): Column name for sizing the scatter points.
        hue_col (str): Column name for coloring the scatter points. Can be None.
        run_id_col (str): Column name for run identifiers, used if annotate_points is True.
        plot_title (str): Title of the plot.
        xlabel (str): Label for the x-axis.
        ylabel (str): Label for the y-axis.
        sizes (tuple): Min and max size for scatter points.
        palette (str): Color palette for the hue.
        figsize (tuple): Figure size.
        annotate_points (bool): Whether to annotate points with run_id.
        save_path (str, optional): Path to save the figure. If None, figure is shown.
    """
    setup_logging()

    if isinstance(summary_df_or_path, str):
        try:
            df_summary = pd.read_csv(summary_df_or_path)
            logging.info(f"Successfully loaded data from {summary_df_or_path}")
        except FileNotFoundError:
            logging.error(f"Error: The file {summary_df_or_path} was not found.")
            return
        except Exception as e:
            logging.error(f"An error occurred while loading {summary_df_or_path}: {e}")
            return
    elif isinstance(summary_df_or_path, pd.DataFrame):
        df_summary = summary_df_or_path.copy()
        logging.info("Using provided DataFrame for plotting.")
    else:
        logging.error("Invalid input for summary_df_or_path. Must be a DataFrame or file path string.")
        return

    required_cols = [x_col, y_col]
    if size_col:
        required_cols.append(size_col)
    if hue_col:
        required_cols.append(hue_col)
    if annotate_points:
        required_cols.append(run_id_col)
        
    if not all(col in df_summary.columns for col in required_cols if col is not None):
        missing = [col for col in required_cols if col not in df_summary.columns and col is not None]
        logging.error(f"One or more required columns missing in the DataFrame. Missing: {missing}")
        logging.info(f"Available columns: {df_summary.columns.tolist()}")
        return

    plt.figure(figsize=figsize)
    
    plot_kwargs = {'data': df_summary, 'x': x_col, 'y': y_col}
    if size_col:
        plot_kwargs['size'] = size_col
        plot_kwargs['sizes'] = sizes
    if hue_col:
        plot_kwargs['hue'] = hue_col
        plot_kwargs['palette'] = palette
        
    scatter_plot = sns.scatterplot(**plot_kwargs)

    if annotate_points and run_id_col in df_summary.columns:
        for i, point in df_summary.iterrows():
            try:
                x_val = point[x_col]
                y_val = point[y_col]
                label = point[run_id_col]
                if pd.notna(x_val) and pd.notna(y_val): # Ensure values are not NaN before plotting text
                     scatter_plot.text(x_val + (df_summary[x_col].max() * 0.01), # Small offset
                                      y_val,
                                      str(label),
                                      fontdict={'size': 8})
            except KeyError as e:
                logging.warning(f"KeyError while trying to annotate point {i}: {e}. Skipping annotation for this point.")
            except Exception as e:
                logging.warning(f"General error while annotating point {i} ({label}): {e}. Skipping.")


    plt.title(plot_title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.grid(True)

    # Customize legend
    handles, labels = scatter_plot.get_legend_handles_labels()
    
    # Attempt to make legend titles more descriptive if hue and size are the same column
    if hue_col and size_col and hue_col == size_col:
        # Find and update the legend title for the combined hue/size aesthetic
        # This often involves finding the label that matches `hue_col` (or `size_col`)
        try:
            idx_to_rename = [i for i, l in enumerate(labels) if l == hue_col][0]
            labels[idx_to_rename] = f"{hue_col} (Color & Size)"
        except IndexError:
            # If the exact label name isn't found, we might need a more robust way or just use a generic title
             pass # logging.debug(f"Could not find '{hue_col}' in legend labels to rename.")
        plt.legend(handles=handles, labels=labels, title=hue_col if hue_col else "Legend")
    elif handles: # Only create legend if there are handles
        plt.legend(handles=handles, labels=labels, title="Legend")
    else: # No legend items
        if scatter_plot.get_legend() is not None:
            scatter_plot.get_legend().remove()


    plt.tight_layout()

    if save_path:
        try:
            plt.savefig(save_path, bbox_inches='tight')
            logging.info(f"Plot saved to {save_path}")
        except Exception as e:
            logging.error(f"Failed to save plot to {save_path}: {e}")
    else:
        plt.show() 