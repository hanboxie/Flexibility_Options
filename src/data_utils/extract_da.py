import pandas as pd
import numpy as np

def extract_da(i, pyomo_system_data):
    energy_data = []
    for g in i.G_FO_sellers:
        for t in i.T:
            energy_data.append({'g': g, 't': t, 'en': i.xDA[g, t].value})
    Energy = pd.DataFrame(energy_data).pivot(index='g', columns='t', values='en')

    xDA_data = {(g,t): i.xDA[g,t].value for g in i.G_FO_sellers for t in i.T}
    rgDA_data = {t: i.rgDA[t].value for t in i.T}
    
    Total = pd.DataFrame()
    Total['cost'] = {t: sum(i.VC[g] * i.xDA[g,t].value for g in i.G_FO_sellers) for t in i.T}
    Total['price'] = {t: i.dual[i.Con3[t]] for t in i.T}
    
    # Extract demand FO data
    hdu_data = {(R): v.value for (R), v in i.hdu.items()}
    demand = pd.DataFrame.from_dict(hdu_data, orient="index", columns=["hdu"])
    hdd_data = {(R): v.value for (R), v in i.hdd.items()}
    demand['hdd'] = pd.DataFrame.from_dict(hdd_data, orient="index", columns=["hdd"])
        
    hsu_data = {}
    hsd_data = {}
    
    print("Extracting hsu and hsd data...")
    try:
        for r in i.R:
            for g in i.G_FO_sellers:  # Use G_FO_sellers instead of G
                for t in i.T:
                    hsu_data[(r,g,t)] = i.hsu[r,g,t].value
                    hsd_data[(r,g,t)] = i.hsd[r,g,t].value
    except Exception as e:
        print(f"Error extracting hsu/hsd data: {e}")
        return None, None, None, None, None, None, None

    df = pd.DataFrame.from_dict(hsu_data, orient="index", columns=["hsu"])
    df['hsd'] = pd.DataFrame.from_dict(hsd_data, orient="index", columns=["hsd"])
    df['R'] = [k[0] for k in df.index]
    df['G'] = [k[1] for k in df.index]
    df['T'] = [k[2] for k in df.index]
    
    up_prices = []
    down_prices = []
    time_periods = []
    reserve_tiers = []

    for t in i.T:
        for r in i.R:
            try:
                up_prices.append(i.dual[i.Con4UP[r,t]])
                down_prices.append(i.dual[i.Con4DN[r,t]])
                time_periods.append(t)
                reserve_tiers.append(r)
            except Exception as e:
                print(f"Error extracting price data for r={r}, t={t}: {e}")
                up_prices.append(0)
                down_prices.append(0)
                time_periods.append(t)
                reserve_tiers.append(r)

    Prices_long = pd.DataFrame({
        'up': up_prices,
        'down': down_prices,
        'T': time_periods,
        'R': reserve_tiers
    })
    Prices = Prices_long.pivot_table(index='T', columns='R', values=['up', 'down'])
    Prices.columns = [f'{val}_R{col}' for val, col in Prices.columns]

    # Calculate gross margins
    Gross_margins = pd.DataFrame(index=i.G_FO_sellers)

    # Energy margins
    energy_margins = {}
    for g in i.G_FO_sellers:
        margin = sum((i.dual[i.Con3[t]] - i.VC[g]) * i.xDA[g, t].value for t in i.T)
        energy_margins[g] = margin
    Gross_margins["en"] = pd.Series(energy_margins)

    # FO margins - only for sellers
    reserve_margins_up = {}
    vcup_values = {g: i.VCUP[g] for g in i.G_FO_sellers}
    df_indexed = df.set_index(['G', 'R', 'T'])

    for g in i.G_FO_sellers:
        for r in i.R:
            total_up_margin_gr = 0
            for t in i.T:
                try:
                    price_up = Prices.loc[t, f'up_R{r}']
                    # Check if this combination exists in the data
                    if (g, r, t) in df_indexed.index:
                        hsu_value = df_indexed.loc[(g, r, t), "hsu"]
                        cost_up_component = vcup_values[g] * i.probTU[r]
                        total_up_margin_gr += hsu_value * (price_up - cost_up_component)
                except (KeyError, ValueError) as e:
                    # Skip if data is missing
                    pass

            reserve_margins_up[(g, f'up_R{r}')] = total_up_margin_gr

    # Convert the margins to DataFrame and join
    if reserve_margins_up:
        Reserve_Margins_Up_df = pd.Series(reserve_margins_up).unstack()
        Gross_margins = Gross_margins.join(Reserve_Margins_Up_df, how='left')
    
    # Fill NaN values with 0
    Gross_margins = Gross_margins.fillna(0)

    # Extract storage data if available
    p_ch_DA_data = {(b,t): i.p_ch[b,t].value for b in i.B for t in i.T}
    p_dch_DA_data = {(b,t): i.p_dch[b,t].value for b in i.B for t in i.T}

    # Create dataRT for RT model
    dataRT = {None:{
        'RE': pyomo_system_data[None]["RE"],
        'CAP': pyomo_system_data[None]["CAP"],
        'VC': pyomo_system_data[None]["VC"],
        'VCUP': pyomo_system_data[None]["VCUP"],
        'VCDN': pyomo_system_data[None]["VCDN"],
        'DEMAND': pyomo_system_data[None]["DEMAND"],
        'D1': pyomo_system_data[None]["D1"],
        'D2': pyomo_system_data[None]["D2"],
        'flag': pyomo_system_data[None].get("flag", {}),  # Include flag for G_FO_sellers in RT
        'prob': {s: 1.0/len(i.S) for s in i.S},  # Equal probability by default
        'RR': pyomo_system_data[None]["RR"],
        'xDA': xDA_data,
        'PEN': pyomo_system_data[None]["PEN"],
        'PENDN': pyomo_system_data[None]["PENDN"],
        'REDA': rgDA_data,
        'DAdr': {t: i.d[t].value for t in i.T},
    }}
    
    # Add storage parameters if storage exists
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
    
    return dataRT, Total, df, demand, Energy, Prices, Gross_margins