#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Feb 16 10:59:19 2026

@author: Mónica Sagastuy-Breña
"""

import numpy as np
import cvxpy as cp
from ..Base_Assets import Asset_STEVFNs
from ...network import Edge_STEVFNs

class VEH_Pass_Demand_Asset(Asset_STEVFNs):
    """
    Class of Passenger Demand (vehicles)
    """
    asset_name = "VEH_Pass_Demand"
    node_type = "PD_VEH"
    source_node_time = 0
    period = 1
    transport_time = 0
    
    def __init__(self):
        super().__init__()
        return
    
    def define_structure(self, asset_structure):
        self.asset_structure = asset_structure
        self.node_location = asset_structure["Location_1"]
        self.number_of_edges = 1
        self.node_times = 0
        self.flows = cp.Parameter(nonneg=True, name=f"vehicle_pass_demand_{self.asset_name}")
        return
    
    def build_costs(self):
        self.cost = cp.Constant(0)
        return
    
    def build_edge(self):
        """
        Method that builds parameter edge for Passenger Vehicle Demand Asset
        """
        node_time = self.node_times
        new_edge = Edge_STEVFNs()
        self.edges += [new_edge]
        # Attach edge from demand node to null
        new_edge.attach_source_node(self.network.extract_node(
            self.node_location, self.node_type, node_time))
        new_edge.flow = self.flows
        return
    
    def build_edges(self):
        self.edges = []
        self.build_edge()
         
    def _load_parameters_df(self, asset_type):
        super()._load_parameters_df(asset_type)
        
    def _update_parameters(self):
        self.flows.value = self.parameters_df["annual_demand"]
        
        
    
    
    