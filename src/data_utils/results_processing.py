import pandas as pd
import numpy as np
import pyomo.environ as pyo

def calculate_rt_margins(iRT, dataRT):
    """Calculates the Real-Time margins for each generator and scenario."""
    rt_margins_data = {}
    for s in iRT.S:
        for g in iRT.G_FO_sellers:
            for t in iRT.T:
                dual_value = iRT.dual[iRT.Con3[s, t]]
                vc_g = dataRT[None]["VC"].get(g)
                if vc_g is None:
                     print(f"Warning: VC not found for generator {g}. Skipping margin calculation for (s={s}, g={g}, t={t}).")
                     continue

                vc_component = iRT.prob[s] * vc_g
                gen_adjustment = iRT.xup[s, g, t].value - iRT.xdn[s, g, t].value

                margin = (dual_value - vc_component) * gen_adjustment
                rt_margins_data[(s, g, t)] = margin

    # Convert dictionary to a Series with MultiIndex (s, g, t)
    rt_margins_series = pd.Series(rt_margins_data)

    # Unstack to create DataFrame: Index (Generator, Time), Columns (Scenario)
    RTmargins = rt_margins_series.unstack(level=0)
    RTmargins.index.names = ['Generator', 'Time']

    # Adjust index if it starts from 0
    if not RTmargins.empty and RTmargins.index.get_level_values('Generator').min() == 0:
         RTmargins.index = pd.MultiIndex.from_tuples(
             [(g + 1, t) for g, t in RTmargins.index],
             names=['Generator', 'Time']
         )
    return RTmargins

def calculate_rt_payoffs(iRT, dataRT, df):
    """Calculates the Real-Time up and down flexibility offer payoffs."""
    up_payoffs_dict = {}
    dn_payoffs_dict = {}

    for s in iRT.S:
        # Calculate UP payoffs summed over time t
        if s < iRT.S.last(): # Ensure s is not the last scenario for UP payoffs
            current_up_payoffs = []
            for g in iRT.G_FO_sellers:
                total_payoff_g = 0
                for t in iRT.T:
                    mask = (df["R"] >= s) & (df["G"] == g) & (df["T"] == t)
                    if not mask.empty and len(df.loc[mask]) > 0:
                        hsu_sum_for_g = df.loc[mask, "hsu"].sum()
                        price_component = iRT.dual[iRT.Con3[s, t]] * hsu_sum_for_g
                        vcup_g = dataRT[None]["VCUP"].get(g)
                        if vcup_g is None:
                            print(f"Warning: VCUP not found for generator {g}. Skipping UP payoff for (s={s}, g={g}, t={t}).")
                            continue
                        cost_component = iRT.prob[s] * vcup_g * hsu_sum_for_g
                        payoff = -(price_component - cost_component)
                        total_payoff_g += payoff
                current_up_payoffs.append(total_payoff_g)
            up_payoffs_dict[f"UP{s}"] = current_up_payoffs

        # Calculate DN payoffs summed over time t
        if s > iRT.S.first(): # Ensure s is not the first scenario for DN payoffs
            current_dn_payoffs = []
            for g in iRT.G_FO_sellers:
                total_payoff_g = 0
                for t in iRT.T:
                    mask = (df["R"] < s) & (df["G"] == g) & (df["T"] == t)
                    if not mask.empty and len(df.loc[mask]) > 0:
                        hsd_sum_for_g = df.loc[mask, "hsd"].sum()
                        price_component = iRT.dual[iRT.Con3[s, t]] * hsd_sum_for_g
                        vcdn_g = dataRT[None]["VCDN"].get(g)
                        if vcdn_g is None:
                            print(f"Warning: VCDN not found for generator {g}. Skipping DN payoff for (s={s}, g={g}, t={t}).")
                            continue
                        cost_component = iRT.prob[s] * vcdn_g * hsd_sum_for_g
                        payoff = price_component - cost_component
                        total_payoff_g += payoff
                current_dn_payoffs.append(total_payoff_g)
            dn_payoffs_dict[f"DN{s}"] = current_dn_payoffs

    # Combine UP and DN payoffs into the RTpayoffs DataFrame
    RTpayoffs = pd.DataFrame({**up_payoffs_dict, **dn_payoffs_dict})
    # Check if RTpayoffs is empty before setting index
    if not RTpayoffs.empty:
        RTpayoffs.index = range(1, len(RTpayoffs) + 1) # Assume generators are 1-indexed
    return RTpayoffs


