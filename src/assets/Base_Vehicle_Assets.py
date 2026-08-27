#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import numpy as np
import cvxpy as cp
from .Base_Stock_Assets import Stock_Asset_STEVFNs
from .Base_Assets import Asset_STEVFNs
from ..network import Edge_STEVFNs

class Base_Vehicle_Asset_STEVFNs(Stock_Asset_STEVFNs):
    """Shared base class for vehicle fleet assets"""

    asset_name = "Base_Vehicle_Asset_STEVFNs"
    source_node_type = "NULL"
    target_node_type = "NULL"   # set in subclass (e.g. PSGR, FRT), transport demand node type
    stock_node_type = "NULL"    # set in ICE/EV PSGR or FRT classes
    capacity_node_type = "NULL" # set in ICE/EV PSGR or FRT classes
    capacity_unit = "M veh-km"
    decommission_mode = "decay_rate"
    period = 1
    transport_time = 0

    @staticmethod
    def conversion_fun(flows, params):
        """Convert veh-km flows to mpsgr-km or mton-km"""
        load_factor = params["load_factor"] # mpsgr/mveh or mton/mveh
        return load_factor * flows

    def __init__(self):
        super().__init__()
        self.conversion_fun_params = {
            "load_factor": cp.Parameter(nonneg=True,
                                        name=f"load_factor_{self.asset_name}")
        }
        return

    def define_structure(self, asset_structure):
        self.asset_structure = asset_structure
        self.source_node_location = asset_structure["Location_1"]
        self.target_node_location = self.source_node_location
        self.stock_node_location = self.source_node_location
        self.capacity_node_location = self.source_node_location
        self.target_node_location = self.source_node_location
        self.source_node_times = np.arange(asset_structure["Start_Time"],
                                           asset_structure["End_Time"],
                                           self.period) # hourly timesteps
        self.num_years = int(self.network.system_parameters_df.loc["project_life", "value"] / 8760)
        self.number_of_edges = len(self.source_node_times)
        self.year_change_indices = self._get_year_change_indices()
        self.year_boundaries = self.year_change_indices + [self.number_of_edges]
        self._define_period_structure(asset_structure)

        self.period_change_indices = self._get_period_change_indices()
        self.period_boundaries = self.period_change_indices + [self.number_of_edges]

        self.flows = cp.Variable(self.number_of_edges, nonneg=True,
                                 name=f"flows_{self.asset_name}") # variable in veh-km
        return

    def build_edges(self):
        self.edges = []
        for edge_number in range(self.number_of_edges):
            self._build_demand_edges(edge_number)
        self._build_capacity_limit_edges()
        self._build_stock_edges()
        return

    def _build_demand_edges(self, edge_number):
        """Driving edges deliver hourly mpsgr-km or mton-km into per year 
        demand nodes.
        self.flows remains a mveh-km variable 
        """
        self._hourly_edges = []
        year_number = self._year_for_edge(edge_number)
        new_edge = Edge_STEVFNs()
        self.edges.append(new_edge)
        self._hourly_edges.append(new_edge)
        new_edge.attach_target_node(self.network.extract_node(
            self.target_node_location, self.target_node_type, year_number))
        new_edge.flow = self.flows[edge_number]
        new_edge.conversion_fun = self.conversion_fun
        new_edge.conversion_fun_params = self.conversion_fun_params
        return

    def _build_capacity_limit_edges(self):
        """Caps the cummulative annual throughput (the sum of mveh-km over the year)
        at fleet's operating stock at that year. Transport fleet constraint binds total
        annual mileage"""
        annualisation_factor = self._annualisation_factor()
        for p in range(self.num_periods):
            start, end = self.period_boundaries[p], self.period_boundaries[p + 1]
            period_flows = self.flows[start:end]
            years = self._years_in_period(p)
            edge = Edge_STEVFNs()
            self.edges.append(edge)
            edge.attach_target_node(self.network.extract_node(
                self.capacity_node_location, self.capacity_node_type, p
            ))
            edge.flow = self.carryover_out[p] * years - (cp.sum(period_flows) * annualisation_factor)
        return

    def _load_sizing_constant(self):
        """Scalar TCO-equivalent CAPEX value in $ per M veh-km
        broadcast across reinvestment periods before amortising"""
        baseline = float(self.parameters_df["sizing_constant"])
        return np.full(self.num_periods, baseline)

    def _update_parameters(self):
        self.conversion_fun_params["load_factor"].value = float(self.parameters_df["load_factor"])
        sizing_constant = self._load_sizing_constant()
        self._update_sizing_constant(sizing_constant)
        self._update_new_capacity_decom_mask()
        self._update_existing_capacity_vec()
        return

    def _year_for_edge(self, edge_number):
        """Identify which year a given hour sample index falls in.
        """
        year_index = 0
        for i, idx in enumerate(self.year_boundaries[:-1]):
            if edge_number >= idx:
                year_index = i
            else:
                break
        return year_index

    def _annualisation_factor(self):
        """Scale sample size to full-year equivalent"""
        hours_per_day = 24
        sampled_days = int((self.number_of_edges / hours_per_day) / self.num_years)
        return 365 / sampled_days

    def get_hourly_flows(self):
        return np.array([edge.flow.value for edge in self._hourly_edges])

    def get_period_flows(self):
        flows_full = self.get_hourly_flows()
        return [flows_full[start:end]
                for start, end in zip(self.period_boundaries[:-1], self.period_boundaries[1:])]

    def get_period_capacity(self):
        """operating fleet size per period for plotting"""
        return self.get_operating_stock()