#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import cvxpy as cp
from ..Base_Stock_Assets import Stock_Asset_STEVFNs
from ...network import Edge_STEVFNs
import numpy as np


class H2_to_EL_Asset(Stock_Asset_STEVFNs):
    """
    Class of H2 to Electricity conversion asset
    """
    asset_name = "H2_to_EL"
    source_node_type = "H2"
    target_node_type = "EL"
    target_node_type_2 = "H2_to_EL_Capacity"
    stock_node_type = "H2_to_EL_Stock"
    decommission_mode = "decay_rate"
    period = 1
    transport_time = 0

    @staticmethod
    def conversion_fun(flows, params):
        conversion_factor = params["conversion_factor"]
        return conversion_factor * flows
    
    def __init__(self):
        super().__init__()
        self.conversion_fun_params = {"conversion_factor": cp.Parameter(nonneg=True,
                                                                        name=f"conversion_factor_{self.asset_name}")}
        return
    
    def define_structure(self, asset_structure):
        self.asset_structure = asset_structure
        self.source_node_location = asset_structure["Location_1"]
        self.source_node_times = np.arange(asset_structure["Start_Time"] + self.transport_time,
                                            asset_structure["End_Time"] + self.transport_time,
                                            self.period)
        self.target_node_location = self.source_node_location
        self.target_node_times = np.arange(asset_structure["Start_Time"] + self.transport_time,
                                            asset_structure["End_Time"] + self.transport_time,
                                            self.period)
        self.target_node_location_2 = self.source_node_location
        self.stock_node_location = self.source_node_location

        self.number_of_edges = len(self.source_node_times)

        self._define_period_structure(asset_structure)
        self.period_change_indices = self._get_period_change_indices()
        self.period_boundaries = self.period_change_indices + [self.number_of_edges]

        self.flows = cp.Variable(self.number_of_edges, nonneg=True, name=f"flows_{self.asset_name}")
        self.cost_fun_params = {"sizing_constant": cp.Parameter(shape=(self.num_periods, self.num_periods), nonneg=True,
                                                                  name=f"sizing_cost_{self.asset_name}"),
                                "usage_constant": cp.Parameter(self.number_of_edges, nonneg=True,
                                                                 name=f"usage_cost_{self.asset_name}"),
                                "terminal_charge": cp.Parameter(shape=(self.num_periods,), nonneg=True,
                                                                name=f"terminal_charge_{self.asset_name}")}

        self.conversion_fun_params = {"conversion_factor": cp.Parameter(nonneg=True,
                                                                          name=f"conversion_factor_{self.asset_name}")}
        return

    def build_edges(self):
        self.edges = []
        for edge_number in range(self.number_of_edges):
            self.build_edge(edge_number)
        self._build_stock_edges()
        self._build_capacity_limit_edges()
        return

    def _build_capacity_limit_edges(self):
        """Caps hourly H2 throughput within each period at that period's
        available stock (carryover_out[p])."""
        for p in range(self.num_periods):
            start, end = self.period_boundaries[p], self.period_boundaries[p + 1]
            period_flows = self.flows[start:end]

            edge = Edge_STEVFNs()
            self.edges.append(edge)
            edge.attach_target_node(self.network.extract_node(
                self.target_node_location_2, self.target_node_type_2, p))
            edge.flow = self.carryover_out[p] - cp.max(period_flows)
        return

    def _get_year_change_indices(self):
        hours_per_day = 24
        days_per_year = int((self.number_of_edges / hours_per_day) / self.num_years)
        hours_per_year = days_per_year * hours_per_day
        self.year_change_indices = [i * hours_per_year for i in range(self.num_years)]
        return list(self.year_change_indices)

    def _update_usage_constant(self):
        sampled_days = int((self.number_of_edges / 24) / self.num_years)
        simulation_factor = 365 / sampled_days
        discount_rate = self.network.system_parameters_df.loc["discount_rate", "value"]

        raw_cost = float(self.parameters_df["usage_constant"])  # scalar $/unit flow from parameters.csv
        discount_factors = (1 / (1 + discount_rate)) ** np.arange(self.num_years)
        yearly_costs = raw_cost * discount_factors * simulation_factor  # shape (num_years,)

        year_indices = self._get_year_change_indices() + [self.number_of_edges]
        expanded_costs = np.zeros(self.number_of_edges)
        for i, (start, end) in enumerate(zip(year_indices[:-1], year_indices[1:])):
            expanded_costs[start:end] = yearly_costs[i]

        self.cost_fun_params["usage_constant"].value = expanded_costs
        return

    def _load_baseline_capex(self):
        """Scalar baseline capex ($/unit capacity), broadcast into a per-period
        vector so it can be passed through the same _update_sizing_constant()
        amortisation/NPV pipeline as every other stock asset."""
        baseline_capex = float(self.parameters_df["sizing_constant"])
        return np.full(self.num_periods, baseline_capex)

    def _update_parameters(self):
        self.conversion_fun_params["conversion_factor"].value = float(self.parameters_df["conversion_factor"])
        self._update_usage_constant()

        sizing_constant_vec = self._load_baseline_capex()
        self._get_lifetime_periods()
        self._update_sizing_constant(sizing_constant_vec)
        self._update_new_capacity_decom_mask()
        self._update_existing_capacity_vec()
        return

    def get_hourly_flows(self):
        return self.flows.value

    def get_period_flows(self):
        flows_full = np.array(self.get_hourly_flows())
        return [flows_full[start:end]
                for start, end in zip(self.period_boundaries[:-1], self.period_boundaries[1:])]

    def get_asset_sizes(self):
        asset_identity = self.asset_name + r"_location_" + str(self.source_node_location)
        return {asset_identity: self.size()}
