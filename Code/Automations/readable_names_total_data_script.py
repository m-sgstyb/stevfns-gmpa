#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Nov 24 12:01:15 2023

@author: Mónica Sagastuy-Breña
"""

import pandas as pd
import numpy as np
import re
import os

base_folder = os.path.dirname(__file__) # script location
root_dir = os.path.dirname(os.path.dirname(base_folder)) #root STEVFNs directory
results_dir = os.path.join(root_dir, "Code", "Results", "Results_for_Website")
total_autarky_filename = os.path.join(results_dir, "total_data_autarky.csv")
total_collaboration_filename = os.path.join(results_dir, "total_data_collaboration.csv")

# new_website_folder = os.path.join(base_folder, "readable_names")
# if not(os.path.isdir(new_website_folder)):
#     os.mkdir(new_website_folder)
final_results_dir = os.path.join(results_dir, "To_Upload")
new_total_autarky_filename = os.path.join(final_results_dir, "total_data_autarky.csv")
new_total_collaboration_filename = os.path.join(final_results_dir, "total_data_collaboration.csv")

tech_names = ["Rooftop PV", "Openfield PV", "Offshore wind", "Onshore wind", "Fossil fuel powerplant", "Battery storage",
              "Electric High Temp. Heating", "Electricity to Ammonia", "Ammonia storage", "Ammonia to electricity", "Ammonia High Temp. Heating",
              "Fossil High Temp. Heating", "HVDC Cables", "Ammonia Transport", "Hydropower"]

data = pd.read_csv(total_autarky_filename)
data_collab = pd.read_csv(total_collaboration_filename)

# Combine both technology_name columns
all_tech_names = pd.concat([data["technology_name"], data_collab["technology_name"]])

# Find all [XX] and [XX-YY] patterns
single_country_matches = np.unique(re.findall(r"\[([A-Z]{2})\]", " ".join(all_tech_names)))
collab_matches = np.unique(re.findall(r"\[([A-Z]{2}-[A-Z]{2})\]", " ".join(all_tech_names)))

# Deduplicate and sort
country_id = sorted(set(single_country_matches))
collab_id = sorted(set(collab_matches))
#%%
for label in country_id:
    # Change names in total_data_autarky
    data.loc[data.technology_name == f"RE_PV_Rooftop_Lim_[{label}]", "technology_name"] = f"{tech_names[0]} [{label}]"
    data.loc[data.technology_name == f"RE_PV_Openfield_Lim_[{label}]", "technology_name"] = f"{tech_names[1]} [{label}]"
    data.loc[data.technology_name == f"RE_WIND_Offshore_Lim_[{label}]", "technology_name"] = f"{tech_names[2]} [{label}]"
    data.loc[data.technology_name == f"RE_WIND_Onshore_Lim_[{label}]", "technology_name"] = f"{tech_names[3]} [{label}]"
    data.loc[data.technology_name == f"PP_CO2_[{label}]", "technology_name"] = f"{tech_names[4]} [{label}]"
    data.loc[data.technology_name == f"BESS_[{label}]", "technology_name"] = f"{tech_names[5]} [{label}]"
    data.loc[data.technology_name == f"EL_to_HTH_[{label}]", "technology_name"] = f"{tech_names[6]} [{label}]"
    data.loc[data.technology_name == f"EL_to_NH3_[{label}]", "technology_name"] = f"{tech_names[7]} [{label}]"
    data.loc[data.technology_name == f"NH3_Storage_[{label}]", "technology_name"] = f"{tech_names[8]} [{label}]"
    data.loc[data.technology_name == f"NH3_to_EL_[{label}]", "technology_name"] = f"{tech_names[9]} [{label}]"
    data.loc[data.technology_name == f"NH3_to_HTH_[{label}]", "technology_name"] = f"{tech_names[10]} [{label}]"
    data.loc[data.technology_name == f"FF_to_HTH_[{label}]", "technology_name"] = f"{tech_names[11]} [{label}]"
    data.loc[data.technology_name == f"HYDRO_[{label}]", "technology_name"] = f"{tech_names[14]} [{label}]"
    
    data.loc[data.technology_name == f"EL_Demand_[{label}]", "technology_name"] = f"Electricity Demand [{label}]"
    data.loc[data.technology_name == f"HTH_Demand_[{label}]", "technology_name"] = f"High Temp. Heating Demand [{label}]"
    
    
    
    # Change names in total_data_collaboration
    data_collab.loc[data_collab.technology_name == f"RE_PV_Rooftop_Lim_[{label}]", "technology_name"] = f"{tech_names[0]} [{label}]"
    data_collab.loc[data_collab.technology_name == f"RE_PV_Openfield_Lim_[{label}]", "technology_name"] = f"{tech_names[1]} [{label}]"
    data_collab.loc[data_collab.technology_name == f"RE_WIND_Offshore_Lim_[{label}]", "technology_name"] = f"{tech_names[2]} [{label}]"
    data_collab.loc[data_collab.technology_name == f"RE_WIND_Onshore_Lim_[{label}]", "technology_name"] = f"{tech_names[3]} [{label}]"
    data_collab.loc[data_collab.technology_name == f"PP_CO2_[{label}]", "technology_name"] = f"{tech_names[4]} [{label}]"
    data_collab.loc[data_collab.technology_name == f"BESS_[{label}]", "technology_name"] = f"{tech_names[5]} [{label}]"
    data_collab.loc[data_collab.technology_name == f"EL_to_HTH_[{label}]", "technology_name"] = f"{tech_names[6]} [{label}]"
    data_collab.loc[data_collab.technology_name == f"EL_to_NH3_[{label}]", "technology_name"] = f"{tech_names[7]} [{label}]"
    data_collab.loc[data_collab.technology_name == f"NH3_Storage_[{label}]", "technology_name"] = f"{tech_names[8]} [{label}]"
    data_collab.loc[data_collab.technology_name == f"NH3_to_EL_[{label}]", "technology_name"] = f"{tech_names[9]} [{label}]"
    data_collab.loc[data_collab.technology_name == f"NH3_to_HTH_[{label}]", "technology_name"] = f"{tech_names[10]} [{label}]"
    data_collab.loc[data_collab.technology_name == f"FF_to_HTH_[{label}]", "technology_name"] = f"{tech_names[11]} [{label}]"
    
    data_collab.loc[data_collab.technology_name == f"EL_Demand_[{label}]", "technology_name"] = f"Electricity Demand [{label}]"
    data_collab.loc[data_collab.technology_name == f"HTH_Demand_[{label}]", "technology_name"] = f"High Temp. Heating Demand [{label}]"
    
    for c_label in collab_id:
        data_collab.loc[data_collab.technology_name == f"EL_Transport_[{c_label}]", "technology_name"] = f"{tech_names[12]}  [{c_label}]"
        data_collab.loc[data_collab.technology_name == f"NH3_Transport_[{c_label}]", "technology_name"] = f"{tech_names[13]} [{c_label}]"

    
    
    

data.to_csv(new_total_autarky_filename, index=False)
data_collab.to_csv(new_total_collaboration_filename, index=False)


    
    
    

    
