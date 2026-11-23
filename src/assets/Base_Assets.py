#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import cvxpy as cp
import numpy as np
import pandas as pd
import os
from ..network import Edge_STEVFNs

####### Define Classes #######

class Asset_STEVFNs:
    """
    Base Class of STEVFNs generalised asset models
    """

    asset_name = "Asset_STEVFNs"
    source_node_type = "NULL"
    target_node_type = "NULL"

    cost_fun = staticmethod(lambda flows, params: cp.Constant(0))
    conversion_fun = staticmethod(lambda flow, params: flow)

    def __init__(self):
        self.cost_fun_params = dict()
        self.conversion_fun_params = dict()
        return
    
    def build_cost(self):
        self.cost = self.cost_fun(self.flows, self.cost_fun_params)
        return
    
    def build_edge(self, edge_number):
        """Standard build edge method for hourly Edges
        in self.number_of_edges (number of sampled timesteps)"""
        source_node_time = self.source_node_times[edge_number]
        target_node_time = self.target_node_times[edge_number]
        new_edge = Edge_STEVFNs()
        self.edges += [new_edge]
        if self.source_node_type != "NULL":
            new_edge.attach_source_node(self.network.extract_node(
                self.source_node_location, self.source_node_type, source_node_time))
        if self.target_node_type != "NULL":
            new_edge.attach_target_node(self.network.extract_node(
                self.target_node_location, self.target_node_type, target_node_time))
        new_edge.flow = self.flows[edge_number]
        new_edge.conversion_fun = self.conversion_fun
        new_edge.conversion_fun_params = self.conversion_fun_params
        return
    
    def build_edges(self):
        self.edges = []
        for counter1 in range(self.number_of_edges):
            self.build_edge(counter1)
        return
    
    def get_plot_data(self):
        """Returns asset.flows.value for plotting.
        Legacy from plotting from single year model version"""
        return self.flows.value
    
    def build(self):
        self.build_edges()
        self.build_cost()
        return
    
    def define_structure(self, asset_structure):
        self.asset_structure = asset_structure
        self.source_node_location = asset_structure["Location_1"]
        self.source_node_times = np.arange(asset_structure["Start_Time"], 
                                           asset_structure["End_Time"], 
                                           asset_structure["Period"])
        self.target_node_location = asset_structure["Location_2"]
        self.target_node_times = np.arange(asset_structure["Start_Time"], 
                                           asset_structure["End_Time"], 
                                           asset_structure["Period"])
        self.number_of_edges = len(self.source_node_times) # Total hourly timesteps sampled
        self.num_years = int(self.network.system_parameters_df.loc["project_life", "value"] / 8760) # Project length in years
        self.flows = cp.Constant(np.zeros(self.number_of_edges)) # hourly flows definition
        return
    
    def _load_parameters_df(self, asset_type):
        self.parameters_folder = os.path.join(self.network.base_folder, "src", "assets", 
                                           self.asset_name)
        parameters_filename = os.path.join(self.parameters_folder, "parameters.csv")
        self.parameters_df = pd.read_csv(parameters_filename).iloc[asset_type]
        return
    
    def _update_parameters(self):
        """Defines and updates values per parameter"""
        for parameter_name, parameter in self.cost_fun_params.items():
            parameter.value = self.parameters_df[parameter_name]
        for parameter_name, parameter in self.conversion_fun_params.items():
            parameter.value = self.parameters_df[parameter_name]
        return
    
    def update(self, asset_type):
        """Update param values in every scenario run"""
        self._load_parameters_df(asset_type)
        self._update_parameters()
        return

    def _compute_period_counts(self):
        """Sets num_years, reinvestment_period, num_periods from system
        parameters for time dependence"""
        self.num_years = int(self.network.system_parameters_df.loc["project_life", "value"] / 8760)
        self.reinvestment_period = int(self.network.system_parameters_df.loc["reinvestment_period", "value"] / 8760)
        self.num_periods = int(np.ceil(self.num_years / self.reinvestment_period))
        return

    def _get_year_change_indices(self):
        """Hourly indices at which each year starts with sampled timesteps.
        Requires self.number_of_edges and _compute_period_counts() already run."""
        hours_per_day = 24
        days_per_year = int((self.number_of_edges / hours_per_day) / self.num_years)
        hours_per_year = days_per_year * hours_per_day
        self.year_change_indices = [i * hours_per_year for i in range(self.num_years)]
        return list(self.year_change_indices)

    def _get_period_change_indices(self):
        """Hourly indices at which each reinvestment period starts with sampled timesteps.
        Requires self.number_of_edges and _compute_period_counts() already run."""
        hours_per_day = 24
        days_per_year = int((self.number_of_edges / hours_per_day) / self.num_years)
        hours_per_year = days_per_year * hours_per_day
        hours_per_period = hours_per_year * self.reinvestment_period
        self.period_change_indices = [i * hours_per_period for i in range(self.num_periods)]
        return self.period_change_indices

    def _period_index_for_edge(self, edge_number):
        period_index = 0
        for i, idx in enumerate(self.period_change_indices):
            if edge_number >= idx:
                period_index = i
            else:
                break
        return period_index
    
    def _years_in_period(self, period_index):
        """Number of modelled years falling within a given reinvestment
        period. Handles a possibly-truncated final period (e.g. project_life
        = 27 years, reinvestment_period = 5 years -> last period is 2 years,
        not 5), so 'average per year' figures in results aren't silently inflated/
        deflated for that period."""
        period_start_year = period_index * self.reinvestment_period
        period_end_year = min(period_start_year + self.reinvestment_period, self.num_years)
        return period_end_year - period_start_year
    
    def size(self):
        """Returns size of asset
        Defaults as maximum of asset.flows; can be overridden 
        Based on asset (child class) design
        """
        return self.flows.value.max()
    
    def component_size(self):
        """Returns size of component (same as asset if only 1 component)
        Defaults as maximum of asset.flows; can be overridden 
        Based on asset (child class) design
        """
        return self.flows.value.max()
    
    def asset_size(self):
        """Returns size of component directly, as defined 
        for self.component_size()"""
        return self.component_size()
    
    def get_component_size(self):
        """Returns the size of component as a dict"""
        component_size = self.component_size()
        component_identity = self.asset_name
        return {component_identity: component_size}
    
    def get_asset_size(self):
        """Returns the size of asset as a dict 
        Default is: asset_size = component size = max(flows)
        """
        asset_size = self.asset_size()
        asset_identity = self.asset_name
        return {asset_identity: asset_size}

    # --- Result-extraction interface ---

    def get_period_costs(self):
        """Per-period annualised cost, length num_periods, in the same
        cost units used in the objective (Billion USD). None if this
        asset class doesn't track a per-period cost breakdown."""
        return None

    def get_period_emissions(self):
        """Per-period annualised emissions, length num_periods (MtCO2e).
        None if this asset class doesn't emit."""
        return None

    def get_new_capacity(self):
        """Per-period new installed capacity, length num_periods.
        None if this asset class has no capacity concept (e.g. a fixed
        demand asset)."""
        return None

    def get_operating_stock(self):
        """Per-period new operating capacity, length num_periods.
        None if this asset class has no capacity concept (e.g. a fixed
        demand asset)."""
        return None

    def get_results_country(self, location_lookup):
        """Resolves this asset's reporting location to an ISO-2 code via
        location_lookup (dict: Network_Structure location index ->
        Location_Parameters.csv location_name). Falls back from source to
        target location. NOTE: for assets that span two locations (e.g.
        *Transport* asset classes), this only reports the source-side
        country -- see caveats in compile_results.py."""

        source_loc = getattr(self, "source_node_location", None)
        target_loc = getattr(self, "target_node_location", None)
        for loc in (source_loc, target_loc):
            if loc is not None and loc != "NULL" and loc in location_lookup:
                return location_lookup[loc]
        return None

    def get_results_technology_name(self, readable_names_df):
        """Looks up this asset's readable technology name from
        readable_names.csv (columns: Asset_Class, Readable_Name). Falls
        back to the raw asset_name if there's no matching row, so a
        missing readable_names.csv entry never silently drops data."""

        matches = readable_names_df.loc[readable_names_df["Asset_Class"] == self.asset_name]
        if len(matches) == 0:
            return self.asset_name
        return matches.iloc[0]["Readable_Name"]

    def get_results_records(self, readable_names_df, location_lookup,
                             start_year, reinvestment_period_years):
        """Builds long-format result rows for this asset:
        [{country, year, technology, metric, unit, value}, ...]
        matching the costsovertime.csv / emissionsovertime.csv schema
        (scenario_id/scenario_type/case_id are added later by the
        compiler, since those are scenario-level, not asset-level).
        """
        technology = self.get_results_technology_name(readable_names_df)
        country = self.get_results_country(location_lookup)

        metric_specs = [
            ("cost", "Billion USD", self.get_period_costs),
            ("emissions", "MtCO2e", self.get_period_emissions),
            ("new_capacity", getattr(self, "capacity_unit", "GWp"), self.get_new_capacity),
            ("stock_capacity", getattr(self, "capacity_unit", "GWp"), self.get_operating_stock)
        ]

        records = []
        for metric_name, unit, getter in metric_specs:
            values = getter()
            if values is None:
                continue
            for period_index, value in enumerate(values):
                year = start_year + period_index * reinvestment_period_years
                records.append({
                    "country": country,
                    "year": year,
                    "technology": technology,
                    "metric": metric_name,
                    "unit": unit,
                    "value": value,
                })
        return records

            
