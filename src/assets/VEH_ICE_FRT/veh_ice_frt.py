#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import numpy as np
import cvxpy as cp
from ..Base_Vehicle_Assets import Base_Vehicle_Asset_STEVFNs
from ...network import Edge_STEVFNs

class VEH_ICE_FRT_Asset(Base_Vehicle_Asset_STEVFNs):
    """
    Class of Freight Internal Combustion Engine Vehicle Fleet
    """
    asset_name = "VEH_ICE_FRT"
    source_node_type = "NULL"
    target_node_type = "FRT" # Freight demand node
    target_node_type_co2 = "CO2_Budget"
    period = 1
    transport_time = 0
    
    @staticmethod
    def conversion_fun_2(flows, params):
        emissions_factor = params["emissions_factor"]
        return -emissions_factor * flows

    def __init__(self):
        super().__init__()
        self.conversion_fun_params_2 = {
            "emissions_factor": cp.Parameter(nonneg=True,
                                                name=f"emissions_factor_{self.asset_name}")
        }
        return

    def define_structure(self, asset_structure):
        super().define_structure(asset_structure)
        self.target_node_location_2 = 0 # Conventionally loc 0 for CO2_Budget
        return

    def build_edges(self):
        super().build_edges()
        self.emissions_edges = []
        for p in range(self.num_periods):
            self._build_emissions_edge_for_period(p)
        return

    def _build_emissions_edge_for_period(self, period_number):
        start, end = self.period_boundaries[period_number], self.period_boundaries[period_number + 1]
        period_flows = self.flows[start:end]
        annualisation_factor = self._annualisation_factor()
        period_emissions_sum = cp.sum(self.conversion_fun_2(period_flows, self.conversion_fun_params_2))
        period_emissions_sum *= annualisation_factor

        edge = Edge_STEVFNs()
        self.edges.append(edge)
        self.emissions_edges.append(edge)
        edge.attach_source_node(self.network.extract_node(
            self.source_node_location, self.source_node_type, period_number))
        edge.attach_target_node(self.network.extract_node(
            self.target_node_location_2, self.target_node_type_co2, period_number))
        edge.flow = period_emissions_sum
        return

    def _update_parameters(self):
        super()._update_parameters()
        self.conversion_fun_params_2["emissions_factor"].value = float(self.parameters_df["emissions_factor"])
        return

    def get_period_emissions(self):
        period_totals = [-edge.flow.value for edge in self.emissions_edges]
        return np.array([total / self._years_in_period(p) for p, total in enumerate(period_totals)])