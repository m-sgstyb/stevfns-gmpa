#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Nov  1 16:36:27 2021

@author: aniqahsan
Adapted for time-dependence, 2026
@contributor: Mónica Sagastuy Breña
"""

import os
import numpy as np
import cvxpy as cp
import pandas as pd
from ..Base_Assets import Asset_STEVFNs
from ...network import Edge_STEVFNs


class RE_WIND_Offshore_Lim_2_Asset(Asset_STEVFNs):
    """
    Offshore Wind asset with time-dependence, 
    stock-node-based operating capacity tracking.
    """

    asset_name = "RE_WIND_Offshore_Lim_2"
    target_node_type = "EL"

    # Node types used for the stock chain and the technical-potential cap
    stock_node_type = "WIND_Off_2_Stock"
    tech_node_type = "WIND_Off_2_Tech_Potential"

    period = 1
    transport_time = 0

    def __init__(self):
        super().__init__()
        self.cost_fun_params = dict()
        self.conversion_fun_params = dict()
        return

    def define_structure(self, asset_structure):
        self.asset_structure = asset_structure
        self.source_node_location = "NULL"
        self.target_node_location = asset_structure["Location_1"] # EL edges
        self.stock_node_location = asset_structure["Location_1"]
        self.tech_node_location = asset_structure["Location_1"]

        self.target_node_times = np.arange(asset_structure["Start_Time"],
                                            asset_structure["End_Time"],
                                            self.period) # EL edges
        self.number_of_edges = len(self.target_node_times) # sampled timesteps

        # --- Horizon / reinvestment-period ---
        self.num_years = int(self.network.system_parameters_df.loc["project_life", "value"] / 8760)
        self.reinvestment_period = int(self.network.system_parameters_df.loc["reinvestment_period", "value"] / 8760)
        self.num_periods = int(np.ceil(self.num_years / self.reinvestment_period))
        self.period_start_years = np.arange(self.num_periods) * self.reinvestment_period

        # --- Decision variable: new capacity installed at each reinvestment-period ---
        self.flows = cp.Variable(shape=(self.num_periods,), nonneg=True,
                                  name=f"new_capacity_{self.asset_name}")

        # --- Stock bookkeeping variable ---
        # carryover_out[p] = capacity still active at the end of period p,
        # net of that period's existing capacity, new isntalls and decommissioning.
        self.carryover_out = cp.Variable(shape=(self.num_periods,), nonneg=True,
                                          name=f"carryover_{self.asset_name}")

        # --- Cost: one multiplier per period, folding sizing cost,
        # amortisation, annuity value and discounting into a single
        # coefficient
        self.cost_multiplier_param = cp.Parameter(shape=(self.num_periods,), nonneg=True,
                                                   name=f"cost_multiplier_{self.asset_name}")

        # --- Decommission mask: decom_mask[p, k] = 1 if a cohort
        # installed at period k retires exactly at period p. Values are
        # set in _update_parameters once asset_lifetime param is known; the
        # edge topology using this parameter is fixed.
        self.decom_mask_param = cp.Parameter(shape=(self.num_periods, self.num_periods), nonneg=True,
                                              name=f"decom_mask_{self.asset_name}")

        # --- Existing capacity: single scalar + assumed decay curve,
        # pre-computed into a per-period vector in _update_parameters
        self.existing_capacity_vec = cp.Parameter(shape=(self.num_periods,), nonneg=True,
                                                    name=f"existing_capacity_vec_{self.asset_name}")

        # --- Technical potential: single scalar cap on stock ---
        self.tech_potential_param = cp.Parameter(nonneg=True,
                                                   name=f"tech_potential_{self.asset_name}")

        # --- Capacity factor profile (hourly) ---
        self.gen_profile = cp.Parameter(shape=(self.number_of_edges,), nonneg=True,
                                         name=f"gen_profile_{self.asset_name}")

        # --- Identify changes in investment period from sampled data ---
        self.period_change_indices = self._get_period_change_indices()
        return

    def build_edges(self):
        self.edges = []
        self._build_generation_edges()
        self._build_stock_edges()
        self._build_tech_potential_edges()
        return

    def _build_generation_edges(self):
        # Hourly edges operating_capacity * capacity factor
        for edge_number in range(self.number_of_edges):
            target_node_time = self.target_node_times[edge_number]
            period_index = self._period_index_for_edge(edge_number)

            new_edge = Edge_STEVFNs()
            self.edges.append(new_edge)
            new_edge.attach_target_node(self.network.extract_node(
                self.target_node_location, self.target_node_type, target_node_time))
            new_edge.flow = self.carryover_out[period_index] * self.gen_profile[edge_number]
        return

    def _period_index_for_edge(self, edge_number):
        period_index = 0
        for i, idx in enumerate(self.period_change_indices):
            if edge_number >= idx:
                period_index = i
            else:
                break
        return period_index

    def _build_stock_edges(self):
        """
        Builds the stock-node chain. For each period p:
          inputs  = new install (flows[p]) + existing-capacity decay term
                    + carry-in from period p-1
          outputs = decommission (decom_mask @ flows, indexed at p)
                    + carry-out to period p+1

        curtailment=False forces inputs == outputs via node equality constraint
        This pins down carryover_out[p] (operating capacity during period p).
        """
        decommission_out = self.decom_mask_param @ self.flows  # shape (num_periods,)

        for p in range(self.num_periods):
            stock_node = self.network.extract_node(self.stock_node_location,
                                                   self.stock_node_type, p)
            stock_node.curtailment = False  # equality constraint

            # New install p -> stock node p
            install_edge = Edge_STEVFNs()
            self.edges.append(install_edge)
            install_edge.attach_target_node(stock_node)
            install_edge.flow = self.flows[p]

            # Decommission stock node p -> null (leaves system)
            # Uses decom_mask_param @ flows
            decom_edge = Edge_STEVFNs()
            self.edges.append(decom_edge)
            decom_edge.attach_source_node(stock_node)
            decom_edge.flow = decommission_out[p]

            # Existing-capacity decay vector[p] -> stock node p
            existing_edge = Edge_STEVFNs()
            self.edges.append(existing_edge)
            existing_edge.attach_target_node(stock_node)
            existing_edge.flow = self.existing_capacity_vec[p]

            # Carry-in from the previous period's stock node
            # stock[p-1] -> stock[p]
            if p > 0:
                prev_stock_node = self.network.extract_node(self.stock_node_location,
                                                            self.stock_node_type, p - 1)
                carry_in_edge = Edge_STEVFNs()
                self.edges.append(carry_in_edge)
                carry_in_edge.attach_source_node(prev_stock_node)
                carry_in_edge.attach_target_node(stock_node)
                carry_in_edge.flow = self.carryover_out[p - 1] # cp.Variable
            # Last period carry_out
            if p == self.num_periods - 1:
                carry_out_edge = Edge_STEVFNs()
                self.edges.append(carry_out_edge)
                carry_out_edge.attach_source_node(stock_node)
                carry_out_edge.flow = self.carryover_out[p]
                
        return

    def _build_tech_potential_edges(self):
        """Caps operating capacity (carryover_out) at a single
        maximum technical-potential scalar parameter."""
        for p in range(self.num_periods):
            edge = Edge_STEVFNs()
            self.edges.append(edge)
            edge.attach_target_node(self.network.extract_node(
                self.tech_node_location, self.tech_node_type, p))
            edge.flow = self.tech_potential_param - self.carryover_out[p]
        return

    def build_cost(self):
        self.cost = cp.sum(cp.multiply(self.flows, self.cost_multiplier_param))
        return

    def _update_parameters(self):
        # --- sizing / learning-curve cost input (per-period vector) ---
        sizing_constant = self._load_cost_profile()

        asset_lifetime = float(self.parameters_df["lifespan"] / 8760)
        interest_rate = float(self.parameters_df["interest_rate"])
        discount_rate = float(self.network.system_parameters_df.loc["discount_rate", "value"])

        # Capital recovery factor (amortisation), technology-specific rate
        amort_factor = (interest_rate * (1 + interest_rate) ** asset_lifetime) / \
                        ((1 + interest_rate) ** asset_lifetime - 1)
        # Present value of $1/year for asset_lifetime years, system discount rate
        annuity_factor = (1 - (1 + discount_rate) ** (-asset_lifetime)) / discount_rate
        # Discount that annuity stream back to year 0 from each period's start year
        period_discount = (1 + discount_rate) ** (-self.period_start_years.astype(float))

        self.cost_multiplier_param.value = sizing_constant * amort_factor * annuity_factor * period_discount

        # --- Decommission mask, in whole reinvestment periods ---
        lifetime_periods = int(round(asset_lifetime / self.reinvestment_period))
        lifetime_periods = max(lifetime_periods, 1)  # ASSUMPTION: never decommission same period as install
        decom_mask = np.zeros((self.num_periods, self.num_periods))
        for p in range(self.num_periods):
            k = p - lifetime_periods
            if 0 <= k < self.num_periods:
                decom_mask[p, k] = 1
        self.decom_mask_param.value = decom_mask

        # --- Existing capacity: most recent known value, decayed forward ---
        existing_capacity = float(self.parameters_df["existing_capacity"])
        existing_decay_rate = float(self.parameters_df["existing_capacity_decay_rate"])
        self.existing_capacity_vec.value = existing_capacity * \
            (1 - existing_decay_rate) ** self.period_start_years.astype(float)

        # --- Technical potential cap ---
        self.tech_potential_param.value = float(self.parameters_df["maximum_size"])

        self._load_RE_profile()
        return

    def update(self, asset_type):
        self._load_parameters_df(asset_type)
        self._update_parameters()
        return

    def _load_RE_profile(self):
        """Loads renewable profile and resamples to
        representative days per year."""
        lat_lon_df = self.network.lat_lon_df.iloc[self.target_node_location]
        lat = lat_lon_df["lat"]
        lat = np.int64(np.round(lat / 0.5)) * 0.5
        lat = min(lat, 90.0)
        lat = max(lat, -90.0)
        LAT = "{:0.1f}".format(lat)

        lon = lat_lon_df["lon"]
        lon = np.int64(np.round(lon / 0.625)) * 0.625
        lon = min(lon, 179.375)
        lon = max(lon, -180.0)
        LON = str(lon)

        RE_TYPE = self.parameters_df["RE_type"]
        profile_folder = os.path.join(self.parameters_folder, "profiles", RE_TYPE, r"lat" + LAT)
        profile_filename = os.path.join(profile_folder, RE_TYPE + r"_lat" + LAT + r"_lon" + LON + r".csv")

        with open(profile_filename, encoding='utf-8-sig') as f:
            full_profile = np.loadtxt(f)

        total_hours = len(full_profile)
        hours_per_year = 8760
        n_years = total_hours // hours_per_year
        hours_per_day = 24
        days_per_year = int((self.number_of_edges / hours_per_day) / n_years)

        new_profile = []
        for year in range(n_years):
            year_start = year * hours_per_year
            for d in range(days_per_year):
                day_idx = int((d + 0.5) * hours_per_year / days_per_year / hours_per_day)
                hour_idx = year_start + day_idx * hours_per_day
                new_profile.extend(full_profile[hour_idx:hour_idx + hours_per_day])

        self.gen_profile.value = np.array(new_profile)
        return

    def _load_cost_profile(self):
        """Reads a given profile of RE total installed capital costs
        Projected into the future by reinvestment period
        parameters.csv colum for sizing constant must have string for
        filename
        """
        costs_filename = self.parameters_df.get("sizing_constant") + ".csv"
        costs_path = os.path.join(self.parameters_folder, "profiles", costs_filename)
        costs_df = pd.read_csv(costs_path)
        location = self.parameters_df["location_name"]

        rows = costs_df[
            (costs_df["case_study"] == location)
        ]
        values = rows["sizing_constant"].to_numpy(dtype=float)
 
        if values.size != self.num_periods:
            raise ValueError(
                f"Sizing constant for location='{location}' in "
                f"{costs_filename} has {values.size} matching rows, "
                f"expected {self.num_periods} (one per reinvestment period)."
            )
        return values

    def _get_period_change_indices(self):
        """Hourly index at which each reinvestment period starts.
        Maps a generation edge's hour to the correct stock period."""
        hours_per_day = 24
        days_per_year = int((self.number_of_edges / hours_per_day) / self.num_years)
        hours_per_year = days_per_year * hours_per_day
        hours_per_period = hours_per_year * self.reinvestment_period
        self.period_change_indices = [i * hours_per_period for i in range(self.num_periods)]
        return self.period_change_indices

    def get_plot_data(self):
        """Hourly generation flow values (same convention as previous versions)."""
        total_flows = []
        for edge in self.edges[:self.number_of_edges]:
            total_flows.append(edge.flow.value)
        return total_flows

    def get_period_flows(self):
        """Hourly flows split by reinvestment period."""
        flows_full = np.array(self.get_plot_data())
        indices = list(self.period_change_indices) + [len(flows_full)]
        return [flows_full[start:end] for start, end in zip(indices[:-1], indices[1:])]

    def size(self):
        # New capacity installed per period
        return self.flows.value

    def asset_size(self):
        return self.flows.value

    def get_asset_sizes(self):
        asset_size = self.size()
        asset_identity = self.asset_name + r"_" + self.parameters_df["RE_type"] + r"_location_" + str(self.target_node_location)
        return {asset_identity: asset_size}