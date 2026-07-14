#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Feb 16 14:34:48 2026

@author: Mónica Sagastuy-Breña
"""

import cvxpy as cp
import numpy as np
from ..Base_Assets import Asset_STEVFNs
from ...network import Edge_STEVFNs


class EL_to_H2_Asset(Asset_STEVFNs):
    """
    Electrolyser: Electricity -> Hydrogen (H2).
    - flows: hourly electricity input (GWh)
    - conversion_fun returns H2_mass (tonnes).
    - cost: sizing (GW electrolyser) uses cp.max(flows) and
            usage (USD per MWh electrolysed) uses cp.sum(flows).
    """
    asset_name = "EL_to_H2"
    source_node_type = "EL"
    target_node_type = "H2"

    @staticmethod
    def cost_fun(flows, params):
        sizing_constant = params["sizing_constant"]   # G$/GW 
        usage_constant = params["usage_constant"]     # G$/GWh electricity input (O&M per GWh)
        return sizing_constant * cp.max(flows) + usage_constant * cp.sum(flows)

    @staticmethod
    def conversion_fun(flows, params):
        """
        Convert electricity (GWh) -> H2 mass (tonnes).
        conversion factor: tonnes H2 per GWh electricity 
        """
        conversion_factor = params["conversion_factor"]
        return conversion_factor * flows

    def __init__(self):
        super().__init__()
        self.cost_fun_params = {
            "sizing_constant": cp.Parameter(nonneg=True, name=f"sizing_constant_{self.asset_name}"),
            "usage_constant": cp.Parameter(nonneg=True, name=f"usage_constant_{self.asset_name}")
        }
        self.conversion_fun_params = {
            "conversion_factor": cp.Parameter(nonneg=True, name="conv_factor_{self.asset_name}")
        }
        return

    def define_structure(self, asset_structure):
        super().define_structure(asset_structure)
        self.target_node_location = self.source_node_location
        self.flows = cp.Variable(self.number_of_edges, nonneg=True)  # electricity input GWh/h
        return

    def build_edge(self, edge_number):
        # standard parent class edge-per-timestep pattern
        super().build_edge(edge_number)
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
        self.cost_fun_params["usage_constant"].value = (self.cost_fun_params["usage_constant"].value * 
                                                        NPV_factor * simulation_factor)
        return
    
    def _update_parameters(self):
        super()._update_parameters()
        # Update cost parameters based on NPV
        self._update_sizing_constant()
        self._update_usage_constant()
        return