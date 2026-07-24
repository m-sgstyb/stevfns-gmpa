#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Nov  3 13:25:54 2021

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

class EL_Demand_Asset(Asset_STEVFNs):
    """
    Electricity demand asset with time-dependence.
    """
    asset_name = "EL_Demand"
    node_type = "EL"

    def __init__(self):
        super().__init__()
        return

    def define_structure(self, asset_structure):
        self.node_location = asset_structure["Location_1"]
        self.node_times = np.arange(
            asset_structure["Start_Time"],
            asset_structure["End_Time"],
            asset_structure["Period"]
        )
        self.number_of_edges = len(self.node_times)
        self.num_years = int(self.network.system_parameters_df.loc["project_life", "value"] / 8760)
        self.flows = cp.Parameter(shape=self.number_of_edges, nonneg=True, name=f"flows_{self.asset_name}")
        return

    def build_cost(self):
        self.cost = cp.Constant(0)
        return

    def build_edge(self, edge_number):
        node_time = self.node_times[edge_number]
        new_edge = Edge_STEVFNs()
        self.edges += [new_edge]
        new_edge.attach_source_node(self.network.extract_node(
            self.node_location, self.node_type, node_time))
        new_edge.flow = self.flows[edge_number]
        return

    def build_edges(self):
        self.edges = []
        for edge_number in range(self.number_of_edges):
            self.build_edge(edge_number)
        return

    def _update_parameters(self):
        profile_filename = self.parameters_df["profile_filename"] + r".csv"
        profile_path = os.path.join(self.parameters_folder, "profiles", profile_filename)
        profile_df = pd.read_csv(profile_path)

        demand_column = self.parameters_df.get("profile_column", "Demand")
        full_profile = np.array(profile_df[demand_column])

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

        self.flows.value = new_profile[:self.number_of_edges]
        return

    def _get_year_change_indices(self):
        hours_per_day = 24
        days_per_year = int((self.number_of_edges / hours_per_day) / self.num_years)
        hours_per_year = days_per_year * hours_per_day
        self.year_change_indices = [i * hours_per_year for i in range(self.num_years)]
        return list(self.year_change_indices)

    def component_size(self):
        """Yearly demand totals"""
        if self.flows.value is None:
            return None

        # re-scale to approximate total annnual demand value with sampled data
        hours_per_day = 24
        sampled_days = int((self.number_of_edges / hours_per_day) / self.num_years)
        scaling_factor = 365 / sampled_days

        year_indices = self._get_year_change_indices() + [len(self.flows.value)]
        
        return np.array([
            np.sum(self.flows.value[start:end]) * scaling_factor
            for start, end in zip(year_indices[:-1], year_indices[1:])
        ])

    def get_asset_sizes(self):
        asset_identity = f"{self.asset_name}_location_{self.node_location}"
        return {asset_identity: self.component_size()}

    def get_yearly_flows(self):
        """Demand hourly flow slices split by each sampled year."""
        if not hasattr(self, "year_change_indices"):
            self._get_year_change_indices()

        flows_full = self.flows.value
        if flows_full is None:
            raise ValueError("Flow values not assigned yet.")
        if not isinstance(flows_full, np.ndarray):
            flows_full = np.array(flows_full)

        year_indices = list(self.year_change_indices) + [len(flows_full)]
        return [flows_full[start:end] for start, end in zip(year_indices[:-1], year_indices[1:])]