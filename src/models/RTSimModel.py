import pyomo.environ as pyo

class RTSimModel:
    def __init__(self, config):
        self.config = config
        if config['benchmark']:
            self.num_periods = 2
            self.num_scenarios = 5
            self.num_generators = 5
            self.num_tiers = 4
            self.num_storage = 0
        else:
            general_cfg = config['general']
            self.num_periods = general_cfg['num_periods']
            self.num_scenarios = general_cfg['num_scenarios']
            self.num_generators = general_cfg['num_generators']
            self.num_tiers = general_cfg['num_tiers']
            self.num_storage = general_cfg['num_storage']
        
        self.model = pyo.AbstractModel()
        self._define_sets()
        self._define_parameters()
        self._define_variables()
        self._define_objective()
        self._define_constraints()

    def _define_sets(self):
        self.model.T = pyo.RangeSet(1, self.num_periods)    # Set of time periods
        self.model.S = pyo.RangeSet(1, self.num_scenarios)  # Set of scenarios
        
        # Generator set
        if self.num_generators > 0:
            self.model.G = pyo.RangeSet(1, self.num_generators)
        else:
            self.model.G = pyo.Set(initialize=[])
        
        # Storage set
        if self.num_storage > 0:
            self.model.B = pyo.RangeSet(1, self.num_storage)
        else:
            self.model.B = pyo.Set(initialize=[])
            
    def _define_parameters(self):
        # Original Parameters
        self.model.VC = pyo.Param(self.model.G)           # Variable cost
        self.model.VCUP = pyo.Param(self.model.G)         # Variable cost up
        self.model.VCDN = pyo.Param(self.model.G)         # Variable cost down
        self.model.CAP = pyo.Param(self.model.G)          # Generator capacity
        self.model.RR = pyo.Param(self.model.G)           # Ramp rate

        self.model.prob = pyo.Param(self.model.S)         # Scenario probability
        self.model.RE = pyo.Param(self.model.S, self.model.T)  # Renewable generation by scenario and time
        self.model.DEMAND = pyo.Param(self.model.T)       # Hourly demand
        self.model.D1 = pyo.Param(within=pyo.NonNegativeIntegers)  # Linear demand cost coefficient
        self.model.D2 = pyo.Param(within=pyo.NonNegativeIntegers)  # Quadratic demand cost coefficient
        self.model.xDA = pyo.Param(self.model.G, self.model.T) # DA schedule by generator and time
        self.model.REDA = pyo.Param(self.model.T)         # DA renewable schedule by time
        self.model.PEN = pyo.Param(within=pyo.NonNegativeIntegers)   # Upward penalty
        self.model.PENDN = pyo.Param()                    # Downward penalty
        self.model.DAdr = pyo.Param(self.model.T)         # DA demand response by time

        # Storage Parameters
        self.model.E_MAX = pyo.Param(self.model.B)        # Maximum energy capacity
        self.model.P_MAX = pyo.Param(self.model.B)        # Maximum power capacity
        self.model.ETA_CH = pyo.Param(self.model.B)       # Charging efficiency
        self.model.ETA_DCH = pyo.Param(self.model.B)      # Discharging efficiency
        self.model.E0 = pyo.Param(self.model.B)           # Initial state of charge
        self.model.STORAGE_COST = pyo.Param(self.model.B)  # Operating cost per MWh of throughput
        self.model.E_FINAL = pyo.Param(self.model.B)      # Required final state of charge
        self.model.VCUP_B = pyo.Param(self.model.B, default=1.0)   # FO Up cost for storage
        self.model.VCDN_B = pyo.Param(self.model.B, default=1.0)   # FO Down cost (benefit) for storage

        # Storage DA parameters
        self.model.e_DA = pyo.Param(self.model.B, self.model.T)  # DA energy level
        self.model.p_ch_DA = pyo.Param(self.model.B, self.model.T)  # DA charging
        self.model.p_dch_DA = pyo.Param(self.model.B, self.model.T)  # DA discharging
    
    def _define_variables(self):
        # Variables that depend on generators
        # RT adjustment variables for each scenario and time
        self.model.xup = pyo.Var(self.model.S, self.model.G, self.model.T, domain=pyo.NonNegativeReals)  # Generator up adjustment
        self.model.xdn = pyo.Var(self.model.S, self.model.G, self.model.T, domain=pyo.NonNegativeReals)  # Generator down adjustment
        
        # Variables independent of generators and storage
        self.model.d = pyo.Var(self.model.S, self.model.T)     # RT demand response
        self.model.rgup = pyo.Var(self.model.S, self.model.T, domain=pyo.NonNegativeReals)  # RE up adjustment
        self.model.rgdn = pyo.Var(self.model.S, self.model.T, domain=pyo.NonNegativeReals)  # RE down adjustment
        self.model.sdup = pyo.Var(self.model.S, self.model.T, domain=pyo.NonNegativeReals)  # Shortage
        self.model.sddn = pyo.Var(self.model.S, self.model.T, domain=pyo.NonNegativeReals)  # Surplus

        # Variables that depend on storage
        # Storage Variables
        self.model.e = pyo.Var(self.model.S, self.model.B, self.model.T, domain=pyo.NonNegativeReals)     # Energy level
        self.model.p_ch = pyo.Var(self.model.S, self.model.B, self.model.T, domain=pyo.NonNegativeReals)  # Charging power
        self.model.p_dch = pyo.Var(self.model.S, self.model.B, self.model.T, domain=pyo.NonNegativeReals) # Discharging power
        self.model.b_up = pyo.Var(self.model.S, self.model.B, self.model.T, domain=pyo.NonNegativeReals)  # Storage up adjustment
        self.model.b_dn = pyo.Var(self.model.S, self.model.B, self.model.T, domain=pyo.NonNegativeReals)  # Storage down adjustment
    
    def _define_objective(self):
        # Objective Function
        def obj_expression(m):
            return sum(
                m.prob[s] * (
                    # Generator adjustment costs over time
                    sum(m.VCUP[g] * m.xup[s, g, t] - m.VCDN[g] * m.xdn[s, g, t]
                        for g in m.G for t in m.T)

                    # Penalty costs over time
                    + m.PENDN * sum(m.sdup[s, t] for t in m.T)
                    + m.PEN * sum(m.sddn[s, t] for t in m.T)

                    # Demand response cost (quadratic) minus base
                    + sum(m.D1 * (m.DAdr[t] + m.d[s, t]) + m.D2 * (m.DAdr[t] + m.d[s, t]) ** 2 for t in m.T)
                    - sum(m.D1 * m.DAdr[t] + m.D2 * m.DAdr[t] ** 2 for t in m.T)

                    # Optional storage throughput cost
                    + sum(m.STORAGE_COST[b] * (m.p_ch[s, b, t] + m.p_dch[s, b, t]) for b in m.B for t in m.T)
                    
                    # FO settlement/activation
                    + sum(m.VCUP_B[b] * m.b_up[s,b,t] - m.VCDN_B[b] * m.b_dn[s,b,t] for b in m.B for t in m.T)
                )
                for s in m.S
            )

        self.model.OBJ = pyo.Objective(rule=obj_expression, sense=pyo.minimize)
    
    def _define_constraints(self):
        # RT energy balance for each scenario and time period
        def RT_energy_balance(model, s, t):
            gen_adjustment = sum(model.xup[s,g,t] - model.xdn[s,g,t] for g in model.G)
            storage_adjustment = sum(
                model.p_dch[s,b,t] - model.p_ch[s,b,t] - 
                model.p_dch_DA[b,t] + model.p_ch_DA[b,t] for b in model.B
            )
            
            return (gen_adjustment +
                    model.rgup[s,t] - model.rgdn[s,t] +
                    storage_adjustment +
                    model.d[s,t] == 0)
                    
        self.model.Con3 = pyo.Constraint(self.model.S, self.model.T, rule=RT_energy_balance)

        # RT renewable availability
        def RT_RE_availability(model, s, t):
            return (model.rgup[s,t] - model.rgdn[s,t] + model.sdup[s,t] - model.sddn[s,t] == 
                    model.RE[s,t] - model.REDA[t])
                    
        self.model.Con4 = pyo.Constraint(self.model.S, self.model.T, rule=RT_RE_availability)

        # Generator constraints - only if generators exist
        if hasattr(self.model, 'xup') and (len(self.model.G) > 0 or isinstance(self.model.G, pyo.RangeSet) or self.num_generators is None):
            # Generator ramping constraints
            def RT_ramp_up(model, s, g, t):
                return model.xup[s,g,t] <= model.RR[g]
                
            self.model.Con5up = pyo.Constraint(self.model.S, self.model.G, self.model.T, rule=RT_ramp_up)

            def RT_ramp_dn(model, s, g, t):
                return model.xdn[s,g,t] <= model.RR[g]
                
            self.model.Con5dn = pyo.Constraint(self.model.S, self.model.G, self.model.T, rule=RT_ramp_dn)

            # Generator capacity constraints
            def RT_capacity_cons(model, s, g, t):
                return model.xDA[g,t] + model.xup[s,g,t] <= model.CAP[g]
                
            self.model.Con6 = pyo.Constraint(self.model.S, self.model.G, self.model.T, rule=RT_capacity_cons)

            def RT_capacity_min(model, s, g, t):
                return model.xDA[g,t] - model.xdn[s,g,t] >= 0
                
            self.model.Con7 = pyo.Constraint(self.model.S, self.model.G, self.model.T, rule=RT_capacity_min)

        # Storage Constraints
        # Storage energy balance
        def storage_balance(model, s, b, t):
            if t == 1:
                return (model.e[s,b,t] == model.E0[b] + 
                        model.ETA_CH[b] * model.p_ch[s,b,t] - 
                        (1/model.ETA_DCH[b]) * model.p_dch[s,b,t])
            return (model.e[s,b,t] == model.e[s,b,t-1] + 
                    model.ETA_CH[b] * model.p_ch[s,b,t] - 
                    (1/model.ETA_DCH[b]) * model.p_dch[s,b,t])
                    
        self.model.storage_balance = pyo.Constraint(self.model.S, self.model.B, self.model.T, rule=storage_balance)

        # Storage capacity constraint
        def storage_capacity(model, s, b, t):
            return model.e[s,b,t] <= model.E_MAX[b]
            
        self.model.storage_capacity = pyo.Constraint(self.model.S, self.model.B, self.model.T, rule=storage_capacity)

        # Power limits 
        # NOTE: Mutual exclusivity is approximated via P_MAX upper bound. Dual-safe but not strict.
        def power_limits(model, s, b, t):
            return model.p_ch[s,b,t] + model.p_dch[s,b,t] <= model.P_MAX[b]
            
        self.model.power_limits = pyo.Constraint(self.model.S, self.model.B, self.model.T, rule=power_limits)
        
        # Storage adjustment limits
        def storage_adjustment_limits(model, s, b, t):
            return model.b_up[s,b,t] + model.b_dn[s,b,t] <= 0.5 * model.P_MAX[b]
            
        self.model.storage_adjustment_limits = pyo.Constraint(self.model.S, self.model.B, self.model.T, 
                                                            rule=storage_adjustment_limits)

        # Final state of charge requirement
        def final_soc(model, s, b):
            return model.e[s,b,self.num_periods] >= model.E_FINAL[b]
        self.model.final_soc = pyo.Constraint(self.model.S, self.model.B, rule=final_soc)

        # Ensure FO up doesn't exceed discharging ability
        def storage_rt_up_cap(model, s, b, t):
            return model.b_up[s,b,t] <= model.e[s,b,t] * model.ETA_DCH[b]
        self.model.storage_rt_up_cap = pyo.Constraint(self.model.S, self.model.B, self.model.T, rule=storage_rt_up_cap)

        # Ensure FO down doesn't exceed charging headroom
        def storage_rt_dn_cap(model, s, b, t):
            return model.b_dn[s,b,t] <= (model.E_MAX[b] - model.e[s,b,t]) / model.ETA_CH[b]
        self.model.storage_rt_dn_cap = pyo.Constraint(self.model.S, self.model.B, self.model.T, rule=storage_rt_dn_cap)

        # Storage ramping constraints
        # def storage_ramp_rate(model, s, b, t):
        #     if t == 1:
        #         return pyo.Constraint.Skip
        #     # constraint with 'abs' needs to be reformulated for a solver
        #     return [
        #         model.p_ch[s,b,t] - model.p_ch[s,b,t-1] <= 0.25 * model.P_MAX[b],
        #         model.p_ch[s,b,t-1] - model.p_ch[s,b,t] <= 0.25 * model.P_MAX[b],
        #         model.p_dch[s,b,t] - model.p_dch[s,b,t-1] <= 0.25 * model.P_MAX[b],
        #         model.p_dch[s,b,t-1] - model.p_dch[s,b,t] <= 0.25 * model.P_MAX[b]
        #     ]
        # self.model.storage_ramp = pyo.Constraint(self.model.S, self.model.B, self.model.T, rule=storage_ramp_rate)

        # Record duals
        self.model.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT)
        
    def create_instance(self, data):
        return self.model.create_instance(data)