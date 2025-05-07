import matplotlib.pyplot as plt

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