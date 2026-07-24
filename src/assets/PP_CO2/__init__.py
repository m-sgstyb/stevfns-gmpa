#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Nov  3 13:25:54 2021

@author: aniqahsan
Adapted for time-dependence, 2026
@contributor: Mónica Sagastuy Breña
"""

import numpy as np
import cvxpy as cp
from ..Base_Assets import Asset_STEVFNs
from ...network import Edge_STEVFNs

class PP_CO2_Asset(Asset_STEVFNs):
    """Existing-capacity fossil generator with annual CO2 accounting.
    Now new investments"""

    asset_name = "PP_CO2"
    source_node_type = "NULL"
    target_node_type = "EL"
    target_node_type_2 = "CO2_Budget"
    source_node_type_3 = "NULL"
    target_node_type_3 = "PP_CO2_Capacity"
    period = 1
    transport_time = 0

    @staticmethod
    def cost_fun(flows, params):
        usage_constant_1 = params["usage_constant_1"]  # shape: (n_timesteps,)
        return cp.sum(cp.multiply(usage_constant_1, flows))

    @staticmethod
    def conversion_fun_2(flows, params):
        """Emissions conversion: negative sign so it enters as a budget draw-down."""
        CO2_emissions_factor = params["CO2_emissions_factor"]
        return -CO2_emissions_factor * flows

    @staticmethod
    def conversion_fun_3(flows, params):
        """Caps hourly dispatch at the asset's existing capacity."""
        existing_capacity = params["existing_capacity"]
        return existing_capacity - cp.max(flows)

    def __init__(self):
        super().__init__()
        self.cost_fun_params = {"usage_constant_1": cp.Parameter(nonneg=True)}
        self.conversion_fun_params_2 = {"CO2_emissions_factor": cp.Parameter(nonneg=True)}
        self.conversion_fun_params_3 = {"existing_capacity": cp.Parameter(nonneg=True)}
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
        # CO2 budget node: individual per-location budget (not global) -- matches
        # source_node_location so each country/location tracks its own emissions
        self.target_node_location_2 = self.source_node_location
        self.source_node_location_3 = "NULL"
        self.target_node_location_3 = self.source_node_location

        self.number_of_edges = len(self.source_node_times)
        self.num_years = int(self.network.system_parameters_df.loc["project_life", "value"] / 8760)
        self.reinvestment_period = int(self.network.system_parameters_df.loc["reinvestment_period", "value"] / 8760)
        self.num_periods = int(np.ceil(self.num_years / self.reinvestment_period))

        self.flows = cp.Variable(self.number_of_edges, nonneg=True, name=f"flows_{self.asset_name}")
        self.cost_fun_params = {"usage_constant_1": cp.Parameter(shape=(self.number_of_edges,), nonneg=True,
                                                                   name=f"usage_cost_{self.asset_name}")}
        self.conversion_fun_params_2 = {"CO2_emissions_factor": cp.Parameter(nonneg=True,
                                                                               name=f"emissions_factor_{self.asset_name}")}
        return

    def build_edges(self):
        super().build_edges()
        period_change_indices = self._get_period_change_indices() + [self.number_of_edges]
        for period in range(self.num_periods):
            self._build_emissions_edge_for_period(period, period_change_indices)
        self._build_capacity_limit_edge()
        return

    def _build_emissions_edge_for_period(self, period_number, period_change_indices):
        """One emissions edge per reinvestment period, summing hourly emissions
        across all years in that period. Lands on the same CO2_Budget node
        time-key (period_number) that CO2_Budget_Asset writes its budget to."""
        start = period_change_indices[period_number]
        end = period_change_indices[period_number + 1]
        period_flows = self.flows[start:end]

        period_emissions_sum = cp.sum(self.conversion_fun_2(period_flows, self.conversion_fun_params_2))

        # Scale emissions from sampled representative days up to aproximate 
        # full (non-leap) calendar year time under assumptions.
        hours_per_day = 24
        sampled_days = int((self.number_of_edges / hours_per_day) / self.num_years)
        emission_scaling_factor = 365 / sampled_days
        period_emissions_sum *= emission_scaling_factor

        edge = Edge_STEVFNs()
        self.edges.append(edge)
        edge.attach_source_node(self.network.extract_node(
            self.source_node_location, self.source_node_type, period_number))
        edge.attach_target_node(self.network.extract_node(
            self.target_node_location_2, self.target_node_type_2, period_number))
        edge.flow = period_emissions_sum
        return

    def _build_capacity_limit_edge(self):
        """Caps hourly dispatch at existing_capacity via conversion_fun_3."""
        new_edge = Edge_STEVFNs()
        self.edges += [new_edge]
        new_edge.attach_target_node(self.network.extract_node(
            self.target_node_location_3, self.target_node_type_3, 0))
        new_edge.flow = self.flows
        new_edge.conversion_fun = self.conversion_fun_3
        new_edge.conversion_fun_params = self.conversion_fun_params_3
        return

    def _get_year_change_indices(self):
        hours_per_day = 24
        days_per_year = int((self.number_of_edges / hours_per_day) / self.num_years)
        hours_per_year = days_per_year * hours_per_day
        self.year_change_indices = [i * hours_per_year for i in range(self.num_years)]
        return list(self.year_change_indices)

    def _get_period_change_indices(self):
        """Hourly index at which each reinvestment period starts (same
        convention as RE_PV_Stock_Asset's version)."""
        hours_per_day = 24
        days_per_year = int((self.number_of_edges / hours_per_day) / self.num_years)
        hours_per_year = days_per_year * hours_per_day
        hours_per_period = hours_per_year * self.reinvestment_period
        self.period_change_indices = [i * hours_per_period for i in range(self.num_periods)]
        return list(self.period_change_indices)

    def process_csv_values(self, values):
        """Converts a comma-separated string to a NumPy array of floats,
        or returns the original numeric value wrapped in a 1-element array.
        (A bare np.array(scalar) would produce a 0-d array, which breaks
        any later [0] indexing.)"""
        if isinstance(values, str):
            return np.array([float(x) for x in values.split(",")], dtype=float)
        return np.array([values], dtype=float)

    def _update_usage_constants(self):
        """
        Builds the full-length hourly usage-cost vector from a scalar or
        per-year input, applying NPV discounting and simulation scaling.
        """
        sampled_days = int((self.number_of_edges / 24) / self.num_years)
        simulation_factor = 365 / sampled_days
        discount_rate = self.network.system_parameters_df.loc["discount_rate", "value"]

        raw_costs = self.process_csv_values(self.parameters_df["usage_constant_1"])
        if raw_costs.size == 1:
            raw_costs = np.full(self.num_years, raw_costs[0])
        elif raw_costs.size != self.num_years:
            raise ValueError(f"Expected {self.num_years} yearly usage cost values, got {raw_costs.size}")

        discount_factors = (1 / (1 + discount_rate)) ** np.arange(self.num_years)
        yearly_costs = raw_costs * discount_factors * simulation_factor

        year_indices = self._get_year_change_indices() + [self.number_of_edges]
        expanded_costs = np.zeros(self.number_of_edges)
        for i, (start, end) in enumerate(zip(year_indices[:-1], year_indices[1:])):
            expanded_costs[start:end] = yearly_costs[i]

        self.cost_fun_params["usage_constant_1"].value = expanded_costs
        return

    def _update_parameters(self):
        for parameter_name, parameter in self.conversion_fun_params_2.items():
            parameter.value = self.parameters_df[parameter_name]
        for parameter_name, parameter in self.conversion_fun_params_3.items():
            parameter.value = self.parameters_df[parameter_name]
        self._update_usage_constants()
        return

    def peak_generation(self):
        """Yearly peak fossil generation (hourly peak per modelled year)."""
        if self.flows.value is None:
            return None
        year_indices = self._get_year_change_indices() + [len(self.flows.value)]
        return np.array([
            np.max(self.flows.value[start:end])
            for start, end in zip(year_indices[:-1], year_indices[1:])
        ])

    def get_asset_sizes(self):
        asset_size = self.size()
        asset_identity = self.asset_name + r"_location_" + str(self.source_node_location)
        return {asset_identity: asset_size}

    def get_period_emissions(self):
        """Emissions edges sit right after the hourly generation edges, one per
        reinvestment period."""
        emissions_edges_start = self.number_of_edges
        emissions_edges_end = self.number_of_edges + self.num_periods
        return [-self.edges[i].flow.value for i in range(emissions_edges_start, emissions_edges_end)]

    def get_yearly_flows(self):
        """Flow slices split by each year."""
        if not hasattr(self, "year_change_indices"):
            self._get_year_change_indices()

        flows_full = self.flows.value
        if flows_full is None:
            raise ValueError("Flow values not assigned yet.")
        if not isinstance(flows_full, np.ndarray):
            flows_full = np.array(flows_full)

        year_indices = list(self.year_change_indices) + [self.number_of_edges]
        return [flows_full[start:end] for start, end in zip(year_indices[:-1], year_indices[1:])]

    def get_yearly_usage_costs(self):
        """Yearly total usage payments (discounted), from hourly flows and costs."""
        hourly_costs = self.cost_fun_params["usage_constant_1"].value
        hourly_flows = self.flows.value
        if hourly_costs is None or hourly_flows is None:
            raise ValueError("Cost or flow values not set.")

        total_hourly_costs = hourly_costs * hourly_flows
        year_indices = list(self.year_change_indices) + [self.number_of_edges]
        return [
            np.sum(total_hourly_costs[start:end])
            for start, end in zip(year_indices[:-1], year_indices[1:])
        ][:self.num_years]