class Multi_Asset(Asset_STEVFNs):
    """Class that contains multiple assets
    From original STEVFNs framework"""
    asset_name = "Multi_Asset"
    cost_fun = staticmethod(lambda costs_dictionary, cost_fun_params: cp.Constant(0))
    assets_class_dictionary = dict() # dictionary that contains assetclasses
    def __init__(self):
        super().__init__()
        self.assets_dictionary = dict()
        self._generate_assets()
        self.costs_dictionary = dict()
        return
    
    def _generate_assets(self):
        for asset_name, asset_class in self.assets_class_dictionary.items():
            self.assets_dictionary[asset_name] = self.assets_class_dictionary[asset_name]()
        return
    
    def build(self):
        self._build_assets()
        self.build_cost()
        return
    
    def build_cost(self):
        for asset_name, asset in self.assets_dictionary.items():
            self.costs_dictionary[asset_name] = asset.cost
        self.cost = self.cost_fun(self.costs_dictionary, self.cost_fun_params)
        return
    
    def _build_assets(self):
        for asset_name, asset in self.assets_dictionary.items():
            asset.build()
        return
    
    def define_structure(self, asset_structure):
        self.asset_structure = asset_structure
        self._define_asset_structures()
        return
    
    def _define_asset_structures(self):
        for asset_name, asset in self.assets_dictionary.items():
            asset.network = self.network
            asset.define_structure(self.asset_structure)
        return
    
    def update(self, asset_type):
        super().update(asset_type)
        self._update_assets()
        return
    
    def _update_assets(self):
        for asset_name, asset in self.assets_dictionary.items():
            asset_type = self.parameters_df[asset_name + "_asset_type"]
            asset.update(asset_type)
        return
    
    def get_plot_data(self):
        flow_dictionary = dict()
        for asset_name, asset in self.assets_dictionary.items():
            flow_dictionary[asset_name] = asset.get_plot_data()
        return flow_dictionary
    
    def size(self):
        asset_sizes_dictionary = dict()
        for asset_name, asset in self.assets_dictionary.items():
            asset_sizes_dictionary[asset_name] = asset.size()
        return asset_sizes_dictionary
    
    def get_asset_sizes(self):
        # Returns the size of the asset as a dict #
        assets_sizes_dict = dict()
        for asset_name, asset in self.assets_dictionary.items():
            assets_sizes_dict.update(asset.get_asset_sizes())
        new_assets_sizes_dict = dict()
        for asset_identity, asset_size in assets_sizes_dict.items():
            new_asset_identity = self.asset_name + r"_" + asset_identity
            new_assets_sizes_dict[new_asset_identity] = asset_size
        return new_assets_sizes_dict
    
    def get_component_sizes(self):
        # Returns the size of components of the asset as a dict #
        component_sizes_dict = dict()
        for component_name, component in self.assets_dictionary.items():
            component_sizes_dict.update(component.get_component_size())
        new_component_sizes_dict = dict()
        for component_identity, component_size in component_sizes_dict.items():
            new_component_identity = self.asset_name + r"_" + component_identity
            new_component_sizes_dict[new_component_identity] = component_size
        return new_component_sizes_dict
    
    def asset_size(self):
        # Returns size of asset #
        component_size_df = self.get_component_sizes()
        asset_size = np.array(list(component_size_df.values())).max()
        return asset_size
    
    def get_asset_size(self):
        # Returns the size of asset as a dict #
        asset_identity = self.asset_name
        asset_size = self.asset_size()
        return {asset_identity : asset_size}