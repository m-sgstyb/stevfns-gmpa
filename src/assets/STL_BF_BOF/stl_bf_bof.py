#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import numpy as np
import cvxpy as cp
from ..Base_Stock_Assets import Stock_Asset_STEVFNs
from ...network import Edge_STEVFNs

class STL_BF_BOF_Asset(Stock_Asset_STEVFNs):
    """
    Time-dependent Steel Production through BF-BOF route
    """
    asset_name = "STL_BF_BOF"
    source_node_type = "NULL"
    target_node_type = "STL"     # Steel demand node
    target_node_type_2 = "CO2_Budget"
    target_node_type_3 = "STL_BF_BOF_Production_Capacity"
    el_node_type = "EL"
    stock_node_type = "STL_BF_BOF_Production_Stock"
    decommission_mode = "decay_rate"
    capacity_unit = "Mt steel/yr"
    period = 1
    transport_time = 0

    @staticmethod
    def emissions_fun(flows, params):
        """Generalised emissions factor for process
        per unit of crude steel produced
        """
        emissions_factor = params["emissions_factor"]
        return -emissions_factor * flows

    @staticmethod
    def electricity_fun(flows, params):
        """
        Electricity draw per unit steel produced
        """
        electricity_intensity = params["electricity_intensity"]
        return electricity_intensity * flows

    @staticmethod
    def conversion_function(flows, params):
        """
        Actual output from nameplate 
        """
        capacity_factor = params["capacity_factor"]
        return capacity_factor * flows

    def __init__(self):
        self.emissions_fun_params = {
            "emissions_factor": cp.Parameter(nonneg=True,
                                            name=f"emissions_factor_{self.asset_name}")
        }
        self.electricity_fun_params = {
            "electricity_intensity": cp.Parameter(nonneg=True,
                                                  name=f"electricity_intensity_{self.asset_name}")
        }
        self.conversion_fun_params = {
            "capacity_factor": cp.Parameter(nonneg=True,
                                            name=f"capacity_factor_{self.asset_name}")
        }
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
        # Allowing variable production of steel at hourly resolution
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
        self._emissions_edges = []

        self._build_capacity_availability_edges()
        for edge_number in range(self.number_of_edges):
            self._build_electricity_edge(edge_number)
            self._build_production_edge(edge_number)  
        self._build_stock_edges()
        for period in range(self.num_periods):
            self._build_emissions_edge_for_period(period)
        return

    def _build_capacity_availability_edges(self):
        """
        Annual node holding available capacity that year. Limits total
        production form hourly edges that draw from it to meet demand
        """
        for y in range(self.num_years):
            p = self._period_for_year(y)
            edge = Edge_STEVFNs()
            self.edges.append(edge)
            self._capacity_edges.append(edge)
            edge.attach_target_node(self.network.extract_node(
                self.target_node_location_3, self.target_node_type_3, y))
            edge.flow = self.carryover_out[p]
        return

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
        """Hourly steel production edge from available capacity node
        into the hourly STL demand node"""
        year_number = self._year_for_edge(edge_number)
        annualisation_factor = self._annualisation_factor()
        edge = Edge_STEVFNs()
        self.edges.append(edge)
        self._production_edges.append(edge)
        edge.attach_source_node(self.network.extract_node(
            self.target_node_location_3, self.target_node_type_3, year_number)) # annual capacity available
        edge.attach_target_node(self.network.extract_node(
            self.target_node_location, self.target_node_type, self.target_node_times[edge_number])) # hourly production
        edge.flow = self.conversion_fun(self.flows[edge_number], self.conversion_fun_params) * annualisation_factor # scale by annualisation to approximate annual demand
        return

    def _build_stock_edges(self):
        """Overwrite stock chain to scale annual production capacity
        to sample size"""
        decommission_out = self.decom_mask_param @ self.new_capacity
        scaling_factor = 1 / self._annualisation_factor()
        for p in range(self.num_periods):
            stock_node = self.network.extract_node(self.stock_node_location,
                                                        self.stock_node_type, p)
            stock_node.curtailment = False
    
            install_edge = Edge_STEVFNs()
            self.edges.append(install_edge)
            install_edge.attach_target_node(stock_node)
            install_edge.flow = self.new_capacity[p]
    
            decom_edge = Edge_STEVFNs()
            self.edges.append(decom_edge)
            decom_edge.attach_source_node(stock_node)
            decom_edge.flow = decommission_out[p]
    
            if p == 0:
                # Seed the pre-model existing fleet once
                existing_edge = Edge_STEVFNs()
                self.edges.append(existing_edge)
                existing_edge.attach_target_node(stock_node)
                existing_edge.flow = self.existing_capacity_vec[0] * scaling_factor
            else:
                # existing_capacity_vec[p] is the decayed level of
                # the pre-model fleet at period p (e.g. existing_capacity *
                # (1 - decay_rate)**p). Its period-on-period decrement
                # leaves the node here, decaying total is carried over through
                # carryover_out balance
                existing_decom_edge = Edge_STEVFNs()
                self.edges.append(existing_decom_edge)
                existing_decom_edge.attach_source_node(stock_node)
                existing_decom_edge.flow = scaling_factor *\
                    (self.existing_capacity_vec[p - 1] - self.existing_capacity_vec[p])
    
                prev_stock_node = self.network.extract_node(self.stock_node_location,
                                                                self.stock_node_type, p - 1)
                carry_in_edge = Edge_STEVFNs()
                self.edges.append(carry_in_edge)
                carry_in_edge.attach_source_node(prev_stock_node)
                carry_in_edge.attach_target_node(stock_node)
                carry_in_edge.flow = self.carryover_out[p - 1]
    
            if p == self.num_periods - 1:
                carry_out_edge = Edge_STEVFNs()
                self.edges.append(carry_out_edge)
                carry_out_edge.attach_source_node(stock_node)
                carry_out_edge.flow = self.carryover_out[p]
        return

    def _build_emissions_edge_for_period(self, period_number):
        """Period-indexed process emissions to CO2 Budget"""
        start, end = self.period_boundaries[period_number], self.period_boundaries[period_number + 1]
        period_flows = self.flows[start:end]
        period_annualisation_factor = self._annualisation_factor()
        period_emissions = cp.sum(
            self.emissions_fun(period_flows, self.emissions_fun_params)
        ) * period_annualisation_factor

        edge = Edge_STEVFNs()
        self.edges.append(edge)
        self._emissions_edges.append(edge)
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

    def _update_sizing_constant(self, sizing_constant_vec):
        """
        Update sizing constant and re-scale back to sample size
        Industry capacity in rate of Mt/year 
        """
        lifetime_periods = self._get_lifetime_periods()
        asset_lifetime = self._asset_lifetime
        interest_rate = float(self.parameters_df["interest_rate"])
        discount_rate = float(self.network.system_parameters_df.loc["discount_rate", "value"])
        scaling_factor = self._annualisation_factor()
        amort_factor = (interest_rate * (1 + interest_rate) ** asset_lifetime) / \
                        ((1 + interest_rate) ** asset_lifetime - 1)
        annual_payment_vec = sizing_constant_vec * amort_factor * scaling_factor

        period_start_years = self.period_start_years
        period_years = np.array([self._years_in_period(p) for p in range(self.num_periods)])
        period_end_years = period_start_years + period_years

        M = np.zeros((self.num_periods, self.num_periods))
        # Charge component indexed by install cohort k, for capacity
        # installed where lifetime exceeds project life
        terminal_charge_vec = np.zeros(self.num_periods)

        for k in range(self.num_periods):
            install_year = period_start_years[k]
            payoff_year = install_year + asset_lifetime
            for p in range(self.num_periods):
                y_start = max(period_start_years[p], install_year)
                y_end = min(period_end_years[p], payoff_year)
                if y_end <= y_start:
                    continue
                years_in_window = np.arange(int(round(y_start)), int(round(y_end)))
                if years_in_window.size == 0:
                    continue
                discount_factors = (1 + discount_rate) ** (-years_in_window.astype(float))
                M[p, k] = annual_payment_vec[k] * discount_factors.sum()

            # NPV of repayment years that fall beyond the model horizon.
            horizon_year = self.num_years
            if payoff_year > horizon_year:
                remaining_years = np.arange(int(round(horizon_year)), int(round(payoff_year)))
                if remaining_years.size > 0:
                    remaining_discount_factors = (1 + discount_rate) ** (-remaining_years.astype(float))
                    terminal_charge_vec[k] = annual_payment_vec[k] * remaining_discount_factors.sum()

        self.cost_fun_params["sizing_constant"].value = M
        self.cost_fun_params["terminal_charge"].value = terminal_charge_vec
        return

    def _load_baseline_capex(self):
        baseline_capex = float(self.parameters_df["sizing_constant"])
        return np.full(self.num_periods, baseline_capex)

    def _update_parameters(self):
        self.emissions_fun_params["emissions_factor"].value = \
                    float(self.parameters_df["emissions_factor"])
        self.electricity_fun_params["electricity_intensity"].value = \
            float(self.parameters_df["electricity_intensity"])
        self.conversion_fun_params["capacity_factor"].value = \
            float(self.parameters_df["capacity_factor"])
        self._update_usage_constant()

        sizing_constant_vec = self._load_baseline_capex()
        self._get_lifetime_periods()
        self._update_sizing_constant(sizing_constant_vec)
        self._update_new_capacity_decom_mask()
        self._update_existing_capacity_vec()
        return

    def get_hourly_flows(self):
        """Hourly steel production (Mt/h)"""
        return self.flows.value

    def get_hourly_electricity(self):
        """Hourly electricity draw (GWh/h) from the EL node."""
        return np.array([edge.flow.value for edge in self._electricity_edges])

    def get_period_flows(self):
        """Raw hourly steel production grouped by reinvestment period
        (not annualised) -- retained for plotting/debugging parity with
        PP_CO2_Asset.get_period_flows."""
        flows_full = self.get_hourly_flows()
        return [flows_full[start:end]
                for start, end in zip(self.period_boundaries[:-1], self.period_boundaries[1:])]

    def get_annual_production(self):
        """Annual steel production (Mt/year) per year, reconstructed from
        the hourly production edges: averages the sampled hourly rate within
        each year and scales by annualistation"""
        flows_full = np.array([edge.flow.value for edge in self._production_edges])
        year_boundaries = self._get_year_change_indices() + [self.number_of_edges]
        annualisation_factor = self._annualisation_factor()
        return np.array([
            np.mean(flows_full[start:end]) * annualisation_factor
            for start, end in zip(year_boundaries[:-1], year_boundaries[1:])
        ])

    def get_period_emissions(self):
        """Total MtCO2e/year per reinvestment period -- this
        feeds the standard 'emissions' metric in get_results_records."""
        period_totals = [-edge.flow.value for edge in self._emissions_edges]
        return np.array([total / self._years_in_period(p) for p, total in enumerate(period_totals)])

    def get_operating_stock(self):
        """Operating production capacity per reinvestment period
        (Mt steel/year)."""
        optimised_capacity = np.array(self.carryover_out.value)
        return optimised_capacity * self._annualisation_factor()

    def get_new_capacity(self):
        """New installed capacity per reinvestment period scaled"""
        optimised_new_capacity = np.array(self.new_capacity.value)
        return optimised_new_capacity * self._annualisation_factor()

    def get_asset_sizes(self):
        asset_identity = self.asset_name + r"_location_" + str(self.target_node_location)
        return {asset_identity: self.size()}