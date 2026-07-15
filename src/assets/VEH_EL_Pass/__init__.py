#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Feb 15 16:18:13 2026

@author: Mónica Sagastuy-Breña
"""

import os
import numpy as np
import pandas as pd
import cvxpy as cp
from ..Base_Assets import Asset_STEVFNs
from ...network import Edge_STEVFNs

class VEH_EL_Pass_Asset(Asset_STEVFNs):
    """
    Class of Passenger Electric Vehicle
    """
    asset_name = "VEH_EL_Pass"
    source_node_type = "NULL" # Edge to passenger demand node
    target_node_type = "PD_VEH" # Edge to passenger demand node
    target_node_type_aux = "EV_Pass_Demand" # Edge to aux node to match units 
    
    source_node_type_1 = "EL" # Charging EV hourly edges
    target_node_type_1 = "NULL" # Charging EV hourly edges
    period = 1
    transport_time = 0
    
    @staticmethod
    def cost_fun(flows, params):
        sizing_constant = params["sizing_constant"]
        usage_constant = params["usage_constant"]
        conversion_factor = params["conversion_factor"]
        return (sizing_constant + usage_constant) * flows * conversion_factor 
        
       
    @staticmethod   
    def conversion_fun(flows, params):
        conversion_factor = params["conversion_factor"]
        return flows * conversion_factor
    
    def __init__(self):
        self.cost_fun_params = {"sizing_constant": cp.Parameter(nonneg=True, name=f"sizing_constant_{self.asset_name}"),
                                "usage_constant": cp.Parameter(nonneg=True, name=f"usage_constant_{self.asset_name}"),
                                "conversion_factor": cp.Parameter(nonneg=True, name=f"mpkm_GWh_conversion_factor_{self.asset_name}"),
            }
        # Energy to million passenger-km conversion
        self.conversion_fun_params = {"conversion_factor": cp.Parameter(nonneg=True, name=f"mpkm_GWh_conversion_factor_{self.asset_name}"),
            }
        return
    
    def define_structure(self, asset_structure):
        self.asset_structure = asset_structure
        self.source_node_location = asset_structure["Location_1"]
        # Source and target node times for hourly EL edges charging EV
        self.source_node_times = np.arange(asset_structure["Start_Time"] + self.transport_time, 
                                           asset_structure["End_Time"] + self.transport_time, 
                                           self.period)
        self.target_node_location = asset_structure["Location_2"]
        self.target_node_times = np.arange(asset_structure["Start_Time"] + self.transport_time, 
                                           asset_structure["End_Time"] + self.transport_time, 
                                           self.period)
        self.number_of_edges = len(self.source_node_times) # sampled hours in the model
        self.ev_charging_profile = cp.Parameter(shape = self.number_of_edges, nonneg=True)
        self.flows = cp.Variable(nonneg=True) # Size of PD provided by EV, scalar
        return
    
    def build_pd_edge(self):
        """
        Build single edge to annual passenger demand node (in mpkm units)
        """
        source_node_time = 0
        target_node_time = 0
        pd_edge = Edge_STEVFNs()
        self.edges += [pd_edge]
        if self.source_node_type != "NULL":
            pd_edge.attach_source_node(self.network.extract_node(
                self.source_node_location, self.source_node_type, source_node_time))
        if self.target_node_type != "NULL":
            pd_edge.attach_target_node(self.network.extract_node(
                self.target_node_location, self.target_node_type, target_node_time))
        pd_edge.flow = self.flows # Total annual demand, GWh
        pd_edge.conversion_fun = self.conversion_fun # Converts to million passenger-km
        pd_edge.conversion_fun_params = self.conversion_fun_params
        return
    
    def build_ev_dem_edge(self):
        """
        Build single edge to EV annual passenger demand node (in energy units)
        """
        source_node_time = 0
        target_node_time = 0
        ev_edge = Edge_STEVFNs()
        self.edges += [ev_edge]
        if self.source_node_type != "NULL":
            ev_edge.attach_source_node(self.network.extract_node(
                self.source_node_location, self.source_node_type, source_node_time))
        if self.target_node_type != "NULL":
            ev_edge.attach_target_node(self.network.extract_node(
                self.target_node_location, self.target_node_type, target_node_time))
        ev_edge.flow = self.flows # Total annual demand, GWh
        return
    
    def build_EL_edges(self, edge_number):
        """
        Build hourly edges to charge EV fleet based on input parameter
        """
        source_node_time = self.source_node_times[edge_number]
        target_node_time = self.target_node_times[edge_number]
        el_edge = Edge_STEVFNs()
        self.edges += [el_edge]
        if self.source_node_type != "NULL":
            el_edge.attach_source_node(self.network.extract_node(
                self.source_node_location, self.source_node_type, source_node_time))
        if self.target_node_type != "NULL":
            el_edge.attach_target_node(self.network.extract_node(
                self.target_node_location, self.target_node_type, target_node_time))
        el_edge.flow = self.flows * self.ev_charging_profile[edge_number]
        return
    
    def build_edges(self):
        self.edges = []
        self.build_pd_edge()
        self.build_ev_dem_edge()
        for t in range(self.number_of_edges):
            self.build_EL_edges(t)
        
    def _load_charging_profile(self):
        """
        Method loads user-provided hourly profile parameter for EV charging load shape
        Samples profile under same sampling technique for RE profiles
        """
        PROFILE_LOC = self.parameters_df["loc_name"]
        profile_filename = os.path.join(self.parameters_folder, "profiles", f"{PROFILE_LOC}_EV_Charge_GW.csv")
        profile_df = pd.read_csv(profile_filename)
        full_profile = np.array(profile_df["Charging_profile"])
        # Sample stitched profile based on model sample size used (self.number_of_edges)
        set_size = self.parameters_df["set_size"]
        set_number = self.parameters_df["set_number"]
        n_sets = int(np.ceil(self.number_of_edges/set_size))
        gap = int(len(full_profile) / (n_sets * set_size)) * set_size
        offset = set_size * set_number
        new_profile = np.zeros(int(n_sets * set_size))
        for counter1 in range(n_sets):
            old_loc_0 = int(offset + gap*counter1)
            old_loc_1 = int(old_loc_0 + set_size)
            new_loc_0 = int(set_size * counter1)
            new_loc_1 = int(new_loc_0 + set_size)
            new_profile[new_loc_0 : new_loc_1] = full_profile[old_loc_0 : old_loc_1]
        self.ev_charging_profile.value = new_profile[:self.number_of_edges]
        return
    
    def _update_sizing_constant(self):
        N = np.ceil(self.network.system_parameters_df.loc["project_life", "value"]/self.parameters_df["lifespan"])
        r = (1 + self.network.system_parameters_df.loc["discount_rate", "value"])**(-self.parameters_df["lifespan"]/8760)
        NPV_factor = (1-r**N)/(1-r)
        self.cost_fun_params["sizing_constant"].value = self.parameters_df["sizing_constant"] * NPV_factor
        return
    
    def _update_usage_constant(self):
        simulation_factor = 8760/self.network.system_structure_properties["simulated_timesteps"]
        N = np.ceil(self.network.system_parameters_df.loc["project_life", "value"]/8760)
        r = (1 + self.network.system_parameters_df.loc["discount_rate", "value"])**-1
        NPV_factor = (1-r**N)/(1-r)
        self.cost_fun_params["usage_constant"].value = (self.cost_fun_params["usage_constant"].value * 
                                                        NPV_factor * simulation_factor)
        return

    def _update_parameters(self):
      super()._update_parameters()
      # Update cost parameters based on NPV
      self._update_sizing_constant()
      self._update_usage_constant()
      self._load_charging_profile()
      return 
      
        
        