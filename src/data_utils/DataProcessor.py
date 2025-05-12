import pandas as pd
import numpy as np
import yaml

class DataProcessor:
    def __init__(self, gen_csv_path, storage_csv_path, demand_csv_path, renewable_csv_path):
        self.gen_csv_path = gen_csv_path
        self.storage_csv_path = storage_csv_path
        self.demand_csv_path = demand_csv_path
        self.renewable_csv_path = renewable_csv_path

        self.gen_data = None
        self.storage_data = None
        self.demand_data = None
        self.renewable_data = None

    def load_data(self, num_generators, num_storage, num_periods):
        try:
            # Load generator data
            self.gen_data = pd.read_csv(self.gen_csv_path)
            total_gen = len(self.gen_data)
            self.gen_data = self.gen_data.head(num_generators)
            print(f"Generator data loaded: {len(self.gen_data)} of {total_gen} generators loaded.")
            
            # Load storage data
            self.storage_data = pd.read_csv(self.storage_csv_path)
            total_storage = len(self.storage_data)
            self.storage_data = self.storage_data.head(num_storage)
            print(f"Storage data loaded: {len(self.storage_data)} of {total_storage} storages loaded.")
            
            # Load demand data
            self.demand_data = pd.read_csv(self.demand_csv_path)
            total_periods = len(self.demand_data)
            self.demand_data = self.demand_data.head(num_periods)
            print(f"Demand data loaded: {len(self.demand_data)} of {total_periods} periods loaded.")

            # Load renewable data
            self.renewable_data = pd.read_csv(self.renewable_csv_path, index_col='T')
            total_periods = len(self.renewable_data)
            self.renewable_data = self.renewable_data.head(num_periods)
            print(f"Renewable data loaded: {len(self.renewable_data)} of {total_periods} periods loaded.")
            
            return True
        except Exception as e:
            print(f"Error loading data: {str(e)}")
            return False

    def process_gen_data(self):
        id_col = 'GEN UID'
        column_mapping = {
            'PMax MW': 'CAP',
            'Ramp Rate MW/Min': 'RR',
        }

        relevant_cols = list(column_mapping.keys()) + ['Fuel Price $/MMBTU', 'HR_avg_0', 'VOM', 'flag']
        existing_cols = [col for col in relevant_cols if col in self.gen_data.columns]
        selected_cols = [id_col] + existing_cols
        gen_data_filtered = self.gen_data[selected_cols].copy()

        rename_dict = {col: column_mapping[col] for col in column_mapping if col in gen_data_filtered.columns}
        gen_data_filtered.rename(columns=rename_dict, inplace=True)

        original_ids = gen_data_filtered[id_col].tolist()
        gen_id_mapping = {original_id: i+1 for i, original_id in enumerate(original_ids)}
        gen_data_filtered[id_col] = gen_data_filtered[id_col].map(gen_id_mapping)

        gen_data_filtered.set_index(id_col, inplace=True)

        if 'RR' in gen_data_filtered.columns:
            # convert from MW/min to MW/h
            gen_data_filtered['RR'] = gen_data_filtered['RR'] * 60

        if 'Fuel Price $/MMBTU' in self.gen_data.columns and 'HR_avg_0' in self.gen_data.columns:
            # VC = (Fuel Price * Heat Rate) / 1000
            gen_data_filtered['VC'] = (
                gen_data_filtered['Fuel Price $/MMBTU'] * gen_data_filtered['HR_avg_0'] / 1000.0
            )
        
        # if 'Fuel Price $/MMBTU' in gen_data_filtered.columns and 'HR_avg_0' in gen_data_filtered.columns:
        #     vc_calculated = gen_data_filtered['Fuel Price $/MMBTU'] * gen_data_filtered['HR_avg_0'] / 1000.0
        #     gen_data_filtered['VC'] = np.where(vc_calculated > 1.0, vc_calculated, 10.0)

        gen_data_filtered['VCUP'] = gen_data_filtered['VC']
        gen_data_filtered['VCDN'] = gen_data_filtered['VC']

        params = ['CAP', 'RR', 'VC', 'VCUP', 'VCDN']
        gen_data_dict = {}

        for param in params:
            if param in gen_data_filtered.columns:
                param_dict = {}
                for gen_idx in gen_data_filtered.index:
                    param_dict[gen_idx] = gen_data_filtered.loc[gen_idx, param]
                gen_data_dict[param] = param_dict

        param_dict = {gen_idx: int(gen_data_filtered.at[gen_idx, 'flag'])
                    for gen_idx in gen_data_filtered.index}
        gen_data_dict['flag'] = param_dict

        return gen_data_dict

    def process_storage_data(self):
        if self.storage_data is None or self.storage_data.empty:
            return {}
            
        try:
            id_col = 'GEN UID'

            column_mapping = {
                'Max Volume GWh': 'E_MAX',
                'Rating MVA': 'P_MAX',
                'Initial Volume GWh': 'E0',
            }

            relevant_cols = list(column_mapping.keys())
            existing_cols = [col for col in relevant_cols if col in self.storage_data.columns]
                
            selected_cols = [id_col] + existing_cols
            storage_data_filtered = self.storage_data[selected_cols].copy()

            rename_dict = {col: column_mapping[col] for col in column_mapping if col in storage_data_filtered.columns}
            storage_data_filtered.rename(columns=rename_dict, inplace=True)

            # Assign new 1-based sequential IDs to the 'GEN UID' column (id_col)
            # This makes 'GEN UID' the new unique identifier for selected storages, ensuring the index is unique.

            # issue: index for UID not unique in storage.csv
            storage_data_filtered[id_col] = range(1, len(storage_data_filtered) + 1)
            storage_data_filtered.set_index(id_col, inplace=True)

            storage_data_dict = {}

            if 'E_MAX' in storage_data_filtered.columns:
                storage_data_dict['E_MAX'] = {
                    storage_idx: float(storage_data_filtered.at[storage_idx, 'E_MAX']) * 1000
                    for storage_idx in storage_data_filtered.index
                }
                
            if 'P_MAX' in storage_data_filtered.columns:
                storage_data_dict['P_MAX'] = {
                    storage_idx: float(storage_data_filtered.loc[storage_idx, 'P_MAX'])
                    for storage_idx in storage_data_filtered.index
                }
            
            # check charging and discharging efficiency
            storage_data_dict['ETA_CH'] = {
                storage_idx: 1    
                for storage_idx in storage_data_filtered.index
            }
            storage_data_dict['ETA_DCH'] = {
                storage_idx: 1
                for storage_idx in storage_data_filtered.index
            }
            storage_data_dict['STORAGE_COST'] = {
                storage_idx: 1e-4
                for storage_idx in storage_data_filtered.index
            }
            storage_data_dict['E0'] = {
                storage_idx: 1e-4
                for storage_idx in storage_data_filtered.index
            }
            storage_data_dict['E_FINAL'] = {
                storage_idx: 1e-4
                for storage_idx in storage_data_filtered.index
            }

            return storage_data_dict
            
        except Exception as e:
            print(f"Error processing storage data: {str(e)}")
            return {}
    
    def process_demand_data(self, num_periods=24):
        try:
            demand_data = self.demand_data.head(num_periods)
            demand_dict = {
                idx + 1: row['1'] + row['2'] + row['3'] 
                for idx, row in demand_data.iterrows()
            }
            return demand_dict
        except Exception as e:
            print(f"Error processing demand data: {str(e)}")
            return {}
    
    def process_renewable_data(self, num_periods=24):
        try:
            renewable_data = self.renewable_data.head(num_periods)
            renewable_dict = {(int(col), int(time_period)): renewable_data.at[time_period, col] 
                for col in renewable_data.columns 
                for time_period in renewable_data.index}
            return renewable_dict
        except Exception as e:
            print(f"Error processing renewable data: {str(e)}")
            return {}

    def prepare_pyomo_data(self, config):
        # Use the loaded fo_params
        fo_params_data = config.get('fo_params', {})
        fo_params = {
            key: {None: value} if not isinstance(value, dict) else value 
            for key, value in fo_params_data.items()
        }
        pyomo_data = {}
        pyomo_data.update(fo_params)

        if config['benchmark']:
            sets = {
                'T': {None: list(range(1, 3))},
                'S': {None: list(range(1, 6))},
                'R': {None: list(range(1, 5))},
                'G': {None: list(range(1, 6))},
                'B': {None: list(range(1, 1))}
            }
            
            pyomo_data.update(sets)

            pyomo_data['CAP'] = {1: 50, 2: 10, 3: 10, 4: 10, 5: 10}
            pyomo_data['RR'] = {1: 50, 2: 10, 3: 10, 4: 10, 5: 10}
            pyomo_data['VC'] = {1: 20, 2: 35, 3: 50, 4: 60, 5: 70}
            # pyomo_data['VC'] = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            pyomo_data['VCUP'] = pyomo_data['VC']
            pyomo_data['VCDN'] = pyomo_data['VC']
            pyomo_data['flag'] = {1: 1, 2: 1, 3: 1, 4: 1, 5: 1}
            pyomo_data['RE'] = {
                (1, 1): 131, (1, 2): 131,
                (2, 1): 141, (2, 2): 141,
                (3, 1): 155, (3, 2): 155,
                (4, 1): 165, (4, 2): 165,
                (5, 1): 172, (5, 2): 172
            }
            pyomo_data['DEMAND'] = {1: 200, 2:200}
            pyomo_data['REDA'] = {} # not needed for DAFO
            
        else:
            general_cfg = config['general']
            num_periods = general_cfg['num_periods']
            num_scenarios = general_cfg['num_scenarios']
            num_generators = general_cfg['num_generators']
            num_tiers = general_cfg['num_tiers']
            num_storage = general_cfg['num_storage']

            sets = {
                'T': {None: list(range(1, num_periods + 1))},
                'S': {None: list(range(1, num_scenarios + 1))},
                'R': {None: list(range(1, num_tiers + 1))},
                'G': {None: list(range(1, num_generators + 1))},
                'B': {None: list(range(1, num_storage + 1))}
            }
            pyomo_data.update(sets)
            
            try:
                if not self.load_data(num_generators, num_storage, num_periods):
                    raise Exception("Failed to load data")
                    
                gen_data_dict = self.process_gen_data()
                storage_data_dict = self.process_storage_data()
                demand_data_dict = self.process_demand_data(num_periods)
                renewable_data_dict = self.process_renewable_data(num_periods)
            except Exception as e:
                print(f"Error in data processing: {str(e)}")
                raise
            
            pyomo_data.update(gen_data_dict)
            pyomo_data.update(storage_data_dict)
            pyomo_data['DEMAND'] = demand_data_dict
            pyomo_data['RE'] = renewable_data_dict

        pyomo_data = {None: pyomo_data} # reformat for pyomo

        # TODO: UPDATE REQUIRED PARAMETERS
        required_params = [
            'CAP', 'VC', 'VCUP', 'VCDN', 'RR',
            'E_MAX', 'P_MAX', 'ETA_CH', 'ETA_DCH', 'E0', 'E_FINAL', 'STORAGE_COST',
            'D1', 'D2', 'PEN', 'PENDN', 'smallM', 'probTU', 'probTD',
            'DEMAND', 'RE'
        ]
        
        missing_params = [param for param in required_params if param not in pyomo_data[None]]
        if missing_params:
            print(f"Warning: Missing parameters: {missing_params}")
        
        return pyomo_data