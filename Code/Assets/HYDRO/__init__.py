#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Apr 13 12:23:59 2025

@author: Mónica Sagastuy-Breña
"""

import numpy as np
import cvxpy as cp
from ..Base_Assets import Asset_STEVFNs
from ...Network import Edge_STEVFNs

class HYDRO_Asset(Asset_STEVFNs):
    """Class for hydropower plant asset with only existing capacity,
    no Capital Cost modeled
    """
    asset_name = "HYDRO"
    source_node_type = "NULL"
    target_node_type = "EL"
    target_node_type_2 = "HYDRO"
    period = 1
    transport_time = 0
    target_node_time_2 = 0
    
    @staticmethod
    def cost_fun(flows, params):
        usage_constant = params["usage_constant"]
        return usage_constant * cp.sum(flows)
    
    @staticmethod
    def conversion_fun(flows, params):
        return flows
    
    @staticmethod
    def conversion_fun_2(flows, params):
        existing_capacity = params["existing_capacity"]
        return existing_capacity - cp.max(flows)
    
    def __init__(self):
        super().__init__()
        self.cost_fun_params = {"usage_constant": cp.Parameter(nonneg=True)}
        self.conversion_fun_params_2 = {"existing_capacity": cp.Parameter(nonneg=True),
                                        "capacity_factor": cp.Parameter(nonneg=True)}
        
        
    def define_structure(self, asset_structure):
        self.asset_structure = asset_structure
        self.source_node_location = asset_structure["Location_1"]
        self.source_node_times = np.arange(asset_structure["Start_Time"] + self.transport_time, 
                                           asset_structure["End_Time"] + self.transport_time, 
                                           self.period)
        self.target_node_location = asset_structure["Location_2"]
        self.target_node_times = np.arange(asset_structure["Start_Time"] + self.transport_time, 
                                           asset_structure["End_Time"] + self.transport_time, 
                                           self.period)
        self.source_node_location_2 = "NULL"
        self.target_node_location_2 = asset_structure["Location_1"]
        self.number_of_edges = len(self.source_node_times)
        self.flows = cp.Variable(self.number_of_edges, nonneg = True)

    
    def build_edges(self):
        super().build_edges()
        self.build_edge_2()

    def build_edge(self, edge_number):
        source_node_time = self.source_node_times[edge_number]
        target_node_time = self.target_node_times[edge_number]
        new_edge = Edge_STEVFNs()
        self.edges += [new_edge]
        if self.source_node_type != "NULL":
            new_edge.attach_source_node(self.network.extract_node(
                self.source_node_location, self.source_node_type, source_node_time))
        if self.target_node_type != "NULL":
            new_edge.attach_target_node(self.network.extract_node(
                self.target_node_location, self.target_node_type, target_node_time))
        new_edge.flow = self.flows[edge_number]
        new_edge.conversion_fun = self.conversion_fun
        new_edge.conversion_fun_params = self.conversion_fun_params
    
    def build_edge_2(self):
        source_node_type = "NULL"
        source_node_location = self.source_node_location_2
        source_node_time = 0
        target_node_type = self.target_node_type_2
        target_node_location = self.target_node_location_2
        target_node_time = self.target_node_time_2
        
        new_edge = Edge_STEVFNs()
        self.edges += [new_edge]
        if source_node_type != "NULL":
            new_edge.attach_source_node(self.network.extract_node(
                source_node_location, source_node_type, source_node_time))
        if target_node_type != "NULL":
            new_edge.attach_target_node(self.network.extract_node(
                target_node_location, target_node_type, target_node_time))
        new_edge.flow = self.flows
        new_edge.conversion_fun = self.conversion_fun_2
        new_edge.conversion_fun_params = self.conversion_fun_params_2
        
    def _update_usage_constants(self):
        simulation_factor = 8760/self.network.system_structure_properties["simulated_timesteps"]
        N = np.ceil(self.network.system_parameters_df.loc["project_life", "value"]/8760)
        r = (1 + self.network.system_parameters_df.loc["discount_rate", "value"])**-1
        NPV_factor = (1-r**N)/(1-r)
        self.cost_fun_params["usage_constant"].value = (self.cost_fun_params["usage_constant"].value * 
                                                        NPV_factor * simulation_factor)

    def _update_existing_capacity(self):
        self.conversion_fun_params_2["existing_capacity"].value =  self.conversion_fun_params_2["existing_capacity"].value * self.conversion_fun_params_2["capacity_factor"].value

    def _update_parameters(self):
        for parameter_name, parameter in self.cost_fun_params.items():
            parameter.value = self.parameters_df[parameter_name]
            
        for parameter_name, parameter in self.conversion_fun_params.items():
            parameter.value = self.parameters_df[parameter_name]
        
        for parameter_name, parameter in self.conversion_fun_params_2.items():
            parameter.value = self.parameters_df[parameter_name]
            
        #Update O&M cost parameters based on NPV#
        self._update_usage_constants()
        #Update existing capacity with CF
        self._update_existing_capacity()
        
    def get_plot_data(self):
        capacity_factor = self.conversion_fun_params["capacity_factor"].value
        return self.flows * capacity_factor
        
        
    




    
    
    