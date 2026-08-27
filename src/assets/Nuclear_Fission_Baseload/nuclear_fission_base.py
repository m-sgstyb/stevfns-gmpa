#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import cvxpy as cp
import numpy as np
from ..Base_Stock_Assets import Stock_Asset_STEVFNs
from ...network import Edge_STEVFNs


class Nuclear_Fission_Baseload_Asset(Stock_Asset_STEVFNs):
    """
    Class for Inflexible nuclear generator for temporal pathways
    Produces constant output equal to:
        capacity_factor * nameplate_capacity
    at every hour.
    """
    asset_name = "Nuclear_Fission_Baseload"
    source_node_type = "NULL"
    target_node_type = "EL"
    stock_node_type = "Nuclear_Stock"
    decommission_mode = "decay_rate"
    transport_time = 0
    period = 1

    def define_structure(self, asset_structure):
        self.asset_structure = asset_structure
        self.source_node_location = asset_structure["Location_1"]
        self.target_node_location = self.source_node_location
        self.stock_node_location = self.source_node_location
        self.source_node_times = np.arange(asset_structure["Start_Time"] + self.transport_time, 
                                           asset_structure["End_Time"] + self.transport_time, 
                                           self.period)
        self.target_node_times = np.arange(asset_structure["Start_Time"] + self.transport_time, 
                                           asset_structure["End_Time"] + self.transport_time, 
                                           self.period)
        self.number_of_edges = len(self.source_node_times)
        self._define_period_structure(asset_structure)
        self.period_change_indices = self._get_period_change_indices()
        self.period_boundaries = self.period_change_indices + [self.number_of_edges]
        self._period_expand_matrix = self._build_period_expand_matrix() # carryover_out as hourly expression
        self.gen_profile = cp.Parameter(shape=self.number_of_edges, nonneg=True,
                                        name=f'gen_profile_{self.asset_name}')
        # Output flows as hourly expression
        self.flows = cp.multiply(self._period_expand_matrix @ self.carryover_out, self.gen_profile)
        self.cost_fun_params = {"sizing_constant": cp.Parameter(shape=(self.num_periods, self.num_periods), nonneg=True,
                                                                name=f"sizing_cost_{self.asset_name}"),
                                "usage_constant": cp.Parameter(self.number_of_edges, nonneg=True,
                                                                name=f"usage_cost_{self.asset_name}"),
                                "terminal_charge": cp.Parameter(shape=(self.num_periods,), nonneg=True,
                                                                name=f"terminal_charge_{self.asset_name}"),
                }
        self.conversion_fun_params = {
            "capacity_factor": cp.Parameter(nonneg=True,
                                           name=f"capacity_factor_{self.asset_name}")
        }
        return

    def _build_period_expand_matrix(self):
        """Matrix shape (number_of_edges, num_periods)
        expand_matrix @ carryover_out gives carryover_out broadcast
        to hourly resolution to build gen profile for costs
        """
        matrix = np.zeros((self.number_of_edges, self.num_periods))
        for p in range(self.num_periods):
            start, end = self.period_boundaries[p], self.period_boundaries[p + 1]
            matrix[start:end, p] = 1
        return matrix

    def _build_generation_edges(self):
        self._hourly_edges = []
        for edge_number in range(self.number_of_edges):
            target_node_time = self.target_node_times[edge_number]
            period_index = self._period_index_for_edge(edge_number)

            new_edge = Edge_STEVFNs()
            self.edges.append(new_edge)
            self._hourly_edges.append(new_edge)
            new_edge.attach_target_node(self.network.extract_node(
                self.target_node_location, self.target_node_type, target_node_time))
            new_edge.flow = self.flows[edge_number]
        return

    def build_edges(self):
        self.edges = []
        self._build_generation_edges()
        self._build_stock_edges()
        return

    def _load_baseline_capex(self):
        return np.full(self.num_periods, float(self.parameters_df["sizing_constant"]))

    def _update_usage_constant(self):
        sampled_days = int((self.number_of_edges / 24) / self.num_years) # per year
        simulation_factor = 365 / sampled_days
        discount_rate = self.network.system_parameters_df.loc["discount_rate", "value"]

        raw_cost = float(self.parameters_df["usage_constant"])  # scalar $/unit flow from parameters.csv
        discount_factors = (1 / (1 + discount_rate)) ** np.arange(self.num_years)
        yearly_costs = raw_cost * discount_factors * simulation_factor  # shape (num_years,)

        year_indices = self._get_year_change_indices() + [self.number_of_edges]
        expanded_costs = np.zeros(self.number_of_edges)
        # Expand each re-scaled and discounted NPV of usage costs to hourly profile
        for i, (start, end) in enumerate(zip(year_indices[:-1], year_indices[1:])):
            expanded_costs[start:end] = yearly_costs[i]

        self.cost_fun_params["usage_constant"].value = expanded_costs
        return
    
    def _load_CF_profile(self):
        """
        Build a gen_profile array of length number_of_edges by repeating the scalar
        user-input capacity_factor (share of nameplate capacity stable output).
        """
        cf_scalar = float(self.parameters_df["capacity_factor"])
        profile = np.full(self.number_of_edges, cf_scalar, dtype=float)
        # assign to parameter
        self.gen_profile.value = profile
        return

    def _update_parameters(self):
        sizing_constant = self._load_baseline_capex()
        self._update_sizing_constant(sizing_constant)
        self._update_new_capacity_decom_mask()
        self._update_existing_capacity_vec()
        self._update_usage_constant()
        self._load_CF_profile()
        return
