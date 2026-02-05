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


class Pumping_Asset(Asset_STEVFNs):
    """
    Grid -> Reservoir (pumping). 
    pump_cap is MWh/h (i.e., equivalent to MW per-hour discretisation).
    conversion_fun should return energy added to reservoir in same units as storage node (MWh)
    """
    asset_name = "Pumping"
    source_node_type = "EL"
    target_node_type = "PHS"

    @staticmethod
    def cost_fun(flows, params):
        """Keep same style as other assets (sizing OR usage). We'll use both in PHS top-level cost."""
        sizing_constant = params["pumping_sizing_constant"]
        usage_constant = params["pumping_usage_constant"]
        # You can keep the same convex pattern (max of peak capex vs usage) or adapt in the top-level PHS asset.
        return cp.maximum(sizing_constant * cp.max(flows), usage_constant * cp.sum(flows))

    @staticmethod
    def conversion_fun(flows, params):
        """Convert the flows (MWh pumped during hour) into energy added to reservoir node.
        For standard discretisation where flows are already MWh, this may be identity * efficiency.
        params expected: 'pumping_conversion_eff' (scalar or vector) and optional dt if flows are MW.
        Implementation supports either:
          - flows are MWh already -> conversion = eff * flows
          - flows are MW and dt param provided -> conversion = eff * flows * dt
        """
        # expected params: pumping_conversion_eff (scalar or vector), pumping_dt (optional)
        eff = params["pumping_conversion_eff"]
        if "pumping_dt" in params and params["pumping_dt"] is not None:
            dt = params["pumping_dt"]
            return eff * dt * flows
        else:
            return eff * flows

    def __init__(self):
        super().__init__()
        # cost fun params
        self.cost_fun_params = {
            "pumping_sizing_constant": cp.Parameter(nonneg=True),
            "pumping_usage_constant": cp.Parameter(nonneg=True)
        }
        # conversion params: efficiency & optional dt (hours per timestep)
        # If you will pass a vector (time-varying eff), set shape when loading parameters in define_structure
        self.conversion_fun_params = {
            "pumping_conversion_eff": cp.Parameter(nonneg=True),
            "pumping_dt": cp.Parameter(nonneg=True)  # default to 1 if hourly; set to None if not used
        }
        # sizing decision variable (peak hourly MWh pumped; i.e. MW when dt=1h)
        self.pump_cap = None  # will be cp.Variable after define_structure
        return

    def define_structure(self, asset_structure):
        super().define_structure(asset_structure)
        # flows: hourly MWh pumped (one value per edge)
        self.target_node_location = self.source_node_location
        self.flows = cp.Variable(self.number_of_edges, nonneg=True)
        # sizing variable (scalar)
        self.pump_cap = cp.Variable(1, nonneg=True)
        return

    def sizing_constraints(self):
        """Return linear constraints ensuring pump_cap >= flows[t] for all time steps.
        Call these from the global model builder and add to constraints list."""
        if self.pump_cap is None:
            return []
        # vector inequality: pump_cap >= flows elementwise
        # Achieve: cp.vstack([self.pump_cap]*self.number_of_edges) >= self.flows
        # Simpler: self.flows <= self.pump_cap (broadcasting)
        return [self.flows <= self.pump_cap]

    def _load_parameters_df(self, parameters_df):
        self.parameters_df = parameters_df
        return

    def component_size(self):
        """Return sizing decision variable (for top-level sizing logic)."""
        return self.pump_cap