def calculate_system_metrics(iRT, dataRT, total_da):
    """Calculates overall system metrics like cost, price, unmet demand, and curtailment."""
    Total = pd.DataFrame()

    # Add DA metrics first
    Total.loc['average price', 'DA'] = total_da['price'].mean() if 'price' in total_da and not total_da['price'].empty else np.nan
    Total.loc['total cost', 'DA'] = total_da['cost'].sum() if 'cost' in total_da else np.nan
    Total.loc['unmet_demand', 'DA'] = np.nan # No unmet demand in DA
    Total.loc['curtail cost', 'DA'] = np.nan # No curtailment in DA


    for s in iRT.S:
        # RT Cost (summed over t)
        up_costs = sum(dataRT[None]["VCUP"].get(g, 0) * iRT.xup[s, g, t].value 
                      for g in iRT.G_FO_sellers for t in iRT.T)
        down_costs = sum(dataRT[None]["VCDN"].get(g, 0) * iRT.xdn[s, g, t].value 
                        for g in iRT.G_FO_sellers for t in iRT.T)
        # Note the sign change for down_costs as xdn is reduction
        Total.at['total cost', s] = iRT.prob[s] * (up_costs - down_costs)

        # RT Price (average price over time)
        prices_s = [iRT.dual[iRT.Con3[s, t]] for t in iRT.T]
        Total.at['average price', s] = np.mean(prices_s) if prices_s else np.nan

        # RT Unmet demand cost (summed over t)
        d1_val = dataRT[None]["D1"].get(None, 0)
        d2_val = dataRT[None]["D2"].get(None, 0)
        Total.at['unmet_demand', s] = iRT.prob[s] * sum(
            d1_val * iRT.d[s, t].value +
            d2_val * iRT.d[s, t].value**2
            for t in iRT.T
        )

        # RT Curtailment cost (summed over t)
        pendn_val = dataRT[None]["PENDN"].get(None, 0)
        Total.at['curtail cost', s] = iRT.prob[s] * sum(iRT.sdup[s, t].value * pendn_val for t in iRT.T)

    return Total


def calculate_premium_convergence(Gross_margins, RTpayoffs):
    """Calculates the convergence of flexibility premiums."""
    # Ensure RTpayoffs index matches Gross_margins if possible, assuming 1-based generator index
    if not Gross_margins.empty and not RTpayoffs.empty:
        RTpayoffs.index = Gross_margins.index

    premium_convergence = pd.DataFrame(index=Gross_margins.index)

    # Sum UP premiums and payoffs
    gross_up = Gross_margins.filter(like='up').sum(axis=1)
    rt_up = RTpayoffs.filter(like='UP').sum(axis=1)
    premium_convergence['UP'] = gross_up + rt_up

    # Sum DN premiums and payoffs
    gross_down = Gross_margins.filter(like='down').sum(axis=1)
    rt_dn = RTpayoffs.filter(like='DN').sum(axis=1)
    premium_convergence['DN'] = gross_down + rt_dn

    premium_convergence.index.name = 'Generator'
    return premium_convergence


