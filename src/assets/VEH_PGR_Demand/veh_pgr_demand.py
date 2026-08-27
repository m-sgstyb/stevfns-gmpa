#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import numpy as np
import cvxpy as cp
import pandas as pd
import os
from ..Base_Assets import Asset_STEVFNs
from ...network import Edge_STEVFNs

class VEH_PGR_Demand_Asset(Asset_STEVFNs):
    """
    Class of Passenger Demand (vehicles)
    """
    asset_name = "VEH_PGR_Demand"
    node_type = "PGR"
    period = 1
    transport_time = 0
    
    def __init__(self):
            super().__init__()
            return
        
    def define_structure(self, asset_structure):
        self.asset_structure = asset_structure
        self.node_location = asset_structure["Location_1"]
        self.num_years = int(self.network.system_parameters_df.loc["project_life", "value"] / 8760)
        self.source_node_times = np.arange(0, self.num_years, self.period) # create annual nodes
        self.number_of_edges = len(self.source_node_times)
        self.flows = cp.Parameter(shape=(self.num_years,), nonneg=True,
                                    name=f"vehicle_freight_demand_{self.asset_name}")
        return
    
    def build_costs(self):
        self.cost = cp.Constant(0)
        return
    
    def build_edge(self):
        """
        Edge from each annual demand node
        """
        for year in range(self.number_of_edges):
            new_edge = Edge_STEVFNs()
            self.edges += [new_edge]
            # Attach edge from demand node type to null
            new_edge.attach_source_node(self.network.extract_node(
                self.node_location, self.node_type, self.source_node_times[year]))
            new_edge.flow = self.flows[year]
        return
    
    def build_edges(self):
        self.edges = []
        self.build_edge()

    def _load_demand_trajectory(self):
        trajectory_value = self.parameters_df.get("annual_demand")
        
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

    def _load_parameters_df(self, asset_type):
        super()._load_parameters_df(asset_type)
        
    def _update_parameters(self):
        self.flows.value = self._load_demand_trajectory()
        return