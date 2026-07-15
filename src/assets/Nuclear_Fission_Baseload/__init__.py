#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Feb 15 15:55:49 2026

@author: Mónica Sagastuy-Breña
"""

import cvxpy as cp
import numpy as np
from ..Base_Assets import Asset_STEVFNs
from ...network import Edge_STEVFNs


class Nuclear_Fission_Baseload_Asset(Asset_STEVFNs):
    """
    Class for Inflexible nuclear generator.
    Produces constant output equal to:
        capacity_factor * nameplate_capacity
    at every hour.
    """
    asset_name = "Nuclear_Fission_Baseload"
    source_node_type = "NULL"
    target_node_type = "EL"
    transport_time = 0
    period = 1

    @staticmethod
    def cost_fun(flows, params):
        """
        flows: scalar nameplate capacity.
        """
        sizing_constant = params["sizing_constant"]
        usage_constant = params["usage_constant"]
        return sizing_constant * flows + usage_constant * flows

    def __init__(self):
        super().__init__()
        self.cost_fun_params = {
            "sizing_constant": cp.Parameter(nonneg=True, name=f'sizing_constant_{self.asset_name}'),
            "usage_constant": cp.Parameter(nonneg=True, name=f'usage_constant_{self.asset_name}'),
        }
        # Stable output share from nameplate capacity
        self.conversion_fun_params = {
            "capacity_factor": cp.Parameter(nonneg=True, name=f'capacity_factor_{self.asset_name}')
        }
        return

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
        self.number_of_edges = len(self.source_node_times)
        self.gen_profile = cp.Parameter(shape=self.number_of_edges, nonneg=True, name=f'gen_profile_{self.asset_name}')
        # Scalar variable, in this case, nameplate capacity
        self.flows = cp.Variable(nonneg = True)
        return

    def build_edge(self, edge_number):
        target_node_time = self.target_node_times[edge_number]
        new_edge = Edge_STEVFNs()
        self.edges += [new_edge]
        new_edge.attach_target_node(self.network.extract_node(
            self.target_node_location, self.target_node_type, target_node_time))
        new_edge.flow = self.flows * self.gen_profile[edge_number]
        return

    def build_edges(self):
        self.edges = []
        for t in range(self.number_of_edges):
            self.build_edge(t)
            
    def _load_CF_profile(self):
        """
        Build a gen_profile array of length number_of_edges by repeating the scalar
        user-input capacity_factor (share of nameplate capacity stable output).
        """
        cf_scalar = self.conversion_fun_params["capacity_factor"].value
        profile = np.full(self.number_of_edges, cf_scalar, dtype=float)
    
        # assign to parameter
        self.gen_profile.value = profile
        return
    
    def _update_sizing_constant(self):
        N = np.ceil(self.network.system_parameters_df.loc["project_life", "value"]/self.parameters_df["lifespan"])
        r = (1 + self.network.system_parameters_df.loc["discount_rate", "value"])**(-self.parameters_df["lifespan"]/8760)
        NPV_factor = (1-r**N)/(1-r)
        self.cost_fun_params["sizing_constant"].value = self.cost_fun_params["sizing_constant"].value * NPV_factor
        return
    
    def _update_usage_constant(self):
        simulation_factor = 8760/self.network.system_structure_properties["simulated_timesteps"]
        N = np.ceil(self.network.system_parameters_df.loc["project_life", "value"]/8760)
        r = (1 + self.network.system_parameters_df.loc["discount_rate", "value"])**-1
        NPV_factor = (1-r**N)/(1-r)
        usage_constant_per_MWh = (self.cost_fun_params["usage_constant"].value * 
                                                        NPV_factor * simulation_factor)
        # numeric cf_sum = sum of the profile entries (should be dimensionless-hours)
        cf_sum = float(np.sum(self.gen_profile.value))
        # effective USD per MWp over the whole simulation
        usage_constant_effective = usage_constant_per_MWh * cf_sum
        self.cost_fun_params["usage_constant"].value = usage_constant_effective
        return

    def _update_parameters(self):
        super()._update_parameters()
        self._load_CF_profile()
        self._update_sizing_constant()
        self._update_usage_constant()
        return