def calculate_total_margins(iRT, dataRT, Gross_margins, RTmargins, RTpayoffs, premium_convergence, total_da):
    """Calculates the total margins for generators, RE, and DR."""
    # Aggregate RTmargins by generator
    if RTmargins.empty:
        RTmargins_gen = pd.DataFrame(index=Gross_margins.index) # Use Gross_margins index if RTmargins is empty
    else:
        RTmargins_gen = RTmargins.groupby(level='Generator').sum()

    # Ensure consistent indexing (assuming 1-based generator index)
    if not Gross_margins.empty:
        if RTmargins_gen.empty:
             RTmargins_gen = pd.DataFrame(0, index=Gross_margins.index, columns=iRT.S) # Create empty df with correct index/cols
        else:
            RTmargins_gen = RTmargins_gen.reindex(Gross_margins.index, fill_value=0)
        if not RTpayoffs.empty:
            RTpayoffs = RTpayoffs.reindex(Gross_margins.index, fill_value=0)
        else:
             RTpayoffs = pd.DataFrame(0, index=Gross_margins.index, columns=RTpayoffs.columns if not RTpayoffs.empty else [])


    Total_margin = pd.DataFrame(index=Gross_margins.index)

    # --- Generator Margins ---
    for s in iRT.S:
        s_col = s # Column name for the scenario

        # DA Margins (sum over tiers/time implicitly included in Gross_margins)
        # Need to handle potential empty Gross_margins
        if Gross_margins.empty:
             da_margins_s = pd.Series(0, index=Total_margin.index)
        else:
             da_margins_s = iRT.prob[s] * Gross_margins.sum(axis=1)


        # RT Margins for scenario s
        rt_margin_s = RTmargins_gen[s] if s in RTmargins_gen else pd.Series(0, index=Total_margin.index)

        # RT Payoffs for scenario s
        # Filter RTpayoffs for columns related to scenario s (e.g., UP{s}, DN{s})
        relevant_payoff_cols = [col for col in RTpayoffs.columns if str(s) in col]
        rt_payoffs_s = RTpayoffs[relevant_payoff_cols].sum(axis=1) if relevant_payoff_cols else pd.Series(0, index=Total_margin.index)

        # Align indexes before summation - crucial step
        da_margins_s = da_margins_s.reindex(Total_margin.index, fill_value=0)
        rt_margin_s = rt_margin_s.reindex(Total_margin.index, fill_value=0)
        rt_payoffs_s = rt_payoffs_s.reindex(Total_margin.index, fill_value=0)

        Total_margin[s_col] = da_margins_s + rt_margin_s + rt_payoffs_s


    # Add rows for 'RE' and 'DR' if they don't exist
    if 'RE' not in Total_margin.index:
        Total_margin.loc['RE'] = np.nan
    if 'DR' not in Total_margin.index:
        Total_margin.loc['DR'] = np.nan

    # --- RE and DR Margins ---
    da_price_mean = total_da['price'].mean() if 'price' in total_da and not total_da['price'].empty else 0

    for s in iRT.S:
        s_col = s

        # --- RE margin calculation for scenario s ---
        RE_rt_adjustment_value = sum(
            iRT.dual[iRT.Con3[s, t]] * (iRT.rgup[s, t].value - iRT.rgdn[s, t].value)
            for t in iRT.T
        )

        DA_RE_revenue = iRT.prob[s] * sum(
            dataRT[None]["REDA"].get(t, 0) * da_price_mean for t in iRT.T
        )

        # Total premium paid by RE (sum across all generators)
        # Need to handle empty premium_convergence
        if premium_convergence.empty:
             total_premiums = 0
        else:
             total_premiums = premium_convergence['UP'].sum() + premium_convergence['DN'].sum()

        # Subtract relevant RT payoffs made *to* RE from generators (this seems reversed in original logic?)
        # Sticking to the provided logic for now: Summing payoffs generators receive
        RE_rt_payoff_adjustment = 0
        if not RTpayoffs.empty:
            if f"DN{s}" in RTpayoffs.columns:
                RE_rt_payoff_adjustment += RTpayoffs[f"DN{s}"].sum()
            if f"UP{s}" in RTpayoffs.columns:
                 RE_rt_payoff_adjustment += RTpayoffs[f"UP{s}"].sum()


        RE_total = RE_rt_adjustment_value + DA_RE_revenue - iRT.prob[s] * total_premiums # - RE_rt_payoff_adjustment # Removed based on re-evaluating original formula's intent

        Total_margin.loc['RE', s_col] = RE_total

        # --- DR margin calculation for scenario s ---
        DR_rt_value = sum( iRT.dual[iRT.Con3[s, t]] * iRT.d[s, t].value for t in iRT.T)

        DA_DR_revenue = iRT.prob[s] * sum( dataRT[None]["DAdr"].get(t, 0) * da_price_mean for t in iRT.T)

        DR_cost = iRT.prob[s] * sum(
             dataRT[None]["D1"].get(None, 0) * (iRT.d[s, t].value + dataRT[None]["DAdr"].get(t, 0)) +
             dataRT[None]["D2"].get(None, 0) * (iRT.d[s, t].value + dataRT[None]["DAdr"].get(t, 0))**2
             for t in iRT.T
        )

        Total_margin.loc['DR', s_col] = DR_rt_value + DA_DR_revenue - DR_cost

    return Total_margin 