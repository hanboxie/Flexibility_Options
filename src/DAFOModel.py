import pyomo.environ as pyo

class DAFOModel:
    def __init__(self, num_periods, num_scenarios, num_generators, num_tiers, num_storage):
        self.num_periods = num_periods
        self.num_scenarios = num_scenarios
        self.num_generators = num_generators
        self.num_tiers = num_tiers
        self.num_storage = num_storage
        
        self.model = pyo.AbstractModel()
        self._define_sets()
        self._define_parameters()
        self._define_variables()
        self._define_objective()
        self._define_constraints()
    
    def _define_sets(self):
        self.model.T = pyo.RangeSet(1, self.num_periods)    # Set of time periods
        self.model.S = pyo.RangeSet(1, self.num_scenarios)  # Set of scenarios
        self.model.R = pyo.RangeSet(1, self.num_tiers)      # Set of tiers
        
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
        # General Parameters
        self.model.VC = pyo.Param(self.model.G)           # Variable cost
        self.model.VCUP = pyo.Param(self.model.G)         # Variable cost up
        self.model.VCDN = pyo.Param(self.model.G)         # Variable cost down
        self.model.CAP = pyo.Param(self.model.G)          # Capacity
        self.model.REDA = pyo.Param(self.model.T)         # Maximum DA RE for each hour
        self.model.DEMAND = pyo.Param(self.model.T)       # Electricity demand per hour
        self.model.D1 = pyo.Param(within=pyo.NonNegativeIntegers)    # Linear cost coefficient for demand slack
        self.model.D2 = pyo.Param(within=pyo.NonNegativeIntegers)    # Quadratic cost coefficient for demand slack

        # Parameters specific to the FO
        self.model.RR = pyo.Param(self.model.G)                      # Ramp rate
        self.model.RE = pyo.Param(self.model.S, self.model.T)        # Renewable generation at each scenario and time
        self.model.PEN = pyo.Param(within=pyo.NonNegativeIntegers)   # Penalty for inadequate flexibility up
        self.model.PENDN = pyo.Param(within=pyo.NonNegativeIntegers) # Penalty for inadequate flexibility down
        self.model.smallM = pyo.Param(within=pyo.NonNegativeReals)   # Parameter for alternative optima
        self.model.probTU = pyo.Param(self.model.R)                  # Probability of exercise FO up
        self.model.probTD = pyo.Param(self.model.R)                  # Probability of exercise FO down

        # Storage Parameters
        self.model.E_MAX = pyo.Param(self.model.B)        # Maximum energy capacity
        self.model.P_MAX = pyo.Param(self.model.B)        # Maximum power capacity
        self.model.ETA_CH = pyo.Param(self.model.B)       # Charging efficiency
        self.model.ETA_DCH = pyo.Param(self.model.B)      # Discharging efficiency
        self.model.E0 = pyo.Param(self.model.B)           # Initial state of charge
        self.model.E_FINAL = pyo.Param(self.model.B)      # Required final state of charge
        self.model.STORAGE_COST = pyo.Param(self.model.B) # Storage operating cost per MWh
    
    def _define_variables(self):
        # Energy and reserve variables
        self.model.d = pyo.Var(self.model.T, domain=pyo.NonNegativeReals)      # Demand slack
        self.model.rgDA = pyo.Var(self.model.T, domain=pyo.NonNegativeReals)   # DA renewables schedule
        self.model.du = pyo.Var(self.model.S, self.model.T)                    # Demand uncertainty
        
        # Variables dependent on generator set
        self.model.xDA = pyo.Var(self.model.G, self.model.T, domain=pyo.NonNegativeReals)  # DA energy schedule
        # generator FO Variables
        self.model.hsu = pyo.Var(self.model.R, self.model.G, self.model.T, domain=pyo.NonNegativeReals)  # Supply FO up
        self.model.hsd = pyo.Var(self.model.R, self.model.G, self.model.T, domain=pyo.NonNegativeReals)  # Supply FO down
            
        # FO Variables independent of generators and storage
        self.model.hdu = pyo.Var(self.model.R, self.model.T, domain=pyo.NonNegativeReals)     # Demand FO up
        self.model.hdd = pyo.Var(self.model.R, self.model.T, domain=pyo.NonNegativeReals)     # Demand FO down
        self.model.sdu = pyo.Var(self.model.R, self.model.T, domain=pyo.NonNegativeReals)     # Self-supply FO up
        self.model.sdd = pyo.Var(self.model.R, self.model.T, domain=pyo.NonNegativeReals)     # Self-supply FO down
        self.model.y = pyo.Var(self.model.S, self.model.T, domain=pyo.NonNegativeReals)       # Auxiliary variable

        # Storage Variables
        self.model.e = pyo.Var(self.model.B, self.model.T, domain=pyo.NonNegativeReals)     # Energy level
        self.model.p_ch = pyo.Var(self.model.B, self.model.T, domain=pyo.NonNegativeReals)  # Charging power
        self.model.p_dch = pyo.Var(self.model.B, self.model.T, domain=pyo.NonNegativeReals) # Discharging power
        # Storage FO Variables
        self.model.bsu = pyo.Var(self.model.R, self.model.B, self.model.T, domain=pyo.NonNegativeReals)  # Storage FO up
        self.model.bsd = pyo.Var(self.model.R, self.model.B, self.model.T, domain=pyo.NonNegativeReals)  # Storage FO down
    
    def _define_objective(self):
        # Objective function
        def obj_expression(m):
            objective_terms = []
            
            # Energy costs - generators
            if hasattr(m, 'xDA') and len(m.G) > 0:
                objective_terms.append(sum(m.VC[g] * m.xDA[g,t] for g in m.G for t in m.T))
            
            # Flexibility costs - generators
            if hasattr(m, 'hsu') and len(m.G) > 0:
                objective_terms.append(sum(m.probTU[r] * m.VCUP[g] * m.hsu[r,g,t] for g in m.G for r in m.R for t in m.T))
                objective_terms.append(-sum(m.probTD[r] * m.VCDN[g] * m.hsd[r,g,t] for g in m.G for r in m.R for t in m.T))
            
            # Self-supply flexibility costs
            objective_terms.append(sum(m.probTU[r] * m.PEN * m.sdu[r,t] for r in m.R for t in m.T))
            objective_terms.append(-sum(m.probTD[r] * m.PENDN * m.sdd[r,t] for r in m.R for t in m.T))
            
            # Storage related costs
            if hasattr(m, 'bsu') and len(m.B) > 0:
                # Storage flexibility costs
                objective_terms.append(sum(m.probTU[r] * m.STORAGE_COST[b] * m.bsu[r,b,t] for b in m.B for r in m.R for t in m.T))
                objective_terms.append(-sum(m.probTD[r] * m.STORAGE_COST[b] * m.bsd[r,b,t] for b in m.B for r in m.R for t in m.T))
                # Storage operation costs
                objective_terms.append(sum(m.STORAGE_COST[b] * (m.p_ch[b,t] + m.p_dch[b,t]) for b in m.B for t in m.T))
            
            # Auxiliary costs
            objective_terms.append(sum(m.y[s,t] for s in m.S for t in m.T) * m.smallM)
            
            # Demand response costs
            objective_terms.append(sum(0.2 * m.D1 * (m.d[t] + m.du[s,t]) for s in m.S for t in m.T))
            objective_terms.append(0.2 * m.D2 * sum((m.d[t] + m.du[s,t]) * (m.d[t] + m.du[s,t]) for s in m.S for t in m.T))
            
            return sum(objective_terms)

        self.model.OBJ = pyo.Objective(rule=obj_expression)
    
    def _define_constraints(self):
        # Define constraints - Numbering of constraints follows paper
        # Energy balance for each hour
        def DA_energy_balance(model, t):
            gen_sum = sum(model.xDA[g,t] for g in model.G)
            storage_sum = sum(model.p_dch[b,t] - model.p_ch[b,t] for b in model.B)
            
            return (gen_sum + 
                    model.rgDA[t] + 
                    storage_sum + 
                    model.d[t] == model.DEMAND[t])
        
        self.model.Con3 = pyo.Constraint(self.model.T, rule=DA_energy_balance)

        # Flexibility balance for each hour
        def DA_flexup_balance(model, r, t):
            gen_flex_up = sum(model.hsu[r,g,t] for g in model.G)
            storage_flex_up = sum(model.bsu[r,b,t] for b in model.B)
            
            return (gen_flex_up + storage_flex_up == model.hdu[r,t])
        
        self.model.Con4UP = pyo.Constraint(self.model.R, self.model.T, rule=DA_flexup_balance)

        def DA_flexdn_balance(model, r, t):
            gen_flex_down = sum(model.hsd[r,g,t] for g in model.G)
            storage_flex_down = sum(model.bsd[r,b,t] for b in model.B)
            
            return (gen_flex_down + storage_flex_down == model.hdd[r,t])
        
        self.model.Con4DN = pyo.Constraint(self.model.R, self.model.T, rule=DA_flexdn_balance)

        # Flexibility demand for each scenario and hour
        def DA_flex_demand(model, s, t):
            return (-model.du[s,t] + 
                    sum(model.hdd[r,t] + model.sdd[r,t] for r in model.R if r <= s-1) -
                    sum(model.hdu[r,t] + model.sdu[r,t] for r in model.R if r >= s) == 
                    model.RE[s,t] - model.rgDA[t])
        
        self.model.Con6 = pyo.Constraint(self.model.S, self.model.T, rule=DA_flex_demand)

        def DA_flex_demand_bound(model, s, t):
            return (sum(model.hdd[r, t] + model.sdd[r, t] for r in model.R if r <= s-1) + 
                    sum(model.hdu[r, t] + model.sdu[r, t] for r in model.R if r >= s)) <= model.y[s, t]
        self.model.Con7 = pyo.Constraint(self.model.S, self.model.T, rule=DA_flex_demand_bound)

        def Y2(model, s, t):
            return model.y[s, t] >= model.rgDA[t] - model.RE[s, t]
        self.model.Con8 = pyo.Constraint(self.model.S, self.model.T, rule=Y2)  

        def Y1(model, s, t):
            return model.y[s, t] >= model.RE[s, t] - model.rgDA[t]
        self.model.Con9 = pyo.Constraint(self.model.S, self.model.T, rule=Y1)

        # Generator constraints
        def RRUP(model, g, t):
            return sum(model.hsu[r, g, t] for r in model.R) <= model.RR[g]
        self.model.Con10up = pyo.Constraint(self.model.G, self.model.T, rule=RRUP)  

        def RRDN(model, g, t):
            return sum(model.hsd[r, g, t] for r in model.R) <= model.RR[g]
        self.model.Con10dn = pyo.Constraint(self.model.G, self.model.T, rule=RRDN)

        # Inter-temporal constraints
        def ramp_rate_up(model, g, t):
            if t == 1:
                return pyo.Constraint.Skip
            return model.xDA[g,t] - model.xDA[g,t-1] <= model.RR[g]
        self.model.Con13up = pyo.Constraint(self.model.G, self.model.T, rule=ramp_rate_up)

        def ramp_rate_down(model, g, t):
            if t == 1:
                return pyo.Constraint.Skip
            return model.xDA[g,t-1] - model.xDA[g,t] <= model.RR[g]
        self.model.Con13dn = pyo.Constraint(self.model.G, self.model.T, rule=ramp_rate_down)

        def generation_limits(model, g, t):
            return model.xDA[g,t]+ sum(model.hsu[r,g,t] for r in model.R) <= model.CAP[g]
        self.model.Con11 = pyo.Constraint(self.model.G, self.model.T, rule=generation_limits)

        def DA_down_cons(model, g, t):
            return sum(model.hsd[r,g,t] for r in model.R)<= model.xDA[g,t]
        self.model.Con12= pyo.Constraint(self.model.G, self.model.T, rule=DA_down_cons)

        # Storage constraints
        # Storage energy balance
        def storage_balance(model, b, t):
            if t == 1:
                return (model.e[b,t] == model.E0[b] + 
                        model.ETA_CH[b] * model.p_ch[b,t] - 
                        (1/model.ETA_DCH[b]) * model.p_dch[b,t])
            else:
                return (model.e[b,t] == model.e[b,t-1] + 
                        model.ETA_CH[b] * model.p_ch[b,t] - 
                        (1/model.ETA_DCH[b]) * model.p_dch[b,t])
        self.model.storage_balance = pyo.Constraint(self.model.B, self.model.T, rule=storage_balance)

            # Storage capacity constraint
        def storage_capacity(model, b, t):
            return model.e[b,t] <= model.E_MAX[b]
        self.model.storage_capacity = pyo.Constraint(self.model.B, self.model.T, rule=storage_capacity)

        # Power limits
        def power_limits(model, b, t):
            return model.p_ch[b,t] + model.p_dch[b,t] <= model.P_MAX[b]
        self.model.power_limits = pyo.Constraint(self.model.B, self.model.T, rule=power_limits)

        # Storage flexibility limits
        def storage_flex_limits(model, r, b, t):
            return model.bsu[r,b,t] + model.bsd[r,b,t] <= 0.5 * model.P_MAX[b]
        self.model.storage_flex_limits = pyo.Constraint(self.model.R, self.model.B, self.model.T, rule=storage_flex_limits)

        # Storage FO up and down constraints
        def storage_fo_up_limit(model, r, b, t):
            return model.bsu[r,b,t] <= 0.5 * model.P_MAX[b]
        self.model.storage_fo_up = pyo.Constraint(self.model.R, self.model.B, self.model.T, 
                                                rule=storage_fo_up_limit)
        
        def storage_fo_down_limit(model, r, b, t):
            return model.bsd[r,b,t] <= 0.5 * model.P_MAX[b]
        self.model.storage_fo_down = pyo.Constraint(self.model.R, self.model.B, self.model.T, 
                                                    rule=storage_fo_down_limit)

        # Record duals for market analysis
        self.model.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT)
        
    def create_instance(self, data):
        return self.model.create_instance(data)