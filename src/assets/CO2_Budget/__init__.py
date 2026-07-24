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

class CO2_Budget_Asset(Asset_STEVFNs):
    """CO2 budget asset enforcing a per-reinvestment-period
    emissions limit."""

    asset_name = "CO2_Budget"
    source_node_type = "NULL"
    target_node_type = "CO2_Budget"
    period = 1
    transport_time = 0

    def __init__(self):
        super().__init__()
        self.conversion_fun_params = dict()
        return

    def define_structure(self, asset_structure):
        self.asset_structure = asset_structure
        self.source_node_location = asset_structure["Location_1"]
        self.target_node_location = self.source_node_location

        self.num_years = int(self.network.system_parameters_df.loc["project_life", "value"] / 8760)
        self.reinvestment_period = int(self.network.system_parameters_df.loc["reinvestment_period", "value"] / 8760)
        self.num_periods = int(np.ceil(self.num_years / self.reinvestment_period))

        self.flows = cp.Constant(np.zeros(self.num_periods))

        self.conversion_fun_params = {
            "maximum_budget": cp.Parameter(shape=(self.num_periods,), nonneg=True,
                                            name=f"max_co2_budget_{self.asset_name}")}
        return

    def build_edge(self, period_number):
        """Build a CO2 budget edge for a single reinvestment period."""
        edge = Edge_STEVFNs()
        self.edges.append(edge)
        edge.attach_target_node(self.network.extract_node(
            self.target_node_location, self.target_node_type, period_number))
        edge.flow = self.conversion_fun_params["maximum_budget"][period_number]
        return

    def build_edges(self):
        self.edges = []
        # --- Build all budget edges ---
        for period in range(self.num_periods):
            self.build_edge(period)
        return

    def _load_budget_trajectory(self):
        """Reads this location's budget trajectory for the current scenario
        from a CSV shaped as: scenario_name, co2_budget, co2_budget_unit,
        case_study. Filters by the network's current scenario (matching
        the scenario folder name) and this asset's case_study parameter

        Ensure Asset/parameters.csv case_study value equals the relevant
        CO2_Budget profiles for all scenarios to run
        """
        trajectory_filename = self.parameters_df.get("trajectory_filename") + ".csv"
        trajectory_path = os.path.join(self.parameters_folder, "profiles", trajectory_filename)
        trajectory_df = pd.read_csv(trajectory_path)
 
        scenario_name = self.network.scenario_name # check scenario folder name
        case_study = self.parameters_df["case_study"]
        scenario_rows = trajectory_df[
            (trajectory_df["scenario_name"] == scenario_name) &
            (trajectory_df["case_study"] == case_study)
        ]
        values = scenario_rows["co2_budget"].to_numpy(dtype=float)
 
        if values.size != self.num_periods:
            raise ValueError(
                f"scenario_name='{scenario_name}', case_study='{case_study}' in "
                f"{trajectory_filename} has {values.size} matching rows, "
                f"expected {self.num_periods} (one per reinvestment period)."
            )
        return values

    def _update_parameters(self):
        self.conversion_fun_params["maximum_budget"].value = self._load_budget_trajectory()
        return

    def component_size(self):
        """Actual emissions drawn per period (positive). Read back from each
        CO2_Budget node's balance: budget + net_output_flows = -emissions.
        emissions has negative value convention coming from emitting Sources.
        This returns positive value for emissions per period."""
        emissions = np.array([
            edge.flow.value + edge.target_node.net_output_flows.value
            for edge in self.edges], dtype=float
        )
        return emissions