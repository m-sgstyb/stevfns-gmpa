#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import numpy as np
import cvxpy as cp
from ..Base_Stock_Assets import Stock_Asset_STEVFNs
from ...network import Edge_STEVFNs

class PP_CO2_Asset(Stock_Asset_STEVFNs):
    """
    Generic fossil generator with an explicit new-build capacity stock and a
    separate hourly dispatch variable, capped per period at available
    operating stock (carryover_out).
    """
    asset_name = "PP_CO2"
    source_node_type = "NULL"
    target_node_type = "EL"
    target_node_type_2 = "CO2_Budget"
    target_node_type_3 = "PP_CO2_Capacity"
    stock_node_type = "PP_CO2_Stock"
    decommission_mode = "decay_rate" # For pre-model existing capacity value only
    period = 1
    transport_time = 0

    @staticmethod
    def conversion_fun_2(flows, params):
        CO2_emissions_factor = params["CO2_emissions_factor"]
        return -CO2_emissions_factor * flows

    def __init__(self):
        super().__init__()
        self.conversion_fun_params_2 = {"CO2_emissions_factor": cp.Parameter(nonneg=True)}
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
        self.target_node_location_2 = 0 # Global CO2 emissions node
        self.stock_node_location = self.source_node_location
        self.target_node_location_3 = self.source_node_location

        self.number_of_edges = len(self.source_node_times)

        self._define_period_structure(asset_structure)
        self.period_change_indices = self._get_period_change_indices()
        self.period_boundaries = self.period_change_indices + [self.number_of_edges]

        
        self.flows = cp.Variable(self.number_of_edges, nonneg=True, name=f"flows_{self.asset_name}")
        self.cost_fun_params = {"sizing_constant": cp.Parameter(shape=(self.num_periods, self.num_periods), nonneg=True,
                                                                name=f"sizing_cost_{self.asset_name}"),
                                "usage_constant": cp.Parameter(self.number_of_edges, nonneg=True,
                                                                name=f"usage_cost_{self.asset_name}"),
                                "terminal_charge": cp.Parameter(shape=(self.num_periods,), nonneg=True,   # limit bias
                                                                   name=f"terminal_charge_{self.asset_name}"),
        }

        self.conversion_fun_params_2 = {"CO2_emissions_factor": cp.Parameter(nonneg=True,
                                                                               name=f"emissions_factor_{self.asset_name}")}
        return

    def build_edges(self):
        self.edges = []
        for edge_number in range(self.number_of_edges):
            self.build_edge(edge_number)
        self._build_stock_edges()
        self._build_capacity_limit_edges()
        for period in range(self.num_periods):
            self._build_emissions_edge_for_period(period)
        return

    def _build_capacity_limit_edges(self):
        """Caps hourly dispatch within each period at that period's
        available stock (carryover_out[p])."""
        for p in range(self.num_periods):
            start, end = self.period_boundaries[p], self.period_boundaries[p + 1]
            period_flows = self.flows[start:end]

            edge = Edge_STEVFNs()
            self.edges.append(edge)
            edge.attach_target_node(self.network.extract_node(
                self.target_node_location_3, self.target_node_type_3, p))
            edge.flow = self.carryover_out[p] - cp.max(period_flows)
        return

    def _build_emissions_edge_for_period(self, period_number):
        start, end = self.period_boundaries[period_number], self.period_boundaries[period_number + 1]
        period_flows = self.flows[start:end]

        self.period_emissions_sum = cp.sum(self.conversion_fun_2(period_flows, self.conversion_fun_params_2))
        hours_per_day = 24
        sampled_days = int((self.number_of_edges / hours_per_day) / self.num_years)
        self.period_emissions_sum *= (365 / sampled_days)

        edge = Edge_STEVFNs()
        self.edges.append(edge)
        edge.attach_source_node(self.network.extract_node(
            self.source_node_location, self.source_node_type, period_number))
        edge.attach_target_node(self.network.extract_node(
            self.target_node_location_2, self.target_node_type_2, period_number))
        edge.flow = self.period_emissions_sum
        return

    def _get_year_change_indices(self):
        """ Year change indices over horizon based on sample size"""
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
        for parameter_name, parameter in self.conversion_fun_params_2.items():
            parameter.value = self.parameters_df[parameter_name]
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

    def get_period_emissions(self):
        flows_full = np.array(self.get_hourly_flows())
        emissions_per_period = []
        for period in range(0,self.num_periods):
            start, end = self.period_boundaries[period], self.period_boundaries[period + 1]
            period_flows = self.flows[start:end]
            period_emissions = cp.sum(self.conversion_fun_2(period_flows, self.conversion_fun_params_2))
            hours_per_day = 24
            sampled_days = int((self.number_of_edges / hours_per_day) / self.num_years)
            period_emissions *= (365 / sampled_days)
            emissions_per_period.append(-period_emissions.value) # return positive value for emissions from this asset
        return emissions_per_period


    def get_asset_sizes(self):
        asset_identity = self.asset_name + r"_location_" + str(self.source_node_location)
        return {asset_identity: self.size()}