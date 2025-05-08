import matplotlib.pyplot as plt
import pandas as pd

def plot_demand_and_renewables(data):
    """Plots both demand and renewable generation over time on the same figure."""
    if None in data and all(key in data[None] for key in ['DEMAND', 'RE', 'T', 'G']):
        demand_data = data[None]['DEMAND']
        re_data = data[None]['RE']
        time_periods = sorted(data[None]['T'][None])
        generators = sorted(data[None]['G'][None])
        
        # Create single figure
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # Plot demand
        demand_values = [demand_data.get(t, 0) for t in time_periods]
        ax.plot(time_periods, demand_values, 'k-', marker='o', label='Demand')
        ax.set_xlabel('Time Period')
        ax.set_ylabel('Power (MW)')
        
        # Plot renewable generation
        for g in generators:
            gen_values = [re_data.get((g, t), 0) for t in time_periods]
            if any(v > 0 for v in gen_values):
                ax.plot(time_periods, gen_values, marker='o', linestyle='-', label=f'Scenario {g}')
        
        ax.legend(loc='upper right')
        plt.title('Cumulative System Demand and Renewable Generation Over Time')
        plt.grid(True)
        plt.show()
    else:
        print("Could not find required data keys in the expected structure.")

def print_renewable_stats(data):
    """Calculates and prints statistics for renewable generation data."""
    if None in data and all(key in data[None] for key in ['RE', 'T', 'S']):
        re_data_dict = data[None]['RE']
        time_periods = sorted(data[None]['T'][None])
        scenarios = sorted(data[None]['S'][None]) # Assuming 'G' here refers to scenarios

        # Convert to DataFrame: rows=time_periods, columns=scenarios
        df_data = {}
        for s_idx, scenario in enumerate(scenarios):
            df_data[f"Scenario {scenario}"] = [re_data_dict.get((scenario, t), 0) for t in time_periods]
        
        re_df = pd.DataFrame(df_data, index=time_periods)
        re_df.index.name = "Time Period"

        if re_df.empty:
            print("No renewable energy data found to calculate statistics.")
            return

        print("\n--- Renewable Energy Statistics ---")

        # Mean and Std Dev per time period
        print("\nMean Renewable Generation per Time Period (across scenarios):")
        print(re_df.mean(axis=1))

        print("\nStandard Deviation of Renewable Generation per Time Period (across scenarios):")
        print(re_df.std(axis=1))

        # Correlation between scenarios
        print("\nCorrelation Matrix between Renewable Scenarios:")
        print("\nCHECK CORR IMPLEMENTATION")
        correlation_matrix = re_df.corr()
        print(correlation_matrix)
        
        print("\n-----------------------------------\n")

    else:
        print("Could not find required renewable data keys ('RE', 'T', 'G') in the expected structure for statistics.")