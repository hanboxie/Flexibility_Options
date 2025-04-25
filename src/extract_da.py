import pandas as pd
import numpy as np

def extract_da(i, pyomo_system_data):
    Energy = pd.DataFrame()

    # Modified Energy DataFrame creation
    energy_data = []
    for g in i.G:
        for t in i.T:
            energy_data.append({'g': g, 't': t, 'en': i.xDA[g, t].value})
    Energy = pd.DataFrame(energy_data).pivot(index='g', columns='t', values='en')

    E_grid_data = {(g): sum(i.xDA[g,t].value for t in i.T) for g in i.G}
    xDA_data = {(g,t): i.xDA[g,t].value for g in i.G for t in i.T}
    temp = {t: i.rgDA[t].value for t in i.T}
    
    Total = pd.DataFrame()
    Total['cost'] = {t: sum(i.VC[g] * i.xDA[g,t].value for g in i.G) for t in i.T}
    Total['price'] = {t: i.dual[i.Con3[t]] for t in i.T}
    
    E_grid_data = {(R): v.value for (R), v in i.hdu.items()}
    demand = pd.DataFrame.from_dict(E_grid_data, orient="index", columns=["hdu"])
    E_grid_data = {(R): v.value for (R), v in i.hdd.items()}
    demand['hdd'] = pd.DataFrame.from_dict(E_grid_data, orient="index", columns=["hdd"])
        
    hsu_data = {}
    hsd_data = {}
    for r in i.R:
        for g in i.G:
            for t in i.T:
                hsu_data[(r,g,t)] = i.hsu[r,g,t].value
                hsd_data[(r,g,t)] = i.hsd[r,g,t].value

    df = pd.DataFrame.from_dict(hsu_data, orient="index", columns=["hsu"])
    df['hsd'] = pd.DataFrame.from_dict(hsd_data, orient="index", columns=["hsd"])
    df['R'] = [k[0] for k in df.index]
    df['G'] = [k[1] for k in df.index]
    df['T'] = [k[2] for k in df.index]
    
    # Initialize empty lists to store prices
    up_prices = []
    down_prices = []

    # Collect prices for each time period and reserve tier
    for t in i.T:
        for r in i.R:
            up_prices.append(i.dual[i.Con4UP[r,t]])
            down_prices.append(i.dual[i.Con4DN[r,t]])

    # Create a temporary long-format DataFrame
    Prices_long = pd.DataFrame({
        'up': up_prices,
        'down': down_prices,
        'T': [t for t in i.T for r in i.R],  # repeat each time period for each reserve tier
        'R': [r for t in i.T for r in i.R]   # repeat reserve tiers for each time period
    })

    # Pivot the table to wide format
    Prices = Prices_long.pivot_table(index='T', columns='R', values=['up', 'down'])

    # Flatten the MultiIndex columns for better readability
    Prices.columns = [f'{val}_R{col}' for val, col in Prices.columns]

    # Reset index to make 'T' a regular column if needed, or keep it as index
    # Prices = Prices.reset_index() # Optional: Uncomment if you want T as a column

    # Calculate Gross Margins per generator
    Gross_margins = pd.DataFrame(index=i.G)

    # Calculate energy margins per generator
    energy_margins = {}
    for g in i.G:
        margin = sum((i.dual[i.Con3[t]] - i.VC[g]) * i.xDA[g, t].value for t in i.T)
        energy_margins[g] = margin
    Gross_margins["en"] = pd.Series(energy_margins)

    # Calculate reserve margins per generator and tier
    reserve_margins_up = {}
    # reserve_margins_down = {} # Uncomment if down-reserve margins are needed
    vcup_values = {g: i.VCUP[g] for g in i.G}  # Use dictionary for easy lookup
    # vcdn_values = {g: i.VCDN[g] for g in i.G} # Uncomment if needed

    # Pre-filter hsu/hsd data by generator and tier for efficiency
    df_indexed = df.set_index(['G', 'R', 'T'])

    for g in i.G:
        for r in i.R: # Assuming i.R contains the tiers, e.g., [1, 2, 3, 4]
            total_up_margin_gr = 0
            # total_down_margin_gr = 0 # Uncomment if needed

            for t in i.T:
                try:
                    price_up = Prices.loc[t, f'up_R{r}']
                    # price_down = Prices.loc[t, f'down_R{r}'] # Uncomment if needed

                    hsu_value = df_indexed.loc[(g, r, t), "hsu"]
                    # hsd_value = df_indexed.loc[(g, r, t), "hsd"] # Uncomment if needed

                    # Calculate margin for this time period
                    cost_up_component = vcup_values[g] * i.probTU[r] # Assuming i.probTU is indexed by tier r
                    total_up_margin_gr += hsu_value * (price_up - cost_up_component)

                    # Add down margin calculation if necessary
                    # cost_down_component = vcdn_values[g] * i.probTD[r] # Assuming i.probTD exists
                    # total_down_margin_gr += hsd_value * (price_down - cost_down_component) # Check margin formula for down reserves

                except KeyError:
                    # Handle cases where data might be missing for a specific g, r, t combination
                    # print(f"Warning: Missing data for g={g}, r={r}, t={t} in margin calculation.")
                    pass # Or add 0, or handle as appropriate

            reserve_margins_up[(g, f'up_R{r}')] = total_up_margin_gr
            # reserve_margins_down[(g, f'down_R{r}')] = total_down_margin_gr # Uncomment if needed

    # Convert the dictionaries to DataFrames and join with Gross_margins
    Reserve_Margins_Up_df = pd.Series(reserve_margins_up).unstack()
    Gross_margins = Gross_margins.join(Reserve_Margins_Up_df)

    # If calculating down margins:
    # Reserve_Margins_Down_df = pd.Series(reserve_margins_down).unstack()
    # Gross_margins = Gross_margins.join(Reserve_Margins_Down_df)

    # Extract storage decisions from DA stage
    p_ch_DA_data = {(b,t): i.p_ch[b,t].value for b in i.B for t in i.T}
    p_dch_DA_data = {(b,t): i.p_dch[b,t].value for b in i.B for t in i.T}

    dataRT = {None:{
        'RE': pyomo_system_data[None]["RE"],
        'CAP': pyomo_system_data[None]["CAP"],
        'VC': pyomo_system_data[None]["VC"],
        'VCUP': pyomo_system_data[None]["VCUP"],
        'VCDN': pyomo_system_data[None]["VCDN"],
        'DEMAND': pyomo_system_data[None]["DEMAND"],
        'D1': pyomo_system_data[None]["D1"],
        'D2': pyomo_system_data[None]["D2"],
        'prob':{1: 0.2, 2:0.2, 3:0.2, 4:0.2, 5:0.2},
        'RR': pyomo_system_data[None]["RR"],
        'xDA':xDA_data,
        'PEN':pyomo_system_data[None]["PEN"],
        'PENDN':pyomo_system_data[None]["PENDN"],
        'REDA': temp,
        'DAdr': {t: i.d[t].value for t in i.T},
    }}
    
    storage_params = {}
    if len(i.B) > 0:
        storage_params = {
            'E_MAX': pyomo_system_data[None]["E_MAX"],
            'P_MAX': pyomo_system_data[None]["P_MAX"],
            'ETA_CH': pyomo_system_data[None]["ETA_CH"],
            'ETA_DCH': pyomo_system_data[None]["ETA_DCH"],
            'STORAGE_COST': pyomo_system_data[None]["STORAGE_COST"],
            'E0': pyomo_system_data[None]["E0"],
            'E_FINAL': pyomo_system_data[None]["E_FINAL"],
            'p_ch_DA': p_ch_DA_data,
            'p_dch_DA': p_dch_DA_data
        }
        dataRT[None].update(storage_params)
    
    # Return additional data along with dataRT
    return dataRT, Total, df, demand, Energy, Prices, Gross_margins