class Turbine_Asset(Asset_STEVFNs):
    """
    Reservoir -> Grid (turbine/generator).
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
        """Convert turbine electrical output flows into energy removed from reservoir.
        If flows are MWh electrical produced in the hour, and eff is turbine_eff, then energy_removed = flows / eff
        If you pass flows as MW, supply dt parameter and do flows*dt/eff.
        """
        eff = params["turbine_conversion_eff"]
        if "turbine_dt" in params and params["turbine_dt"] is not None:
            dt = params["turbine_dt"]
            return (dt * flows) / eff
        else:
            return flows / eff

    def __init__(self):
        super().__init__()
        self.cost_fun_params = {
            "turbine_sizing_constant": cp.Parameter(nonneg=True),
            "turbine_usage_constant": cp.Parameter(nonneg=True)
        }
        self.conversion_fun_params = {
            "turbine_conversion_eff": cp.Parameter(nonneg=True),
            "turbine_dt": cp.Parameter(nonneg=True)
        }
        self.turbine_cap = None
        return

    def define_structure(self, asset_structure):
        super().define_structure(asset_structure)
        self.target_node_location = self.source_node_location
        self.flows = cp.Variable(self.number_of_edges, nonneg=True)
        self.turbine_cap = cp.Variable(1, nonneg=True)
        return
    
    # Need to add an edge to cap the sizing via a parameter to ensure convexity 
    # and in line with the STEVFNs formatting

    def sizing_constraints(self):
        if self.turbine_cap is None:
            return []
        return [self.flows <= self.turbine_cap]

    def _load_parameters_df(self, parameters_df):
        self.parameters_df = parameters_df
        return

    def component_size(self):
        return self.turbine_cap


class Reservoir_Asset(Asset_STEVFNs):
    """
    Storage/reservoir: PHS(t) -> PHS(t+1). Stores energy and shifts in time
    lows are hourly energy stored (MWh carried to next timestep).
    """
    asset_name = "Reservoir"
    source_node_type = "PHS"
    target_node_type = "PHS"

    @staticmethod
    def cost_fun(flows, params):
        sizing_constant = params["reservoir_sizing_constant"] # If we're building the PHS facility
        usage_constant = params["reservoir_usage_constant"]
        return cp.maximum(sizing_constant * cp.max(flows), usage_constant * cp.sum(flows))

    def __init__(self):
        super().__init__()
        self.cost_fun_params = {
            "reservoir_sizing_constant": cp.Parameter(nonneg=True),
            "reservoir_usage_constant": cp.Parameter(nonneg=True)
        }
        self.reservoir_cap = None  # GWh sizing variable
        return

    def define_structure(self, asset_structure):
        super().define_structure(asset_structure)
        self.target_node_location = self.source_node_location
        # shift times like BESS Storage_Asset: target_node_times[-1] = source_node_times[0], etc.
        self.target_node_times[-1] = self.source_node_times[0]
        self.target_node_times[:-1] = self.source_node_times[1:]
        self.flows = cp.Variable(self.number_of_edges, nonneg=True)
        return
    
    # Add edge for sizing constraints into a max capacity node for existing caps.

    # def sizing_constraints(self):
    #     if self.reservoir_cap is None:
    #         return []
    #     # reservoir level E[t] is implicitly represented by store flows sequence (depends on node balances).
    #     # However we guarantee reservoir_cap >= flows elementwise (so cap bounds carryover)
    #     return [self.flows <= self.reservoir_cap]

    def _load_parameters_df(self, parameters_df):
        self.parameters_df = parameters_df
        return

    def component_size(self):
        return self.reservoir_cap


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
        # Sum all component cost expressions
        total = None
        for v in costs_dictionary.values():
            if total is None:
                total = v
            else:
                total = total + v
        return total

    def __init__(self):
        super().__init__()
        # keep reference to sub-asset sizing vars for convenience
        self.pump_cap = None
        self.turbine_cap = None
        self.reservoir_cap = None

        # optional duration parameter (hours) as cp.Parameter to allow reservoir >= turbine * D
        self.min_duration_hours = cp.Parameter(nonneg=True, value=0.0)

        # a place to set top-level penalty or country premium (optional)
        self.cost_fun_params = {"development_premium": cp.Parameter(nonneg=True)}
        return

    def _update_assets(self):
        """Propagate parameter updates to subassets like BESS."""
        for asset_name, asset in self.assets_dictionary.items():
            asset.update(self.parameters_df)
        # cache sizing variables
        self.pump_cap = self.assets_dictionary["Pumping"].component_size()
        self.turbine_cap = self.assets_dictionary["Turbine"].component_size()
        self.reservoir_cap = self.assets_dictionary["Reservoir"].component_size()
        return

    def asset_size(self):
        """
        Return a single effective scalar size
        We compute three normalized components (power and energy) and return the max to be conservative,
        similar to the BESS approach.
        Note: users can override how sizing constants map to common dimension.
        """
        effective_component_sizes = np.zeros(3)
        # handle None or cp.Variable carefully: this function may be called before variables exist
        try:
            pumping_size = np.squeeze(self.assets_dictionary["Pumping"].component_size().value) \
                           if isinstance(self.assets_dictionary["Pumping"].component_size(), cp.Parameter) \
                           else self.assets_dictionary["Pumping"].component_size()
        except Exception:
            pumping_size = 0.0
        try:
            turbine_size = np.squeeze(self.assets_dictionary["Turbine"].component_size().value) \
                            if isinstance(self.assets_dictionary["Turbine"].component_size(), cp.Parameter) \
                            else self.assets_dictionary["Turbine"].component_size()
        except Exception:
            turbine_size = 0.0
        try:
            reservoir_size = np.squeeze(self.assets_dictionary["Reservoir"].component_size().value) \
                             if isinstance(self.assets_dictionary["Reservoir"].component_size(), cp.Parameter) \
                             else self.assets_dictionary["Reservoir"].component_size()
        except Exception:
            reservoir_size = 0.0

        # Bring into same "units" by scaling if desired; here we assume reservoir_sizing_constant maps GWh to same base unit:
        effective_component_sizes[0] = pumping_size
        effective_component_sizes[1] = turbine_size
        effective_component_sizes[2] = reservoir_size
        # If these are cvxpy vars, returning a python float isn't appropriate; the framework expecting a scalar may handle differently.
        # Return the max as a conservative effective size
        try:
            return np.max(effective_component_sizes)
        except Exception:
            # If any entries are cvxpy Variables, return a cp expression approximating max via cp.maximum
            return cp.maximum(cp.maximum(effective_component_sizes[0], effective_component_sizes[1]), effective_component_sizes[2])

    # def sizing_constraints(self):
    #     """Collect sizing constraints from subassets and also add optional duration constraint:
    #        reservoir_cap >= turbine_cap * min_duration_hours
    #        Return a list of cp.Constraint objects to be appended to the global model.
    #        IMPORTANT: the global model builder must call this and include the returned constraints.
    #     """
    #     constraints = []
    #     # gather subasset sizing constraints
    #     for asset in self.assets_dictionary.values():
    #         if hasattr(asset, "sizing_constraints"):
    #             constraints += asset.sizing_constraints()

    #     # Add linear minimum-duration constraint if desired (min_duration_hours > 0)
    #     if (self.reservoir_cap is not None) and (self.turbine_cap is not None):
    #         # reservoir_cap (MWh) >= turbine_cap (MWh/h) * duration_hours
    #         # Note: min_duration_hours is a cp.Parameter
    #         constraints += [self.reservoir_cap >= self.turbine_cap * self.min_duration_hou*]()
