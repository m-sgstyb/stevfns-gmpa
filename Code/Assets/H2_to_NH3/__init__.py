#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Feb 16 13:43:16 2026

@author: Mónica Sagastuy-Breña
"""

import cvxpy as cp
import numpy as np
from ..Base_Assets import Asset_STEVFNs
from ...Network import Edge_STEVFNs


class H2_to_NH3_Asset(Asset_STEVFNs):
    """
    Haber-Bosch: Hydrogen -> Ammonia
    - flows: hourly H2 feed (tonnes)
    - conversion_fun returns NH3 mass (tonnes)
    - cost: sizing based on peak H2 feed, usage based on throughput
    """
    asset_name = "H2_to_NH3"
    source_node_type = "H2"
    target_node_type = "NH3"

    @staticmethod
    def cost_fun(flows, params):
        sizing_constant = params["sizing_constant"] # Haber-Bosch sizing constant
        usage_constant = params["usage_constant"]# Haber-Bosch usage constant
        return sizing_constant * cp.max(flows) + usage_constant * cp.sum(flows)

    @staticmethod
    def conversion_fun(flows, params):
        """
        Convert H2 mass -> NH3 mass using stoichiometry and HB process conversion efficiency.
        params expects:
          - 'h2_to_nh3_stoich' : NH3_per_H2_mass (tonnes NH3 per tonne H2)  (this is the inverse of 0.176..)
          - 'hb_yield' : fraction (0-1) capturing process inefficiency or losses in HB conversion
        """
        nh3_per_h2_stoich = params["nh3_per_tonne_h2"]
        hb_yield = params["hb_yield"]
        return flows * nh3_per_h2_stoich * hb_yield

    def __init__(self):
        super().__init__()
        self.cost_fun_params = {
            "hb_sizing_constant": cp.Parameter(nonneg=True, name="hb_sizing_constant"),
            "hb_usage_constant": cp.Parameter(nonneg=True, name="hb_usage_constant")
        }
        # We set stoichiometric and yield parameters
        self.conversion_fun_params = {
            "nh3_per_tonne_h2": cp.Parameter(nonneg=True, name="nh3_per_tonne_h2"),
            "hb_yield": cp.Parameter(nonneg=True, name="hb_yield")
        }
        return

    def define_structure(self, asset_structure):
        super().define_structure(asset_structure)
        self.target_node_location = self.source_node_location
        # flows are H2 mass per hour (tonnes/h)
        self.flows = cp.Variable(self.number_of_edges, nonneg=True)
        return

    def build_edge(self, edge_number):
        super().build_edge(edge_number)
        return

    def _update_parameters(self):
        super()._update_parameters()

        return
