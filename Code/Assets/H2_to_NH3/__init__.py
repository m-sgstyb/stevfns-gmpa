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
          - 'conversion_factor_stoich' : NH3_per_H2_mass (tonnes NH3 per tonne H2)
          - 'conversion_factor_yield' : fraction (0-1) capturing overall conversion assuming recycling H2 and N2 into the reactor
        """
        conversion_factor_stoich = params["conversion_factor_stoich"]
        conversion_factor_yield = params["conversion_factor_yield"]
        return flows * conversion_factor_stoich * conversion_factor_yield

    def __init__(self):
        super().__init__()
        self.cost_fun_params = {
            "sizing_constant": cp.Parameter(nonneg=True, name=f"sizing_constant_{self.asset_name}"),
            "usage_constant": cp.Parameter(nonneg=True, name=f"usage_constant_{self.asset_name}")
        }
        # Set stoichiometric and yield parameters
        self.conversion_fun_params = {
            "conversion_factor_stoich": cp.Parameter(nonneg=True, name=f"conversion_factor_stoich_{self.asset_name}"),
            "conversion_factor_yield": cp.Parameter(nonneg=True, name=f"conversion_factor_yield_{self.asset_name}") # process efficiency
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
