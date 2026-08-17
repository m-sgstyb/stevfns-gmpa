#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import numpy as np
import cvxpy as cp
import pandas as pd
from ..Base_Assets import Asset_STEVFNs
from ...network import Edge_STEVFNs


class CEM_Demand_Asset(Asset_STEVFNs):
    """
    Annual cement demand for the temporal pathways model: 
    Creates an assumed constant hourly, year-length profile
    of cement demand based on annual demand

    If a single value for annual demand is provided under that asset
    parameters "demand" column, demand is assumed constant through
    entire project lifetime.
    """
    asset_name = "CEM_Demand"
    node_type = "CEM"    
    period = 1

    def __init__(self):
        super().__init__()
        self.conversion_fun_params = dict()
        return

    def define_structure(self, asset_structure):
        self.asset_structure = asset_structure
        self.node_location = asset_structure["Location_1"]

        self.target_node_times = np.arange(asset_structure["Start_Time"],
                                            asset_structure["End_Time"], self.period)
        self.number_of_edges = len(self.target_node_times)

        self.num_years = int(self.network.system_parameters_df.loc["project_life", "value"] / 8760)
        self.year_change_indices = self._get_year_change_indices()
        self.year_boundaries = self.year_change_indices + [self.number_of_edges]

        self.flows = cp.Constant(np.zeros(self.number_of_edges))

        self.demand_param = cp.Parameter(shape=(self.number_of_edges,), nonneg=True,
                                        name=f"demand_{self.asset_name}")
        return

    def build_edge(self, edge_number):
        """Demand draws (output edge) from the CEM node at each hour"""
        edge = Edge_STEVFNs()
        self.edges.append(edge)
        edge.attach_source_node(self.network.extract_node(
            self.node_location, self.node_type, self.target_node_times[edge_number]))
        edge.flow = self.demand_param[edge_number]
        return

    def build_edges(self):
        self.edges = []
        for edge_number in range(self.number_of_edges):
            self.build_edge(edge_number)
        return

    def _load_demand_trajectory(self):
        """
        If parameters_df['demand'] holds a string, treats it as a
        profile filename and load the per-year trajectory from CSV.
        If it holds a numeric value instead, treat that as a constant
        annual demand (Mt cement/year) and broadcast it across all years.
        """
        trajectory_value = self.parameters_df.get("demand")

        if isinstance(trajectory_value, str):
            trajectory_filename = trajectory_value + ".csv"
            trajectory_path = os.path.join(self.parameters_folder, "profiles", trajectory_filename)
            trajectory_df = pd.read_csv(trajectory_path)

            location = self.parameters_df["location_name"]
            demand_rows = trajectory_df[
                (trajectory_df["location_name"] == location)
            ]
            values = demand_rows["demand"].to_numpy(dtype=float)

            if values.size != self.num_years:
                raise ValueError(
                    f"location_name='{location}' in "
                    f"{trajectory_filename} has {values.size} matching rows, "
                    f"expected {self.num_years} (one per year of project_life)."
                )
            return values

        # If single demand value (float) is provided, treat as a 
        # constant scalar demand, same value every year
        constant_demand = float(trajectory_value)
        return np.full(self.num_years, constant_demand)

    def _expand_annual_to_hourly(self, annual_demand):
        """Assumes constant hourly demand through the year: each hour in year y
        gets annual_demand[y] / 8760 (Mt/hour), the same value regardless of
        which representative hour is being sampled."""
        hourly_demand = np.zeros(self.number_of_edges)
        for y, (start, end) in enumerate(zip(self.year_boundaries[:-1], self.year_boundaries[1:])):
            hourly_demand[start:end] = annual_demand[y] / 8760
        return hourly_demand

    def _update_parameters(self):
        annual_demand = self._load_demand_trajectory()
        self.demand_param.value = self._expand_annual_to_hourly(annual_demand)
        return

    def get_asset_sizes(self):
        asset_identity = self.asset_name + r"_location_" + str(self.node_location)
        return {asset_identity: self.demand_param.value}