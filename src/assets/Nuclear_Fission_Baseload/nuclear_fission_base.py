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

    DPP compliance note: hourly generation is gen_profile[t] * carryover_out[p(t)]
    (param * var). The usage cost on that generation would add a second param (usage_constant)
    to that product, and since both are known before solving they are multiplied in NumPy
    and summed per period into usage_weight[p]
    usage_cost then becomes sum_p usage_weight[p] * carryover_out[p] (param * var)
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
        # usage constant not a separate parameter, computed for usage_weight
        self.cost_fun_params = {"sizing_constant": cp.Parameter(shape=(self.num_periods, self.num_periods), nonneg=True,
                                                                name=f"sizing_cost_{self.asset_name}"),
                                "terminal_charge": cp.Parameter(shape=(self.num_periods,), nonneg=True,
                                                                name=f"terminal_charge_{self.asset_name}"),
                }
        self.usage_weight = cp.Parameter(shape=(self.num_periods,), nonneg=True,
                                         name=f"usage_weight_{self.asset_name}")
        self.usage_hourly = None # NumPy hourly usage costs, set in _update_usage_constant
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

    def build_cost(self):
        """Capital + terminal charge plus usage cost expressed on carryover_out via
        the precomputed period weights
        """
        params = self.cost_fun_params
        capital_cost = cp.sum(params["sizing_constant"] @ self.new_capacity)
        terminal_charge = cp.sum(cp.multiply(params["terminal_charge"], self.new_capacity))
        usage_cost = cp.sum(cp.multiply(self.usage_weight, self.carryover_out))
        self.cost = capital_cost + usage_cost + terminal_charge
        return

    def _load_baseline_capex(self):
        return np.full(self.num_periods, float(self.parameters_df["sizing_constant"]))

    def _update_usage_constant(self):
        """NPV-discounted, annualised hourly usage cost
        as plain NumPy vector (outside of CVXPY)
        """
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
        self._usage_hourly = expanded_costs
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

    def _update_usage_weight(self):
        """usage_weight[p] = sum over hours t in period p of
        usage_hourly[t] * gen_profile[t]
        """
        hourly_weight = self._usage_hourly * np.array(self.gen_profile.value)
        self.usage_weight.value = np.array([
            hourly_weight[start:end].sum()
            for start, end in zip(self.period_boundaries[:-1], self.period_boundaries[1:])
        ])
        return

    def _update_parameters(self):
        sizing_constant = self._load_baseline_capex()
        self._update_sizing_constant(sizing_constant)
        self._update_new_capacity_decom_mask()
        self._update_existing_capacity_vec()
        self._update_usage_constant()
        self._load_CF_profile()
        self._update_usage_weight() # after usage and gen profile
        return

    # --- Result extraction

    def get_hourly_flows(self):
        return np.array([edge.flow.value for edge in self._hourly_edges])

    def get_period_flows(self):
        flows_full = self.get_hourly_flows()
        return [flows_full[start:end] 
                for start, end in zip(self.period_boundaries[:-1], self.period_boundaries[1:])]

    def get_period_costs(self):
        """Per-period annualised cost. 
        Capital repayments + usage costs averaged over the modelled years in 
        each period. The terminal charge is exlcluded, as in the base class. 
        Overrides base version as the usage_constant parameter changes in this
        asset class
        """
        M = self.cost_fun_params["sizing_constant"].value
        new_capacity = self.new_capacity.value
        carryover = self.carryover_out.value
        if M is None or new_capacity is None or carryover is None:
            return None
        period_capital = np.array(M) @ np.array(new_capacity)
        period_usage = np.array(self.usage_weight.value) * np.array(carryover)
        period_total = period_capital + period_usage
        return np.array([period_total[p] / self._years_in_period(p)
                         for p in range(self.num_periods)]) 
