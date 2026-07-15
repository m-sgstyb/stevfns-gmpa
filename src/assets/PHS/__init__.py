#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Feb  5 14:21:19 2026

@author: Mónica Sagastuy-Breña
Extended based on BESS asset, author: aniqahsan
"""
import cvxpy as cp
import numpy as np
from ..Base_Assets import Asset_STEVFNs
from ..Base_Assets import Multi_Asset
from ...network import Edge_STEVFNs


class Pumping_Asset(Asset_STEVFNs):
    """
    Grid -> Reservoir (pumping component). 
    pump_cap is MWh/h (i.e., equivalent to MW per-hour discretisation).
    conversion_fun should return energy added to reservoir in same units as storage node (MWh)
    """
    asset_name = "Pumping"
    source_node_type = "EL"
    target_node_type = "PHS"
    
    @staticmethod
    def cost_fun(flows, params):
        sizing_constant = params["pumping_sizing_constant"]
        usage_constant = params["pumping_usage_constant"]
        return cp.maximum(sizing_constant * cp.max(flows), usage_constant * cp.sum(flows))

    @staticmethod
    def conversion_fun(flows, params):
        """
        Converts the flows (GWh pumped at each hour) into energy added to reservoir node.
        params expected: 'pumping_conversion_eff' (scalar)
        
        """
        pumping_efficiency = params["pumping_conversion_eff"]
        return flows * pumping_efficiency
    
    def __init__(self):
        super().__init__()
        # For path-dependent extenstion, may need vector costs. Adapt Parameter shapes as needed
        self.cost_fun_params = {
            "pumping_sizing_constant": cp.Parameter(nonneg=True, name=f"pumping_sizing_constant_{self.asset_name}"),
            "pumping_usage_constant": cp.Parameter(nonneg=True, name=f"pumping_usage_constant_{self.asset_name}")
            }
        self.conversion_fun_params = {
            "pumping_conversion_eff": cp.Parameter(nonneg=True, name=f"pumping_conv_efficiency_{self.asset_name}"),
            }
        return

    def define_structure(self, asset_structure):
        super().define_structure(asset_structure)
        self.target_node_location = self.source_node_location
        # sel.flows here: hourly GWh pumped (one value per edge)
        self.flows = cp.Variable(self.number_of_edges, nonneg = True)
        return
    
    def build_edges(self):
        super().build_edges()
        return

    def _load_parameters_df(self, parameters_df):
        self.parameters_df = parameters_df
        return

    def _update_sizing_constant(self):
        N = np.ceil(self.network.system_parameters_df.loc["project_life", "value"]/self.parameters_df["lifespan"])
        r = (1 + self.network.system_parameters_df.loc["discount_rate", "value"])**(-self.parameters_df["lifespan"]/8760)
        NPV_factor = (1-r**N)/(1-r)
        self.cost_fun_params["pumping_sizing_constant"].value = self.cost_fun_params["pumping_sizing_constant"].value * NPV_factor
        return
     
    def _update_usage_constant(self):
        simulation_factor = 8760/self.network.system_structure_properties["simulated_timesteps"]
        N = np.ceil(self.network.system_parameters_df.loc["project_life", "value"]/8760)
        r = (1 + self.network.system_parameters_df.loc["discount_rate", "value"])**-1
        NPV_factor = (1-r**N)/(1-r)
        self.cost_fun_params["pumping_usage_constant"].value = (self.cost_fun_params["pumping_usage_constant"].value * 
                                                        NPV_factor * simulation_factor)
        return
    
    def _update_parameters(self):
        super()._update_parameters()
        # Update Usage Parameters Based on NPV
        self._update_usage_constant()
        self._update_sizing_constant()
        return


class Turbine_Asset(Asset_STEVFNs):
    """
    Reservoir -> Grid (turbine/generator component).
    flows are hourly energy (MWh produced during the hour).
    """
    asset_name = "Turbine"
    source_node_type = "PHS"
    target_node_type = "EL"

    @staticmethod
    def cost_fun(flows, params):
        sizing_constant = params["turbine_sizing_constant"]
        usage_constant = params["turbine_usage_constant"]
        return cp.maximum(sizing_constant * cp.max(flows), usage_constant * cp.sum(flows))

    @staticmethod
    def conversion_fun(flows, params):
        turbine_efficiency = params["turbine_conversion_eff"]
        return flows * turbine_efficiency
  
    def __init__(self):
        super().__init__()
        # For path-dependent extenstion, may need vector costs. Adapt Parameter shapes as needed
        self.cost_fun_params = {
            "turbine_sizing_constant": cp.Parameter(nonneg=True, name=f"turbine_sizing_constant_{self.asset_name}"),
            "turbine_usage_constant": cp.Parameter(nonneg=True, name=f"turbine_usage_constant_{self.asset_name}")
            }
        self.conversion_fun_params = {
            "turbine_conversion_eff": cp.Parameter(nonneg=True, name=f"turbine_conv_efficiency_{self.asset_name}"),
            }
        return

    def define_structure(self, asset_structure):
        super().define_structure(asset_structure)
        self.target_node_location = self.source_node_location
        self.flows = cp.Variable(self.number_of_edges, nonneg=True)
        return
    
    def build_edges(self):
        super().build_edges()
        return

    def _load_parameters_df(self, parameters_df):
        self.parameters_df = parameters_df
        return

    def _update_sizing_constant(self):
        N = np.ceil(self.network.system_parameters_df.loc["project_life", "value"]/self.parameters_df["lifespan"])
        r = (1 + self.network.system_parameters_df.loc["discount_rate", "value"])**(-self.parameters_df["lifespan"]/8760)
        NPV_factor = (1-r**N)/(1-r)
        self.cost_fun_params["turbine_sizing_constant"].value = self.cost_fun_params["turbine_sizing_constant"].value * NPV_factor
        return
     
    def _update_usage_constant(self):
        simulation_factor = 8760/self.network.system_structure_properties["simulated_timesteps"]
        N = np.ceil(self.network.system_parameters_df.loc["project_life", "value"]/8760)
        r = (1 + self.network.system_parameters_df.loc["discount_rate", "value"])**-1
        NPV_factor = (1-r**N)/(1-r)
        self.cost_fun_params["turbine_usage_constant"].value = (self.cost_fun_params["turbine_usage_constant"].value * 
                                                        NPV_factor * simulation_factor)
        return
    
    def _update_parameters(self):
        super()._update_parameters()
        # Update Usage Parameters Based on NPV
        self._update_usage_constant()
        self._update_sizing_constant()
        return


class Reservoir_Asset(Asset_STEVFNs):
    """
    Storage/reservoir: PHS(t) -> PHS(t+1). Stores energy and shifts in time
    flows are hourly energy stored (GWh carried to next timestep).
    """
    asset_name = "Reservoir"
    source_node_type = "PHS"
    target_node_type = "PHS"
    target_node_type_cap = "Reservoir_size" # Set independent node for max capacity

    @staticmethod
    def cost_fun(flows, params):
        sizing_constant = params["reservoir_sizing_constant"] # If we're building the PHS facility
        usage_constant = params["reservoir_usage_constant"]
        return cp.maximum(sizing_constant * cp.max(flows), usage_constant * cp.sum(flows))
    
    @staticmethod
    def max_cap_conversion_fun(flows, params):
        # Requires definition of a maximum reservoir capacity in GWh in parameters.csv
        maximum_capacity = params["reservoir_maximum_capacity"]
        return maximum_capacity - flows # In line with sign convention at constraint at Reservoir_size node type

    def __init__(self):
        super().__init__()
        self.cost_fun_params = {
            "reservoir_sizing_constant": cp.Parameter(nonneg=True, name=f"reservoir_sizing_constant_{self.asset_name}"),
            "reservoir_usage_constant": cp.Parameter(nonneg=True, name=f"reservoir_usage_constant_{self.asset_name}"),
            }
        self.max_cap_conversion_fun_params = {
            "reservoir_maximum_capacity": cp.Parameter(nonneg=True, name=f"reservoir_max_capacity_{self.asset_name}")
            }
        return

    def define_structure(self, asset_structure):
        super().define_structure(asset_structure)
        self.target_node_location = asset_structure["Location_1"]
        # enforce cyclic reservoir level (SOC at first hour = SOC at last hour)
        self.target_node_times[-1] = self.source_node_times[0]
        self.target_node_times[:-1] = self.source_node_times[1:]
        self.flows = cp.Variable(self.number_of_edges, nonneg=True)
        return
    
    def build_edge(self, edge_number):
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
    
    def build_max_cap_edge(self, edge_number):
        source_node_type = "NULL"
        source_node_location = self.source_node_location
        source_node_time = 0
        target_node_type = self.target_node_type_cap
        target_node_location = self.target_node_location
        target_node_time = self.target_node_times[edge_number]
        
        max_cap_edge = Edge_STEVFNs()
        self.edges += [max_cap_edge]
        if source_node_type != "NULL":
            max_cap_edge.attach_source_node(self.network.extract_node(
                source_node_location, source_node_type, source_node_time))
        if target_node_type != "NULL":
            max_cap_edge.attach_target_node(self.network.extract_node(
                target_node_location, target_node_type, target_node_time))
        max_cap_edge.flow = self.flows
        max_cap_edge.conversion_fun = self.max_cap_conversion_fun
        max_cap_edge.conversion_fun_params = self.max_cap_conversion_fun_params
        return
    
    def build_edges(self):
        self.edges = []
        for counter1 in range(self.number_of_edges):
            self.build_edge(counter1)
            self.build_max_cap_edge(counter1)
    
    def _update_sizing_constant(self):
        N = np.ceil(self.network.system_parameters_df.loc["project_life", "value"]/self.parameters_df["lifespan"])
        r = (1 + self.network.system_parameters_df.loc["discount_rate", "value"])**(-self.parameters_df["lifespan"]/8760)
        NPV_factor = (1-r**N)/(1-r)
        self.cost_fun_params["reservoir_sizing_constant"].value = self.cost_fun_params["reservoir_sizing_constant"].value * NPV_factor
        return
     
    def _update_usage_constant(self):
        simulation_factor = 8760/self.network.system_structure_properties["simulated_timesteps"]
        N = np.ceil(self.network.system_parameters_df.loc["project_life", "value"]/8760)
        r = (1 + self.network.system_parameters_df.loc["discount_rate", "value"])**-1
        NPV_factor = (1-r**N)/(1-r)
        self.cost_fun_params["reservoir_usage_constant"].value = (self.cost_fun_params["reservoir_usage_constant"].value * 
                                                        NPV_factor * simulation_factor)
        return
        
    def _load_parameters_df(self, parameters_df):
        self.parameters_df = parameters_df
        return

    def _update_parameters(self):
        super()._update_parameters()
        # Update parameters in custom conversion function not in parent class
        for parameter_name, parameter in self.max_cap_conversion_fun_params.items():
            parameter.value = self.parameters_df[parameter_name]
        # Set Usage Parameters Based on NPV
        self._update_usage_constant()
        self._update_sizing_constant()
        return


class PHS_Asset(Multi_Asset):
    """
    Country-level generic Pumped Hydro Storage multi-asset.
    """
    asset_name = "PHS"
    assets_class_dictionary = {
        "Pumping": Pumping_Asset,
        "Turbine": Turbine_Asset,
        "Reservoir": Reservoir_Asset
    }

    @staticmethod
    def cost_fun(costs_dictionary, cost_fun_params):
        """Sum of component costs. Expects costs_dictionary to contain named costs for Pumping, Turbine, Reservoir.
        cost_fun_params can be used for top-level aggregator constants if needed."""
        return sum(costs_dictionary.values())
    
    def define_structure(self, asset_structure):
        self.asset_structure = asset_structure
        self._define_asset_structures()
        self.target_node_location = self.assets_dictionary["Reservoir"].target_node_location
        return

    def _update_assets(self):
        """Propagate parameter updates to subassets like BESS."""
        for asset_name, asset in self.assets_dictionary.items():
            asset.update(self.parameters_df)   
        return
    
    def asset_size(self):
        """
        Returns the reservoir capacity as the asset size, maximum of hourly
        storage to storage flows
        """
        # Cache capacity values to access sizing results per component quickly
        self.pump_cap = self.assets_dictionary["Pumping"].component_size()
        self.turbine_cap = self.assets_dictionary["Turbine"].component_size()
        self.reservoir_cap = self.assets_dictionary["Reservoir"].component_size()
        return self.reservoir_cap  # GWh
