#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Oct 31 10:49:50 2023

@author: Mónica Sagastuy-Breña
"""

import pandas as pd
import numpy as np
import re

def export_total_data(my_network, location_parameters_df, asset_parameters_df):
    ''' Function to export results, generalized for all case studies'''
    
    location_names = list(location_parameters_df["location_name"])
    loc_names_set_list = list(set(asset_parameters_df["Location_1"]).union(set(asset_parameters_df["Location_2"])))
    loc_names_list = ["",]*4
    for counter1 in range(len(loc_names_set_list)):
        loc_names_list[counter1] = location_names[loc_names_set_list[counter1]]
    
    total_data_columns = ["country_1",
                  "country_2",
                  "country_3",
                  "country_4",
                  "collaboration_emissions",
                  "technology_cost",
                  "technology_name",]
    total_data_df = pd.DataFrame(columns = total_data_columns)
    
    collaboration_emissions =  my_network.assets[0].asset_size()
    loc_names_set = set()
    
    for counter1 in range(1,len(my_network.assets)):
        asset = my_network.assets[counter1]
        name = asset.asset_name
        
        ### Exceptions in formatting or extracting results per type of asset ###
        if name == 'BESS' or name == 'NH3_Storage':
            loc1 = asset.asset_structure["Location_1"]
            loc_name = location_names[loc1]
            loc_names_set.add(loc_name)
            technology_name = name + r"_[" + loc_name + r"]"
            technology_cost = asset.cost.value
            
        elif name == 'RE_PV_Rooftop_Lim' or name == 'RE_PV_Openfield_Lim' or name == 'RE_WIND_Onshore_Lim' or name == 'RE_WIND_Offshore_Lim' or name == 'RE_WIND_Onshore_BAU' or name == 'RE_PV_Openfield_BAU':
            loc1 = asset.target_node_location
            loc_name = location_names[loc1]
            loc_names_set.add(loc_name)
            technology_name = name + r"_[" + loc_name + r"]"
            technology_cost =  asset.cost.value

        elif name == 'EL_Demand' or name == 'HTH_Demand':
            loc1 = asset.node_location
            loc_name = location_names[loc1]
            loc_names_set.add(loc_name)
            technology_name = name + r"_[" + loc_name + r"]"
            technology_cost = asset.cost.value
            
        elif name == 'EL_Transport' or name == 'NH3_Transport':
            loc1 = asset.asset_structure["Location_1"]
            loc2 = asset.asset_structure["Location_2"]
            loc_name_1 = location_names[loc1]
            loc_name_2 = location_names[loc2]
            loc_names_set.add(loc_name_1)
            loc_names_set.add(loc_name_1)
            technology_name = name + r"_[" + loc_name_1 + r"-" + loc_name_2 + r"]"
            technology_cost = asset.cost.value
        
        
        
        ### The rest of the assets, in general ###
        else:
            loc1 = asset.asset_structure["Location_1"]
            loc_name = location_names[loc1]
            loc_names_set.add(loc_name)
            technology_name = name + r"_[" + loc_name + r"]"
            technology_cost = asset.cost.value
        
        N = np.ceil(my_network.system_parameters_df.loc["project_life", "value"]/8760) #number of years for the project
        t_df = pd.DataFrame({"country_1": [loc_names_list[0]],
                             "country_2": [loc_names_list[1]],
                             "country_3": [loc_names_list[2]],
                             "country_4": [loc_names_list[3]],
                             "collaboration_emissions": [round(collaboration_emissions/N, 1)],# Number is annualized, number is converted from ktCO2e to MtCO2e
                             "technology_cost": [round(technology_cost/N, 1)],# Number is annualized
                             "technology_name": [technology_name],
            })
        total_data_df = pd.concat([total_data_df, t_df], ignore_index=True)
    
    return total_data_df

def export_total_data_not_rounded(my_network, location_parameters_df, asset_parameters_df):
    ''' Function to export results, generalized for all case studies'''
    
    location_names = list(location_parameters_df["location_name"])
    loc_names_set_list = list(set(asset_parameters_df["Location_1"]).union(set(asset_parameters_df["Location_2"])))
    loc_names_list = ["",]*4
    for counter1 in range(len(loc_names_set_list)):
        loc_names_list[counter1] = location_names[loc_names_set_list[counter1]]
    
    total_data_columns = ["country_1",
                  "country_2",
                  "country_3",
                  "country_4",
                  "collaboration_emissions",
                  "technology_cost",
                  "technology_name",]
    total_data_df = pd.DataFrame(columns = total_data_columns)
    
    collaboration_emissions =  my_network.assets[0].asset_size()
    loc_names_set = set()
    
    for counter1 in range(1,len(my_network.assets)):
        asset = my_network.assets[counter1]
        name = asset.asset_name
        
        ### Exceptions in formatting or extracting results per type of asset ###
        if name == 'BESS' or name == 'NH3_Storage':
            loc1 = asset.asset_structure["Location_1"]
            loc_name = location_names[loc1]
            loc_names_set.add(loc_name)
            technology_name = name + r"_[" + loc_name + r"]"
            technology_cost = asset.cost.value
            
        elif name == 'RE_PV_Rooftop_Lim' or name == 'RE_PV_Openfield_Lim' or name == 'RE_WIND_Onshore_Lim' or name == 'RE_WIND_Offshore_Lim' or name == 'RE_WIND_Onshore_BAU' or name == 'RE_PV_Openfield_BAU':
            loc1 = asset.target_node_location
            loc_name = location_names[loc1]
            loc_names_set.add(loc_name)
            technology_name = name + r"_[" + loc_name + r"]"
            technology_cost =  asset.cost.value

        elif name == 'EL_Demand' or name == 'HTH_Demand':
            loc1 = asset.node_location
            loc_name = location_names[loc1]
            loc_names_set.add(loc_name)
            technology_name = name + r"_[" + loc_name + r"]"
            technology_cost = asset.cost.value
            
        elif name == 'EL_Transport' or name == 'NH3_Transport':
            loc1 = asset.asset_structure["Location_1"]
            loc2 = asset.asset_structure["Location_2"]
            loc_name_1 = location_names[loc1]
            loc_name_2 = location_names[loc2]
            loc_names_set.add(loc_name_1)
            loc_names_set.add(loc_name_1)
            technology_name = name + r"_[" + loc_name_1 + r"-" + loc_name_2 + r"]"
            technology_cost = asset.cost.value
        
        ### The rest of the assets, in general ###
        else:
            loc1 = asset.asset_structure["Location_1"]
            loc_name = location_names[loc1]
            loc_names_set.add(loc_name)
            technology_name = name + r"_[" + loc_name + r"]"
            technology_cost = asset.cost.value
        
        N = np.ceil(my_network.system_parameters_df.loc["project_life", "value"]/8760) #number of years for the project
        t_df = pd.DataFrame({"country_1": [loc_names_list[0]],
                             "country_2": [loc_names_list[1]],
                             "country_3": [loc_names_list[2]],
                             "country_4": [loc_names_list[3]],
                             "collaboration_emissions": [collaboration_emissions/N],# Number is annualized, number is converted from ktCO2e to MtCO2e
                             "technology_cost": [technology_cost/N],# Number is annualized
                             "technology_name": [technology_name],
            })
        total_data_df = pd.concat([total_data_df, t_df], ignore_index=True)
    return total_data_df

def export_total_data_website(my_network, location_parameters_df, asset_parameters_df):
    ''' Function to export results, generalized for all case studies with wind bin aggregation for web display '''
    
    location_names = list(location_parameters_df["location_name"])
    loc_names_set_list = list(set(asset_parameters_df["Location_1"]).union(set(asset_parameters_df["Location_2"])))
    loc_names_list = ["",]*4
    for counter1 in range(len(loc_names_set_list)):
        loc_names_list[counter1] = location_names[loc_names_set_list[counter1]]
    
    total_data_columns = ["country_1",
                          "country_2",
                          "country_3",
                          "country_4",
                          "collaboration_emissions",
                          "technology_cost",
                          "technology_name"]
    total_data_df = pd.DataFrame(columns=total_data_columns)
    wind_bin_costs = {}  # key: base asset name, value: dict of loc -> aggregated cost
    
    collaboration_emissions = my_network.assets[0].asset_size()
    
    for counter1 in range(1, len(my_network.assets)):
        asset = my_network.assets[counter1]
        name = asset.asset_name
        if re.match(r"RE_WIND_(Onshore|Offshore)_Lim_\d+$", name):
            base_name = re.sub(r"_\d+$", "", name)
        else:
            base_name = name

        if "RE_WIND_Onshore_Lim" in name or "RE_WIND_Offshore_Lim" in name:
            loc = asset.target_node_location
            loc_name = location_names[loc]
            wind_type = "RE_WIND_Onshore_Lim" if "Onshore" in name else "RE_WIND_Offshore_Lim"
            if wind_type not in wind_bin_costs:
                wind_bin_costs[wind_type] = {}
            if loc_name not in wind_bin_costs[wind_type]:
                wind_bin_costs[wind_type][loc_name] = 0.0
            wind_bin_costs[wind_type][loc_name] += asset.cost.value
            continue  # Skip adding to total_data_df here; we will add it later as aggregated

        ### Other assets
        if name in ['BESS', 'NH3_Storage']:
            loc1 = asset.asset_structure["Location_1"]
            loc_name = location_names[loc1]
        elif name in ['RE_PV_Rooftop_Lim', 'RE_PV_Openfield_Lim', 'RE_WIND_Onshore_Lim', 'RE_WIND_Offshore_Lim',
                      'RE_WIND_Onshore_BAU', 'RE_PV_Openfield_BAU']:
            loc1 = asset.target_node_location
            loc_name = location_names[loc1]
        elif name in ['EL_Demand', 'HTH_Demand']:
            loc1 = asset.node_location
            loc_name = location_names[loc1]
        elif name in ['EL_Transport', 'NH3_Transport']:
            loc1 = asset.asset_structure["Location_1"]
            loc2 = asset.asset_structure["Location_2"]
            loc_name = location_names[loc1] + "-" + location_names[loc2]
        else:
            loc1 = asset.asset_structure["Location_1"]
            loc_name = location_names[loc1]
        
        technology_name = base_name + r"_[" + loc_name + r"]"
        technology_cost = asset.cost.value
        N = np.ceil(my_network.system_parameters_df.loc["project_life", "value"]/8760)

        t_df = pd.DataFrame({
            "country_1": [loc_names_list[0]],
            "country_2": [loc_names_list[1]],
            "country_3": [loc_names_list[2]],
            "country_4": [loc_names_list[3]],
            "collaboration_emissions": [collaboration_emissions / N],
            "technology_cost": [technology_cost / N],
            "technology_name": [technology_name],
        })
        total_data_df = pd.concat([total_data_df, t_df], ignore_index=True)

    # Now add the aggregated wind bins
    for wind_type, loc_costs in wind_bin_costs.items():
        for loc_name, total_cost in loc_costs.items():
            technology_name = wind_type + r"_[" + loc_name + r"]"
            t_df = pd.DataFrame({
                "country_1": [loc_names_list[0]],
                "country_2": [loc_names_list[1]],
                "country_3": [loc_names_list[2]],
                "country_4": [loc_names_list[3]],
                "collaboration_emissions": [collaboration_emissions / N],
                "technology_cost": [total_cost / N],
                "technology_name": [technology_name],
            })
            total_data_df = pd.concat([total_data_df, t_df], ignore_index=True)

    return total_data_df


def export_total_data_capacities(my_network, location_parameters_df, asset_parameters_df):
    ''' Function to export results, generalized for all case studies
        Creates the same dataframe than total_data (rounded results)
        but includes a column for installed capacities. For internal reference and
        analysis only
    '''
    
    location_names = list(location_parameters_df["location_name"])
    loc_names_set_list = list(set(asset_parameters_df["Location_1"]).union(set(asset_parameters_df["Location_2"])))
    loc_names_list = ["",]*4
    for counter1 in range(len(loc_names_set_list)):
        loc_names_list[counter1] = location_names[loc_names_set_list[counter1]]
    
    total_data_columns = ["country_1",
                  "country_2",
                  "country_3",
                  "country_4",
                  "collaboration_emissions",
                  "technology_cost",
                  "technology_capacity",
                  "technology_name",]
    total_data_df = pd.DataFrame(columns = total_data_columns)
    
    collaboration_emissions =  my_network.assets[0].asset_size()
    loc_names_set = set()
    
    for counter1 in range(1,len(my_network.assets)):
        asset = my_network.assets[counter1]
        name = asset.asset_name
        
        ### Exceptions in formatting or extracting results per type of asset ###
        if name == 'BESS' or name == 'NH3_Storage':
            loc1 = asset.asset_structure["Location_1"]
            loc_name = location_names[loc1]
            loc_names_set.add(loc_name)
            technology_name = name + r"_[" + loc_name + r"]"
            technology_cost = asset.cost.value
            technology_capacity = asset.asset_size()
            
        elif name == 'RE_PV_Rooftop_Lim' or name == 'RE_PV_Openfield_Lim' or name == 'RE_WIND_Onshore_Lim' or name == 'RE_WIND_Offshore_Lim' or name == 'RE_WIND_Onshore_BAU' or name == 'RE_PV_Openfield_BAU':
            loc1 = asset.target_node_location
            loc_name = location_names[loc1]
            loc_names_set.add(loc_name)
            technology_name = name + r"_[" + loc_name + r"]"
            technology_cost =  asset.cost.value
            technology_capacity = asset.asset_size()

        elif name == 'EL_Demand' or name == 'HTH_Demand':
            loc1 = asset.node_location
            loc_name = location_names[loc1]
            loc_names_set.add(loc_name)
            technology_name = name + r"_[" + loc_name + r"]"
            technology_cost = asset.cost.value
            technology_capacity = asset.asset_size()
            
        elif name == 'EL_Transport' or name == 'NH3_Transport':
            loc1 = asset.asset_structure["Location_1"]
            loc2 = asset.asset_structure["Location_2"]
            loc_name_1 = location_names[loc1]
            loc_name_2 = location_names[loc2]
            loc_names_set.add(loc_name_1)
            loc_names_set.add(loc_name_1)
            technology_name = name + r"_[" + loc_name_1 + r"-" + loc_name_2 + r"]"
            technology_cost = asset.cost.value
            technology_capacity = asset.asset_size()
        
        
        
        ### The rest of the assets, in general ###
        else:
            loc1 = asset.asset_structure["Location_1"]
            loc_name = location_names[loc1]
            loc_names_set.add(loc_name)
            technology_name = name + r"_[" + loc_name + r"]"
            technology_cost = asset.cost.value
            technology_capacity = asset.asset_size()
        
        N = np.ceil(my_network.system_parameters_df.loc["project_life", "value"]/8760) #number of years for the project
        t_df = pd.DataFrame({"country_1": [loc_names_list[0]],
                             "country_2": [loc_names_list[1]],
                             "country_3": [loc_names_list[2]],
                             "country_4": [loc_names_list[3]],
                             "collaboration_emissions": [round(collaboration_emissions/N, 1)],# Number is annualized, number is converted from ktCO2e to MtCO2e
                             "technology_cost": [round(technology_cost/N, 1)],# Number is annualized
                             "technology_capacity": [round(technology_capacity, 1)],
                             "technology_name": [technology_name],
            })
        total_data_df = pd.concat([total_data_df, t_df], ignore_index=True)
    
    return total_data_df

