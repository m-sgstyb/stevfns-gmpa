#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Feb 20 15:14:31 2026

@author: Mónica Sagastuy-Breña
"""

import numpy as np
import cvxpy as cp
from ..Base_Assets import Asset_STEVFNs
from ..Base_Assets import Multi_Asset
from ...network import Edge_STEVFNs

class CEM_Milling_Asset(Asset_STEVFNs):
    """
    Class of Cement/Clinker Milling Asset (single optimisation variable: cement output per timestep)
    Abstracts production process, except for heat supply
    Produces: cement (main output edge)
    Additional conversion edges:
      - CO2 emissions (process + fuel) -> negative conversion to CO2 budget node
      - Electricity consumption (grinding etc.) -> conversion from EL node
      - Heat consumption (kiln) -> conversion to high temp heat demand node
    """
    asset_name = "CEM_Milling"
    # Nodes for edges to the annual cement demand node
    source_node_type = "NULL"
    target_node_type = "CEM" 
    target_node_time = 0
    # Nodes for edges to global emissions node
    target_node_type_2 = "CO2_Budget" 
    target_node_location_2 = 0 # CO2_Budget Asset node location
    target_node_time_2 = 0 # CO2_Budget Asset node time
    # Nodes for electricity edges from grid
    source_node_type_3 = "EL"
    target_node_type_3 = "NULL"
    # Nodes for kiln
    source_node_type_4 = "CEM_HTH" # Kiln heat requirement node 
    target_node_type_4 = "NULL"
    

    period = 1
    transport_time = 0

    @staticmethod
    def cost_fun(flows, params):
        sizing_constant = params["sizing_constant"]
        usage_constant = params["usage_constant"]
        return (sizing_constant * cp.max(flows) + usage_constant * cp.sum(flows))

    @staticmethod
    def conversion_fun_2(flows, params):
        """
        Conversion function of 
        CO2 emissions: negative conversion into CO2 budget node (flows = mass cement output)
        CO2_emissions_factor in MtCO2/Mt cement produced
        """
        CO2_emissions_factor = params["process_CO2_factor"]
        return -CO2_emissions_factor * flows

    @staticmethod
    def conversion_fun_3(flows, params):
        """
        Electricity consumption for grinding/blending (from grid (EL) node).
        electricity_intensity in GWh per Mt cement
        """
        electricity_intensity = params["electricity_intensity"] # GWh/Mtcement
        return electricity_intensity * flows
    
    @staticmethod
    def conversion_fun_4(flows, params):
        """
        Energy (heat) required for calcination per unit mass of cement produced:
            GWh per Mt cement produced. 
        """
        heat_factor = params["heat_factor"]
        return heat_factor * flows

    def __init__(self):
        super().__init__()
        # cost params (same structure as your PP)
        self.cost_fun_params = {
            "sizing_constant": cp.Parameter(nonneg=True, name=f"sizing_constant_{self.asset_name}"),
            "usage_constant": cp.Parameter(nonneg=True, name=f"usage_constant_{self.asset_name}"),
        }

        self.conversion_fun_params_2 = {"process_CO2_factor": cp.Parameter(nonneg=True,
                                                                             name=f"process_CO2_factor_{self.asset_name}")}
        self.conversion_fun_params_3 = {"electricity_intensity": cp.Parameter(nonneg=True,
                                                                              name=f"electricity_intensity:{self.asset_name}")}
        self.conversion_fun_params_4 = {"heat_factor": cp.Parameter(nonneg=True,
                                                                              name=f"heat_factor_{self.asset_name}")}
        return

    def define_structure(self, asset_structure):
        """
        asset_structure keys expected:
          - Location_1 (source / plant location)
          - Start_Time, End_Time, Period
          - Location_2 (target cement demand location)
        """
        self.asset_structure = asset_structure
        self.source_node_location = asset_structure["Location_1"]
        self.source_node_times = np.arange(
            asset_structure["Start_Time"] + self.transport_time,
            asset_structure["End_Time"] + self.transport_time,
            asset_structure.get("Period", self.period)
        )
        self.target_node_location = asset_structure["Location_2"]
        self.target_node_times = np.arange(
            asset_structure["Start_Time"] + self.transport_time,
            asset_structure["End_Time"] + self.transport_time,
            asset_structure.get("Period", self.period)
        )
        self.number_of_edges = len(self.source_node_times)
        # optimisation variable: cement produced (Mt per timestep)
        self.flows = cp.Variable(self.number_of_edges, nonneg=True)
        return

    def build_edges(self):
        """
        Build:
         - main cement output edges (attach to CEM node) no conversion_fun, 
         - CO2 emission edges (attach to CO2_Budget node) using conversion_fun_2
         - electricity consumption edges (attach to EL node) using conversion_fun_3
         - heat consumption edges (attach to CEM_HTH node) using conversion_fun_4
        """
        self.edges = []
        
        for t in range(self.number_of_edges):
            self.build_edge(t)
            self.build_edge_2(t)
            self.build_edge_3(t)
            self.build_edge_4(t)
        return

    def build_edge(self, edge_number):
        """Main cement output edge (mass)"""
        source_node_type = self.source_node_type
        source_node_location = self.source_node_location
        source_node_time = self.source_node_times[edge_number]
        target_node_type = self.target_node_type
        target_node_location = self.target_node_location
        target_node_time = self.target_node_time # links all edges to single node annual demand

        new_edge = Edge_STEVFNs()
        self.edges += [new_edge]
        if source_node_type != "NULL":
            new_edge.attach_source_node(self.network.extract_node(
                source_node_location, source_node_type, source_node_time))
        if target_node_type != "NULL":
            new_edge.attach_target_node(self.network.extract_node(
                target_node_location, target_node_type, target_node_time))
        new_edge.flow = self.flows[edge_number] # hourly mass cement output, asset optimisation variable
        return

    def build_edge_2(self, edge_number):
        """CO2 emissions edge (negative conversion into CO2 budget node)"""
        source_node_type = self.source_node_type
        source_node_location = self.source_node_location
        source_node_time = self.source_node_times[edge_number]
        target_node_type = self.target_node_type_2
        target_node_location = self.target_node_location_2
        target_node_time = self.target_node_time_2
        
        co2_edge = Edge_STEVFNs()
        self.edges += [co2_edge]
        if source_node_type != "NULL":
            co2_edge.attach_source_node(self.network.extract_node(
                source_node_location, source_node_type, source_node_time))
        if target_node_type != "NULL":
            co2_edge.attach_target_node(self.network.extract_node(
                target_node_location, target_node_type, target_node_time))
        co2_edge.flow = self.flows[edge_number]
        co2_edge.conversion_fun = self.conversion_fun_2
        co2_edge.conversion_fun_params = self.conversion_fun_params_2
        return

    def build_edge_3(self, edge_number):
        """Electricity consumption edge (conversion from EL (grid) node)"""
        source_node_type = self.source_node_type_3 # Source is EL
        source_node_location = self.source_node_location 
        source_node_time = self.source_node_times[edge_number]
        target_node_type = self.target_node_type_3
        target_node_location = self.target_node_location
        target_node_time = self.target_node_times[edge_number]

        el_edge = Edge_STEVFNs()
        self.edges += [el_edge]
        if source_node_type != "NULL":
            el_edge.attach_source_node(self.network.extract_node(
                source_node_location, source_node_type, source_node_time))
        if target_node_type != "NULL":
            el_edge.attach_target_node(self.network.extract_node(
                target_node_location, target_node_type, target_node_time))
        el_edge.flow = self.flows[edge_number]
        el_edge.conversion_fun = self.conversion_fun_3
        el_edge.conversion_fun_params = self.conversion_fun_params_3
        return
    
    def build_edge_4(self, edge_number):
        """
        Edges to endogenously determine HTH demand specific to cement production
        Creates edges from CEM_HTH node to NULL (output edges)
        """
        source_node_type = self.source_node_type_4
        source_node_location = self.source_node_location
        source_node_time = self.source_node_times[edge_number]
        target_node_type = self.target_node_type_4
        target_node_location = self.target_node_location
        target_node_time = self.target_node_times[edge_number]
        
        hth_edge = Edge_STEVFNs()
        self.edges += [hth_edge]
        if source_node_type != "NULL":
            hth_edge.attach_source_node(self.network.extract_node(
                source_node_location, source_node_type, source_node_time))
        if target_node_type != "NULL":
            hth_edge.attach_target_node(self.network.extract_node(
                target_node_location, target_node_type, target_node_time))
        hth_edge.flow = self.flows[edge_number]
        hth_edge.conversion_fun = self.conversion_fun_4
        hth_edge.conversion_fun_params = self.conversion_fun_params_4
        return

    def _update_sizing_constant(self):
        """
        Update sizing constant to account for total project lifetime and NPV
        """
        N = np.ceil(self.network.system_parameters_df.loc["project_life", "value"]
                    / self.parameters_df["lifespan"])
        r = (1 + self.network.system_parameters_df.loc["discount_rate", "value"])**(
            -self.parameters_df["lifespan"] / 8760)
        NPV_factor = (1 - r**N) / (1 - r)
        self.cost_fun_params["sizing_constant"].value = (
            self.cost_fun_params["sizing_constant"].value * NPV_factor)
        return

    def _update_usage_constants(self):
        """
        Update usage constant to account for total project lifetime, simulated 
        timesteps and NPV
        """
        simulation_factor = 8760 / self.network.system_structure_properties["simulated_timesteps"]
        N = np.ceil(self.network.system_parameters_df.loc["project_life", "value"] / 8760)
        r = (1 + self.network.system_parameters_df.loc["discount_rate", "value"])**-1
        NPV_factor = (1 - r**N) / (1 - r)
        self.cost_fun_params["usage_constant"].value = (
            self.cost_fun_params["usage_constant"].value * NPV_factor * simulation_factor)
        return

    def _update_co2_emissions_factor(self):
        """
        Update CO2 emissions factor to account for simulated timesteps and for emissions
        over total project life
        """
        simulation_factor = 8760 / self.network.system_structure_properties["simulated_timesteps"]
        N = np.ceil(self.network.system_parameters_df.loc["project_life", "value"] / 8760)
        self.conversion_fun_params_2["process_CO2_factor"].value = (
            self.conversion_fun_params_2["process_CO2_factor"].value * simulation_factor * N)
        return

    def _update_parameters(self):
        super()._update_parameters()
        for parameter_name, parameter in self.conversion_fun_params_2.items():
            parameter.value = self.parameters_df[parameter_name]
        for parameter_name, parameter in self.conversion_fun_params_3.items():
            parameter.value = self.parameters_df[parameter_name]
        for parameter_name, parameter in self.conversion_fun_params_4.items():
            parameter.value = self.parameters_df[parameter_name]
        # Update cost parameters with NPV and simulation factors
        self._update_sizing_constant()
        self._update_usage_constants()
        self._update_co2_emissions_factor()
        return
    
    def _load_parameters_df(self, parameters_df):
        self.parameters_df = parameters_df
        return

    def get_asset_sizes(self):
        asset_size = self.size()
        asset_identity = self.asset_name + r"_location_" + str(self.node_location)
        return {asset_identity: asset_size}
    
class CEM_HTH_Asset(Asset_STEVFNs):
    """
    High-Temperature Heat (HTH) node provider:
      - Produces heat (flows in GWh per timestep) into CEM_HTH commodity node.
      - Fuel based (produces CO2 per unit energy provided)
      - Has sizing/usage costs, conversion eff (fuel->heat) and fuel CO2 factor (tCO2 / GWh fuel).
    """
    asset_name = "CEM_HTH"
    source_node_type = "NULL"
    target_node_type = "CEM_HTH"   # produces heat into this node (target)
    # optional electricity source if electric heating is modelled as supply from EL
    target_node_type_2 = "CO2_Budget"
    target_node_location_2 = 0
    target_node_time_2 = 0
    
    # source_node_type_el = "EL"
    # target_node_type_el = "NULL"

    period = 1
    transport_time = 0

    @staticmethod
    def cost_fun(flows, params):
        sizing_constant = params["hth_sizing_constant"]
        usage_constant = params["hth_usage_constant"]
        return (sizing_constant * cp.max(flows) + usage_constant * cp.sum(flows))

    @staticmethod
    def conversion_fun_2(flows, params):
        # compute CO2 emissions from fuel used to produce the heat (tCO2 per GWh_heat)
        fuel_co2_factor = params["fuel_co2_factor"]    # MtCO2 / GWh
        return -fuel_co2_factor * flows

    def __init__(self):
        super().__init__()
        self.cost_fun_params = {
            "hth_sizing_constant": cp.Parameter(nonneg=True, name=f"hth_sizing_constant_{self.asset_name}"),
            "hth_usage_constant": cp.Parameter(nonneg=True, name=f"hth_usage_constant_{self.asset_name}"),
        }
        self.conversion_fun_params_2 = {
            "fuel_co2_factor": cp.Parameter(nonneg=True, name=f"fuel_CO2_factor_{self.asset_name}")
        }
        return

    def define_structure(self, asset_structure):
        super().define_structure(asset_structure)
        # flows are heat energy produced per timestep (GWh)
        self.flows = cp.Variable(self.number_of_edges, nonneg=True)
        return

    def build_edges(self):
        self.edges = []
        for t in range(self.number_of_edges):
            self.build_heat_edges(t)
            self.build_emissions_edges(t)
        return
    
    def build_heat_edges(self, edge_number):
        """
        Supply of heat to meet the demand calculated in CEM_Milling
        """
        source_node_type = self.source_node_type
        source_node_location = self.source_node_location
        source_node_time = self.source_node_times[edge_number]
        target_node_type = self.target_node_type
        target_node_location = self.target_node_location
        target_node_time = self.target_node_times[edge_number]
        
        heat_edge = Edge_STEVFNs()
        self.edges += [heat_edge]
        if source_node_type != "NULL":
            heat_edge.attach_source_node(self.network.extract_node(
                source_node_location, source_node_type, source_node_time))
        if target_node_type != "NULL":
            heat_edge.attach_target_node(self.network.extract_node(
                target_node_location, target_node_type, target_node_time))
        heat_edge.flow = self.flows[edge_number]
        return
    
    def build_emissions_edges(self, edge_number):
        """
        Emissions edges from heating with fuel
        """
        source_node_type = self.source_node_type
        source_node_location = self.source_node_location
        source_node_time = self.source_node_times[edge_number]
        target_node_type = self.target_node_type_2
        target_node_location = self.target_node_location_2
        target_node_time = self.target_node_time_2
        
        co2_edge = Edge_STEVFNs()
        self.edges += [co2_edge]
        if source_node_type != "NULL":
            co2_edge.attach_source_node(self.network.extract_node(
                source_node_location, source_node_type, source_node_time))
        if target_node_type != "NULL":
            co2_edge.attach_target_node(self.network.extract_node(
                target_node_location, target_node_type, target_node_time))
        co2_edge.flow = self.flows[edge_number]
        co2_edge.conversion_fun = self.conversion_fun_2
        co2_edge.conversion_fun_params = self.conversion_fun_params_2
        return
    
    def _update_sizing_constant(self):
        """
        Update sizing constant to account for total project lifetime and NPV
        """
        N = np.ceil(self.network.system_parameters_df.loc["project_life", "value"]
                    / self.parameters_df["lifespan"])
        r = (1 + self.network.system_parameters_df.loc["discount_rate", "value"])**(
            -self.parameters_df["lifespan"] / 8760)
        NPV_factor = (1 - r**N) / (1 - r)
        self.cost_fun_params["hth_sizing_constant"].value = (
            self.cost_fun_params["hth_sizing_constant"].value * NPV_factor)
        return

    def _update_usage_constants(self):
        """
        Update usage constant to account for total project lifetime, simulated 
        timesteps and NPV
        """
        simulation_factor = 8760 / self.network.system_structure_properties["simulated_timesteps"]
        N = np.ceil(self.network.system_parameters_df.loc["project_life", "value"] / 8760)
        r = (1 + self.network.system_parameters_df.loc["discount_rate", "value"])**-1
        NPV_factor = (1 - r**N) / (1 - r)
        self.cost_fun_params["hth_usage_constant"].value = (
            self.cost_fun_params["hth_usage_constant"].value * NPV_factor * simulation_factor)
        return

    def _update_co2_emissions_factor(self):
        """
        Update CO2 emissions factor to account for simulated timesteps and for emissions
        over total project life
        """
        simulation_factor = 8760 / self.network.system_structure_properties["simulated_timesteps"]
        N = np.ceil(self.network.system_parameters_df.loc["project_life", "value"] / 8760)
        self.conversion_fun_params_2["fuel_co2_factor"].value = (
            self.conversion_fun_params_2["fuel_co2_factor"].value * simulation_factor * N)
        return

    def _load_parameters_df(self, parameters_df):
        self.parameters_df = parameters_df
        return

    def _update_parameters(self):
        super()._update_parameters()
        # set conversion params (intensive)
        for parameter_name, parameter in self.conversion_fun_params.items():
            parameter.value = self.parameters_df[parameter_name]
        for parameter_name, parameter in self.conversion_fun_params_2.items():
            parameter.value = self.parameters_df[parameter_name]
        self._update_sizing_constant()
        self._update_usage_constants()
        self._update_co2_emissions_factor()
        return

# --- Multi-asset that bundles Milling + HTH ---
class CEM_Production_Asset(Multi_Asset):
    """
    Multi-asset combining Milling (mass -> electricity + process CO2) and HTH (heat supply).
    Subassets: "Milling" and "HTH".
    """
    asset_name = "CEM_Production"
    assets_class_dictionary = {
        "Milling": CEM_Milling_Asset,
        "HTH": CEM_HTH_Asset
    }

    @staticmethod
    def cost_fun(costs_dictionary, cost_fun_params):
        return sum(costs_dictionary.values())

    def define_structure(self, asset_structure):
        # set up subasset structures
        self.asset_structure = asset_structure
        self._define_asset_structures()
        # Make asset target node location accessible
        self.target_node_location = self.assets_dictionary["Milling"].target_node_location
        return

    def _update_assets(self):
        """
        Propagate parameter updates to subassets.
        parameters_df should contain keys used by subcomponents.
        """
        for asset_name, asset in self.assets_dictionary.items():
            asset.update(self.parameters_df)
        return

    def asset_size(self):
        """
        Return a primary size metric for reporting.
        Example: return HTH peak hourly capacity (max flow variable) or milling size.
        """
        # ensure assets are sized (component_size methods)
        try:
            hth_size = self.assets_dictionary["HTH"].component_size()
        except Exception:
            # fallback: use max flow variable as size (if component_size unavailable)
            hth = self.assets_dictionary["HTH"]
            hth_size = float(np.max(np.nan_to_num(hth.flows.value))) if hasattr(hth, "flows") else 0.0
        return hth_size