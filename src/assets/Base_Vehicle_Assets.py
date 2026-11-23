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
    capacity_unit = None # Set in sub classes as mtkm/year or mpkm/yr
    demand_unit = None # Set in sub classes as mtkm/year or mpkm/yr
    decommission_mode = "decay_rate"
    period = 1
    transport_time = 0

    @staticmethod
    def conversion_fun(flows, params):
        """Convert Mveh-km flows to mpsgr-km or mton-km"""
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
        # Fallback for naming stock and capacity node types in child classes
        if self.stock_node_type == "NULL":
            self.stock_node_type = f"{self.asset_name}_Stock"
        if self.capacity_node_type == "NULL":
            self.capacity_node_type = f"{self.asset_name}_Capacity"
        self._define_period_structure(asset_structure)

        self.period_change_indices = self._get_period_change_indices()
        self.period_boundaries = self.period_change_indices + [self.number_of_edges]
        # self.flows[t] [=] M veh-km driven in sampled hour t for t in number of edges
        self.flows = cp.Variable(self.number_of_edges, nonneg=True,
                                 name=f"flows_{self.asset_name}")
        annualisation = self._annualisation_factor()
        A = np.zeros((self.num_years, self.number_of_edges))
        for y, (start, end) in enumerate(zip(self.year_boundaries[:-1], self.year_boundaries[1:])):
            A[y, start:end] = annualisation
        # annual_veh_km [=] M veh-km/yr (sampled hours scaled to 365 days)
        self.annual_veh_km = A @ self.flows
        self.year_to_period = [min(y // self.reinvestment_period, self.num_periods -1)
                               for y in range(self.num_years)]
        return

    def build_edges(self):
        self.edges = []
        self._annual_edges = []

        self._build_capacity_limit_edges()
        self._build_stock_edges()
        return

    def _build_demand_edges(self):
        """One edge per year into FRT or PGR nodes. Annualised veh-km * load_factor
        -> Mton-km or Mpkm per year, same units as demand asset
        """
        for y in range(self.num_years):
            edge = Edge_STEVFNs()
            self.edges.append(edge)
            self._annual_edges.append(edge)
            edge.attach_target_node(self.network.extract_node(
                self.target_node_location, self.target_node_type, y))
            edge.flow = self.annual_veh_km[y]
            edge.conversion_fun = self.conversion_fun
            edge.conversion_fun_params = self.conversion_fun_params
        return

    def _build_capacity_limit_edges(self):
        """Peak annual veh-km in any year of period p <= operating stock in p.
        carryover_out is stock in M veh-km/year, reused every year"""
        for p in range(self.num_periods):
            years_p = [y for y in range(self.num_years) if self.year_to_period[y] == p]
            peak = cp.max(self.annual_veh_km[years_p[0]:years_p[-1] + 1])
            edge = Edge_STEVFNs()
            self.edges.append(edge)
            edge.attach_target_node(self.network.extract_node(
                self.target_node_location, self.capacity_node_type, p))
            edge.flow = self.carryover_out[p] - peak
        return

    # Helpers to get numpy values to convert required units 
    # parameters and keep DPP compliance
    def _load_factor(self):
        return float(self.parameters_df["load_factor"])

    def _demand_units_to_veh_km(self, value_in_demand_units):
        """Convert quantity in mtkm (or mpkm) to Mveh-km
        Divide by load factor
        """
        load_factor = self._load_factor()
        if load_factor <= 0:
            raise ValueError(f"{self.asset_name}: load factor must be > 0 to convert units")
        return value_in_demand_units / load_factor

    def _existing_capacity_value(self):
        """Overrides Base_Stock_Assets as parameters for VEH assets give existing capacity
        in demand units per year (mtkm or mpkm). Stock (carryover_out) is Mveh-km/yr
        """
        return self._demand_units_to_veh_km(float(self.parameters_df["existing_capacity"]))

    def _load_sizing_constant(self):
        """Scalar TCO-equivalent CAPEX value in $ per M veh-km
        broadcast across reinvestment periods before amortising"""
        baseline = float(self.parameters_df["sizing_constant"])
        return np.full(self.num_periods, baseline)

    def _update_parameters(self):
        self.conversion_fun_params["load_factor"].value = self._load_factor()
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

    def get_annual_flows(self):
        return np.array([edge.flow.value for edge in self._annual_edges])

    def get_period_flows(self):
        flows_full = self.get_hourly_flows()
        return [flows_full[start:end]
                for start, end in zip(self.period_boundaries[:-1], self.period_boundaries[1:])]

    def get_period_capacity(self):
        """operating fleet size per period for plotting"""
        return self.get_operating_stock()

    def get_operating_stock_demand_units(self):
        """Operating fleet size in relevant demand asset's units to be
        directly comparable with demand
        """
        stock = self.get_operating_stock()
        return None if stock is None else stock * self._load_factor()

    def get_hourly_flows(self):
        """Hourly veh-km (M veh-km per sampled hour)."""
        return None if self.flows.value is None else np.array(self.flows.value)

    def get_period_throughput(self):
        """Annual-average M veh-km/yr per period. Compare with
        get_period_capacity() for fleet utilisation."""
        flows = self.get_hourly_flows()
        if flows is None:
            return None
        f = self._annualisation_factor()
        return np.array([
            flows[s:e].sum() * f / self._years_in_period(p)
            for p, (s, e) in enumerate(zip(self.period_boundaries[:-1],
                                        self.period_boundaries[1:]))])

    def asset_size(self):
        self.carryover_out.value
        return np.array(self.carryover_out.value)

    def get_asset_sizes(self):
        asset_identity = self.asset_name + r"_location_" + str(self.source_node_location)
        return {asset_identity: self.asset_size()}