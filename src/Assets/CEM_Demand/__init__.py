#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Feb 20 15:14:28 2026

@author: Mónica Sagastuy-Breña
"""

import numpy as np
import pandas as pd
import cvxpy as cp
from ..Base_Assets import Asset_STEVFNs
from ...network import Edge_STEVFNs

class CEM_Demand_Asset(Asset_STEVFNs):
    """
    Cement demand Asset Class.
      - flows is a user-input cp.Parameter
      - attaches as an edge from the CEM node (output_edge)
    Expects a single value for demand in Mt cement/year
    """
    asset_name = "CEM_Demand"
    node_type = "CEM" # Cement demand node for this location
    node_time = 0 # Single node for annual demand

    def __init__(self):
        super().__init__()
        return

    def define_structure(self, asset_structure):
        self.asset_structure = asset_structure
        self.node_location = asset_structure["Location_1"]
        self.flows = cp.Parameter(nonneg=True) # total demand of cement
        return

    def build_costs(self):
        self.cost = cp.Constant(0)
        return

    def build_edge(self):
        node_time = self.node_time
        new_edge = Edge_STEVFNs()
        self.edges += [new_edge]
        
        new_edge.attach_source_node(self.network.extract_node(
            self.node_location, self.node_type, node_time))
        new_edge.flow = self.flows
        return
    
    def build_edges(self):
        """
        Build single edge
        Overwrites parent class build_edges
        """
        self.edges = []
        self.build_edge()
        return
    
    def _update_parameters(self):
        """
        Assign user-input parameter value to self.flows and adjust by simulated
        time steps to match input flows from CEM_Production
        """
        simulation_factor = 8760 / self.network.system_structure_properties["simulated_timesteps"]
        self.flows.value = self.parameters_df["demand"] / simulation_factor
        return

    def get_asset_sizes(self):
        asset_size = self.size()
        asset_identity = self.asset_name + r"_location_" + str(self.node_location)
        return {asset_identity: asset_size}
