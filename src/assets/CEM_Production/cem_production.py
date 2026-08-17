#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import numpy as np
import cvxpy as cp
from ..Base_Stock_Assets import Stock_Asset_STEVFNs
from ...network import Edge_STEVFNs


class CEM_Production_Asset(Stock_Asset_STEVFNs):
    """
    Time-dependent Conventional cement production asset
    """
    asset_name = "CEM_Production"
    source_node_type = "NULL"
    target_node_type = "CEM"                           # year-indexed cement demand node
    target_node_type_2 = "CO2_Budget"                  # period-indexed emissions node
    target_node_type_3 = "CEM_Production_Capacity"     # period-indexed capacity-limit node
    el_node_type = "EL"                                # hourly electricity node
    stock_node_type = "CEM_Production_Stock"
    decommission_mode = "decay_rate"
    capacity_unit = "Mt cement/yr"
    period = 1
    transport_time = 0

    @staticmethod
    def process_emissions_fun(flows, params):
        """Process (calcination) CO2e per unit cement produced
        (MtCO2/Mt cement)."""
        process_emissions_factor = params["process_emissions_factor"]
        clinker_to_cement_ratio = params["clinker_to_cement_ratio"] # Mt clinker/Mt cement
        return (-process_emissions_factor * clinker_to_cement_ratio) * flows

    @staticmethod
    def fuel_emissions_fun(flows, params):
        """Fuel/kiln-heat CO2e per unit cement produced (MtCO2/Mt
        cement). Specific to a carbon based fuel-fired kiln tech type"""
        fuel_emissions_factor = params["fuel_emissions_factor"]
        return -fuel_emissions_factor * flows

    @staticmethod
    def electricity_fun(flows, params):
        """Combined electricity draw per unit cement produced
        (GWh/Mt cement)."""
        electricity_intensity = params["electricity_intensity"]
        return electricity_intensity * flows

    def __init__(self):
        self.process_emissions_fun_params = {
            "process_emissions_factor": cp.Parameter(nonneg=True,
                                                    name=f"process_emissions_factor_{self.asset_name}"),
            "clinker_to_cement_ratio": cp.Parameter(nonneg=True,
                                                    name=f"clinker_to_cement_ratio_{self.asset_name}"),                                           }
        self.fuel_emissions_fun_params = {
            "fuel_emissions_factor": cp.Parameter(nonneg=True,
                                                  name=f"fuel_emissions_factor_{self.asset_name}")}
        self.electricity_fun_params = {
            "electricity_intensity": cp.Parameter(nonneg=True, name=f"electricity_intensity_{self.asset_name}")}
        return

    def define_structure(self, asset_structure):
        self.asset_structure = asset_structure
        self.target_node_location = asset_structure["Location_1"]
        self.stock_node_location = asset_structure["Location_1"]
        self.target_node_location_2 = 0 # CO2 Budget node location set to 0 conventionally for global emissions budget node
        self.target_node_location_3 = asset_structure["Location_1"]
        self.el_node_location = asset_structure["Location_1"]

        self.target_node_times = np.arange(asset_structure["Start_Time"],
                                            asset_structure["End_Time"], self.period)
        self.number_of_edges = len(self.target_node_times)

        self._define_period_structure(asset_structure)   # sets num_years, num_periods, reinvestment_period, ...
        self.period_change_indices = self._get_period_change_indices()
        self.period_boundaries = self.period_change_indices + [self.number_of_edges]
        self.year_change_indices = self._get_year_change_indices()
        self.year_boundaries = self.year_change_indices + [self.number_of_edges]
        # Allowing variable production of cement at hourly resolution
        self.flows = cp.Variable(self.number_of_edges, nonneg=True, name=f"flows_{self.asset_name}")
        self.cost_fun_params = {
            "sizing_constant": cp.Parameter(shape=(self.num_periods, self.num_periods), nonneg=True,
                                             name=f"sizing_constant_{self.asset_name}"),
            "usage_constant": cp.Parameter(self.number_of_edges, nonneg=True,
                                            name=f"usage_constant_{self.asset_name}"),
            "terminal_charge": cp.Parameter(shape=(self.num_periods,), nonneg=True,   # limit bias
                                   name=f"terminal_charge_{self.asset_name}"),
        }
        return

    def build_edges(self):
        # Track different kinds of edges in asset
        self.edges = []
        self._electricity_edges = []
        self._capacity_edges = []
        self._production_edges = []
        self._process_emissions_edges = []
        self._fuel_emissions_edges = []

        self._build_capacity_availability_edges()
        for edge_number in range(self.number_of_edges):
            self._build_electricity_edge(edge_number)
            self._build_production_edge(edge_number)  
        self._build_stock_edges()
        for period in range(self.num_periods):
            self._build_process_emissions_edge_for_period(period)
            self._build_fuel_emissions_edge_for_period(period)
        return

    def _build_capacity_availability_edges(self):
        """
        Annual node holding the available capacity that year to limit
        total production from this technology

        Hourly production edges draw from each annual node
        """
        for y in range(self.num_years):
            p = self._period_for_year(y)
            edge = Edge_STEVFNs()
            self.edges.append(edge)
            self._capacity_edges.append(edge)
            edge.attach_target_node(self.network.extract_node(
                self.target_node_location_3, self.target_node_type_3, y))
            edge.flow = self.carryover_out[p]
            
    def _build_electricity_edge(self, edge_number):
        """Hourly electricity draw from the EL node."""
        new_edge = Edge_STEVFNs()
        self.edges.append(new_edge)
        self._electricity_edges.append(new_edge)
        new_edge.attach_source_node(self.network.extract_node(
            self.el_node_location, self.el_node_type, self.target_node_times[edge_number]))
        new_edge.flow = self.electricity_fun(self.flows[edge_number], self.electricity_fun_params)
        return

    def _build_production_edge(self, edge_number):
        """Hourly cement production edge from available capacity node
        into the hourly CEM demand node"""
        year_number = self._year_for_edge(edge_number)
        annualisation_factor = self._annualisation_factor()
        edge = Edge_STEVFNs()
        self.edges.append(edge)
        self._production_edges.append(edge)
        edge.attach_source_node(self.network.extract_node(
            self.target_node_location_3, self.target_node_type_3, year_number)) # annual capacity available
        edge.attach_target_node(self.network.extract_node(
            self.target_node_location, self.target_node_type, self.target_node_times[edge_number])) # hourly production
        edge.flow = self.flows[edge_number] * annualisation_factor # scale by annualisation to approximate annual demand
        return
    
    def _build_process_emissions_edge_for_period(self, period_number):
        """Period-indexed process emissions to CO2 Budget"""
        start, end = self.period_boundaries[period_number], self.period_boundaries[period_number + 1]
        period_flows = self.flows[start:end]
        period_annualisation_factor = self._annualisation_factor()
        period_emissions = cp.sum(
            self.process_emissions_fun(period_flows, self.process_emissions_fun_params)
        ) * period_annualisation_factor

        edge = Edge_STEVFNs()
        self.edges.append(edge)
        self._process_emissions_edges.append(edge)
        edge.attach_target_node(self.network.extract_node(
            self.target_node_location_2, self.target_node_type_2, period_number))
        edge.flow = period_emissions
        return

    def _build_fuel_emissions_edge_for_period(self, period_number):
        """Period-indexed fuel emissions to CO2 Budget"""
        start, end = self.period_boundaries[period_number], self.period_boundaries[period_number + 1]
        period_flows = self.flows[start:end]
        period_annualisation_factor = self._annualisation_factor()
        period_emissions = cp.sum(
            self.fuel_emissions_fun(period_flows, self.fuel_emissions_fun_params)
        ) * period_annualisation_factor

        edge = Edge_STEVFNs()
        self.edges.append(edge)
        self._fuel_emissions_edges.append(edge)
        edge.attach_target_node(self.network.extract_node(
            self.target_node_location_2, self.target_node_type_2, period_number))
        edge.flow = period_emissions
        return

    def _annualisation_factor(self):
        """Scale sample size to full-year equivalent"""
        hours_per_day = 24
        sampled_days = int((self.number_of_edges / hours_per_day) / self.num_years)
        return 365 / sampled_days

    def _period_for_year(self, year_number):
        """Identify which reinvestment period a specific year falls in"""
        return min(year_number // self.reinvestment_period, self.num_periods - 1)

    def _year_for_edge(self, edge_number):
        """Identify which year a given hour sample index falls in."""
        year_index = 0
        for i, idx in enumerate(self.year_boundaries[:-1]):
            if edge_number >= idx:
                year_index = i
            else:
                break
        return year_index

    def _update_usage_constant(self):
        sampled_days = int((self.number_of_edges / 24) / self.num_years)
        simulation_factor = 365 / sampled_days
        discount_rate = self.network.system_parameters_df.loc["discount_rate", "value"]

        raw_cost = float(self.parameters_df["usage_constant"])
        discount_factors = (1 / (1 + discount_rate)) ** np.arange(self.num_years)
        yearly_costs = raw_cost * discount_factors * simulation_factor

        year_indices = self._get_year_change_indices() + [self.number_of_edges]
        expanded_costs = np.zeros(self.number_of_edges)
        for i, (start, end) in enumerate(zip(year_indices[:-1], year_indices[1:])):
            expanded_costs[start:end] = yearly_costs[i]

        self.cost_fun_params["usage_constant"].value = expanded_costs
        return

    def _load_baseline_capex(self):
        baseline_capex = float(self.parameters_df["sizing_constant"])
        return np.full(self.num_periods, baseline_capex)

    def _update_parameters(self):
        self.process_emissions_fun_params["process_emissions_factor"].value = \
                    float(self.parameters_df["process_emissions_factor"])
        self.process_emissions_fun_params["clinker_to_cement_ratio"].value = \
                    float(self.parameters_df["clinker_to_cement_ratio"])
        self.fuel_emissions_fun_params["fuel_emissions_factor"].value = \
            float(self.parameters_df["fuel_emissions_factor"])
        self.electricity_fun_params["electricity_intensity"].value = \
            float(self.parameters_df["electricity_intensity"])
        self._update_usage_constant()

        sizing_constant_vec = self._load_baseline_capex()
        self._get_lifetime_periods()
        self._update_sizing_constant(sizing_constant_vec)
        self._update_new_capacity_decom_mask()
        self._update_existing_capacity_vec()
        return

    def get_hourly_flows(self):
        """Hourly cement production (Mt/h)"""
        return self.flows.value

    def get_hourly_electricity(self):
        """Hourly electricity draw (GWh/h) from the EL node."""
        return np.array([edge.flow.value for edge in self._electricity_edges])

    def get_period_flows(self):
        """Raw hourly cement production grouped by reinvestment period
        (not annualised) -- retained for plotting/debugging parity with
        PP_CO2_Asset.get_period_flows."""
        flows_full = self.get_hourly_flows()
        return [flows_full[start:end]
                for start, end in zip(self.period_boundaries[:-1], self.period_boundaries[1:])]

    def get_annual_production(self):
        """Annual cement production (Mt/year) per year, reconstructed from
        the hourly production edges: averages the sampled hourly rate within
        each year and scales by annualistation"""
        flows_full = np.array([edge.flow.value for edge in self._production_edges])
        year_boundaries = self._get_year_change_indices() + [self.number_of_edges]
        annualisation_factor = self._annualisation_factor()
        return np.array([
            np.mean(flows_full[start:end]) * annualisation_factor
            for start, end in zip(year_boundaries[:-1], year_boundaries[1:])
        ])

    def get_period_process_emissions(self):
        """Emissions from calcination in MtCO2e/year
        Results output per reinvestment period, average annualised emissions
        over the number of modelled years actually falling in each period."""
        period_totals = [-edge.flow.value for edge in self._process_emissions_edges]
        return np.array([total / self._years_in_period(p) for p, total in enumerate(period_totals)])

    def get_period_fuel_emissions(self):
        """MtCO2e/year from kiln fuel alone, per reinvestment period,
        same annualisation convention as get_period_process_emissions."""
        period_totals = [-edge.flow.value for edge in self._fuel_emissions_edges]
        return np.array([total / self._years_in_period(p) for p, total in enumerate(period_totals)])

    def get_period_emissions(self):
        """Total MtCO2e/year (process + fuel) per reinvestment period --
        feeds the standard 'emissions' metric in get_results_records."""
        return self.get_period_process_emissions() + self.get_period_fuel_emissions()

    def get_period_capacity(self):
        """Operating production capacity per reinvestment period
        (Mt cement/year)."""
        return self.get_operating_stock()

    def get_asset_sizes(self):
        asset_identity = self.asset_name + r"_location_" + str(self.target_node_location)
        return {asset_identity: self.size()}