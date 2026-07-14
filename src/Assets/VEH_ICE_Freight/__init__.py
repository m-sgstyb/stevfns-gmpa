#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Feb 19 15:19:44 2026

@author: Mónica Sagastuy-Breña
"""

import numpy as np
import cvxpy as cp
from ..Base_Assets import Asset_STEVFNs
from ...Network import Edge_STEVFNs

class VEH_ICE_Freight_Asset(Asset_STEVFNs):
    """
    Class of Freight Internal Combustion Engine Vehicle
    """
    asset_name = "VEH_ICE_Freight"
    source_node_type = "NULL"
    target_node_type = "FD_VEH"
    target_node_type_co2 = "CO2_Budget"
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
        """
        Converts demand in energy to demand in Mtonnes-km
        """
        conversion_factor = params["conversion_factor"]
        return flows * conversion_factor
    
    @staticmethod
    def conversion_fun_2(flows, params):
        CO2_emissions_factor = params["CO2_emissions_factor"]
        return -CO2_emissions_factor * flows
    
    def __init__(self):
        super().__init__()
        self.cost_fun_params = {"sizing_constant": cp.Parameter(nonneg=True,
                                                                name=f"sizing_constant_{self.asset_name}"),
                          "usage_constant": cp.Parameter(nonneg=True,
                                                         name=f"usage_constant_{self.asset_name}"),
                          "conversion_factor": cp.Parameter(nonneg=True,
                                                            name=f"mtkm_GWh_conversion_factor_{self.asset_name}"),
                          }
        self.conversion_fun_params = {"conversion_factor": cp.Parameter(nonneg=True,
                                                                        name=f"mtkm_GWh_conversion_factor_{self.asset_name}")}
        self.conversion_fun_params_2 = {"CO2_emissions_factor": cp.Parameter(nonneg=True,
                                                                             name=f"co2_emissions_factor_{self.asset_name}")}
        return
    
    def define_structure(self, asset_structure):
        self.asset_structure = asset_structure
        self.source_node_location = asset_structure["Location_1"]
        self.target_node_location = asset_structure["Location_2"]
        self.flows = cp.Variable(nonneg = True) # Total annual energy from ICE veh. to meet FD_VEH
        return
    
    def build_ice_dem_edge(self):
        """
        Method builds the edge converting energy units to demand to link to 
        the tonne demand node

        """
        source_node_type = self.source_node_type
        source_node_location = self.source_node_location
        source_node_time = 0
        target_node_type = self.target_node_type
        target_node_location = self.target_node_location
        target_node_time = 0
        
        pd_edge = Edge_STEVFNs()
        self.edges += [pd_edge]
        if source_node_type != "NULL":
            pd_edge.attach_source_node(self.network.extract_node(
                source_node_location, source_node_type, source_node_time))
        if target_node_type != "NULL":
            pd_edge.attach_target_node(self.network.extract_node(
                target_node_location, target_node_type, target_node_time))
        pd_edge.flow = self.flows 
        pd_edge.conversion_fun = self.conversion_fun
        pd_edge.conversion_fun_params = self.conversion_fun_params
        return
    
    def build_emissions_edge(self):
        source_node_type = self.source_node_type
        source_node_location = self.source_node_location
        source_node_time = 0
        target_node_type = self.target_node_type_co2
        target_node_location = self.target_node_location
        target_node_time = 0
        
        co2_edge = Edge_STEVFNs()
        self.edges += [co2_edge]
        if source_node_type != "NULL":
            co2_edge.attach_source_node(self.network.extract_node(
                source_node_location, source_node_type, source_node_time))
        if target_node_type != "NULL":
            co2_edge.attach_target_node(self.network.extract_node(
                target_node_location, target_node_type, target_node_time))
        co2_edge.flow = self.flows
        co2_edge.conversion_fun = self.conversion_fun_2
        co2_edge.conversion_fun_params = self.conversion_fun_params_2
        return
    
    def build_edges(self):
        self.edges = []
        self.build_emissions_edge()
        self.build_ice_dem_edge()
        return
    
    def _update_sizing_constant(self):
        N = np.ceil(self.network.system_parameters_df.loc["project_life", "value"]/self.parameters_df["lifespan"])
        r = (1 + self.network.system_parameters_df.loc["discount_rate", "value"])**(-self.parameters_df["lifespan"]/8760)
        NPV_factor = (1-r**N)/(1-r)
        self.cost_fun_params["sizing_constant"].value = self.cost_fun_params["sizing_constant"].value * NPV_factor
        return
    
    def _update_usage_constants(self):
        simulation_factor = 8760/self.network.system_structure_properties["simulated_timesteps"]
        N = np.ceil(self.network.system_parameters_df.loc["project_life", "value"]/8760)
        r = (1 + self.network.system_parameters_df.loc["discount_rate", "value"])**-1
        NPV_factor = (1-r**N)/(1-r)
        self.cost_fun_params["usage_constant"].value = (self.cost_fun_params["usage_constant"].value * 
                                                        NPV_factor * simulation_factor)
        return
    
    def _update_co2_emissions_factor(self):
        simulation_factor = 8760/self.network.system_structure_properties["simulated_timesteps"]
        N = np.ceil(self.network.system_parameters_df.loc["project_life", "value"]/8760)
        self.conversion_fun_params_2["CO2_emissions_factor"].value = (self.conversion_fun_params_2["CO2_emissions_factor"].value * 
                                                                      simulation_factor * N)
        return
        
    def _update_parameters(self):
        super()._update_parameters()
        for parameter_name, parameter in self.conversion_fun_params_2.items():
            parameter.value = self.parameters_df[parameter_name]
        # Update cost parameters based on NPV
        self._update_sizing_constant()
        self._update_usage_constants()
        self._update_co2_emissions_factor()
        return
    
    def get_asset_sizes(self):
        # Returns the size of the asset as a dict #
        asset_size = self.size()
        asset_identity = self.asset_name + r"_location_" + str(self.node_location)
        return {asset_identity: asset_size}