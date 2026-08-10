#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import numpy as np
import cvxpy as cp
import pandas as pd
from ..Base_Stock_Assets import Stock_Asset_STEVFNs
from ...network import Edge_STEVFNs

class RE_WIND_Onshore_Lim_7_Asset(Stock_Asset_STEVFNs):
    asset_name = "RE_WIND_Onshore_Lim_7"
    target_node_type = "EL"
    stock_node_type = "WIND_On_Lim_7_Stock"
    tech_node_type = "WIND_On_Lim_7_Tech_Potential"
    decommission_mode = "decay_rate" # scalar step wise period decommission for existing capacity
    period = 1
    transport_time = 0

    def define_structure(self, asset_structure):
        self.asset_structure = asset_structure
        self.source_node_location = "NULL"
        self.target_node_location = asset_structure["Location_1"]
        self.stock_node_location = asset_structure["Location_1"]
        self.tech_node_location = asset_structure["Location_1"]

        self.target_node_times = np.arange(asset_structure["Start_Time"],
                                            asset_structure["End_Time"], self.period)
        self.number_of_edges = len(self.target_node_times)

        self._define_period_structure(asset_structure)
        # self.flows stays cp.Constant(0), usage_constant_1 stays cp.Constant(0) --
        # RE assets have no hourly dispatch decision variable and no usage cost.

        self.tech_potential_param = cp.Parameter(nonneg=True,
                                                   name=f"tech_potential_{self.asset_name}")
        self.gen_profile = cp.Parameter(shape=(self.number_of_edges,), nonneg=True,
                                         name=f"gen_profile_{self.asset_name}")
        self.period_change_indices = self._get_period_change_indices()
        return

    def build_edges(self):
        self.edges = []
        self._build_generation_edges()
        self._build_stock_edges()
        self._build_tech_potential_edges()
        return

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
            new_edge.flow = self.carryover_out[period_index] * self.gen_profile[edge_number]
        return

    def _build_tech_potential_edges(self):
        for p in range(self.num_periods):
            edge = Edge_STEVFNs()
            self.edges.append(edge)
            edge.attach_target_node(self.network.extract_node(
                self.tech_node_location, self.tech_node_type, p))
            edge.flow = self.tech_potential_param - self.carryover_out[p]
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

    def _update_parameters(self):
        sizing_constant = self._load_cost_profile() # load profile with learning curve
        self._update_sizing_constant(sizing_constant)
        self._update_new_capacity_decom_mask()
        self._update_existing_capacity_vec()
        self.tech_potential_param.value = float(self.parameters_df["maximum_size"])
        self._load_RE_profile()
        return

    def get_hourly_flows(self):
        return np.array([edge.flow.value for edge in self._hourly_edges])

    def get_period_flows(self):
        flows_full = self.get_hourly_flows()
        indices = list(self.period_change_indices) + [len(flows_full)]
        return [flows_full[start:end] for start, end in zip(indices[:-1], indices[1:])]

    def get_asset_sizes(self):
        asset_identity = self.asset_name + r"_" + self.parameters_df["RE_type"] + r"_location_" + str(self.target_node_location)
        return {asset_identity: self.size()}
