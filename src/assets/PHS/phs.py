#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import cvxpy as cp
import numpy as np
from ..Base_Stock_Assets import Stock_Asset_STEVFNs
from ..Base_Assets import Asset_STEVFNs
from ..Base_Assets import Multi_Asset
from ...network import Edge_STEVFNs
 
class Reservoir_Asset(Stock_Asset_STEVFNs):
    """Hourly SOC node links PHS(t) -> PHS(t+1), cyclic assumption. 
    Reservoir capacity (GWh) as decision variable"""
    asset_name = "Reservoir"
    source_node_type = "PHS"
    target_node_type = "PHS"
    stock_node_type = "Reservoir_Stock"
    capacity_node_type = "Reservoir_Capacity"
    decommission_mode = "decay_rate"
    period = 1
    transport_time = 0
 
    def define_structure(self, asset_structure):
        self.asset_structure = asset_structure
        self.source_node_location = asset_structure["Location_1"]
        self.stock_node_location = self.source_node_location
        self.source_node_times = np.arange(asset_structure["Start_Time"] + self.transport_time,
                                            asset_structure["End_Time"] + self.transport_time,
                                            self.period)
        self.target_node_location = self.source_node_location
        self.target_node_times = np.arange(asset_structure["Start_Time"] + self.transport_time,
                                            asset_structure["End_Time"] + self.transport_time,
                                            self.period)
        self.number_of_edges = len(self.source_node_times)
 
        self._define_period_structure(asset_structure)
        self.period_change_indices = self._get_period_change_indices()
        self.period_boundaries = self.period_change_indices + [self.number_of_edges]
 
        self.flows = cp.Variable(self.number_of_edges, nonneg=True, name=f"flows_{self.asset_name}")
 
        self.cost_fun_params["power_sizing_constant"] = cp.Parameter(
            shape=(self.num_periods, self.num_periods), nonneg=True,
            name=f"power_sizing_constant_{self.asset_name}")
        self.inv_hours_storage = cp.Parameter(nonneg=True, name=f"inv_hours_storage_{self.asset_name}")
 
        # cyclic soc level assumption (SOC at first hour = SOC at last hour)
        self.target_node_times[-1] = self.source_node_times[0]
        self.target_node_times[:-1] = self.source_node_times[1:]
        return
 
    def power_capacity(self, p):
        """Derive the power capacity (GW) available in period p. Called by
        Pumping_Asset/Turbine_Asset for their capacity-limit and ramp
        edges."""
        return self.carryover_out[p] * self.inv_hours_storage
 
    def build_edges(self):
        self.edges = []
        for edge_number in range(self.number_of_edges):
            self.build_edge(edge_number)
        self._build_stock_edges()
        self._build_capacity_limit_edges()
        return
 
    def _build_capacity_limit_edges(self):
        """Caps hourly SOC (self.flows) within each period at that
        period's built energy stock (carryover_out[p])."""
        for p in range(self.num_periods):
            start, end = self.period_boundaries[p], self.period_boundaries[p + 1]
            period_flows = self.flows[start:end]
 
            edge = Edge_STEVFNs()
            self.edges.append(edge)
            edge.attach_target_node(self.network.extract_node(
                self.target_node_location, self.capacity_node_type, p))
            edge.flow = self.carryover_out[p] - cp.max(period_flows)
        return
 
    def build_cost(self):
        storage_capital = cp.sum(self.cost_fun_params["sizing_constant"] @ self.new_capacity)
        derived_power_capacity = self.new_capacity * self.inv_hours_storage
        power_capital = cp.sum(self.cost_fun_params["power_sizing_constant"] @ derived_power_capacity)
        self.cost = storage_capital + power_capital
        return
 
    def _compute_annuity_matrix(self, sizing_constant_vec):
        """Same NPV-annuity computation as
        Stock_Asset_STEVFNs._update_sizing_constant, factored out so it
        can be reused for both the storage and power cost streams."""
        self._get_lifetime_periods()
        asset_lifetime = self._asset_lifetime
        interest_rate = float(self.parameters_df["interest_rate"])
        discount_rate = float(self.network.system_parameters_df.loc["discount_rate", "value"])
 
        amort_factor = (interest_rate * (1 + interest_rate) ** asset_lifetime) / \
                        ((1 + interest_rate) ** asset_lifetime - 1)
        annual_payment_vec = sizing_constant_vec * amort_factor
 
        period_start_years = self.period_start_years
        period_years = np.array([self._years_in_period(p) for p in range(self.num_periods)])
        period_end_years = period_start_years + period_years
 
        M = np.zeros((self.num_periods, self.num_periods))
        for k in range(self.num_periods):
            install_year = period_start_years[k]
            payoff_year = install_year + asset_lifetime
            for p in range(self.num_periods):
                y_start = max(period_start_years[p], install_year)
                y_end = min(period_end_years[p], payoff_year)
                if y_end <= y_start:
                    continue
                years_in_window = np.arange(int(round(y_start)), int(round(y_end)))
                if years_in_window.size == 0:
                    continue
                discount_factors = (1 + discount_rate) ** (-years_in_window.astype(float))
                M[p, k] = annual_payment_vec[k] * discount_factors.sum()
        return M
 
    def _load_parameters_df(self, parameters_df):
        """PHS_Asset passes the shared PHS parameters row directly (not
        an asset_type index)."""
        self.parameters_df = parameters_df
        return
 
    def _update_parameters(self):
        self.inv_hours_storage.value = 1.0 / float(self.parameters_df["hours_storage"])
 
        storage_vec = np.full(self.num_periods, float(self.parameters_df["storage_sizing_constant"]))
        self.cost_fun_params["sizing_constant"].value = self._compute_annuity_matrix(storage_vec)
 
        power_vec = np.full(self.num_periods, float(self.parameters_df["power_sizing_constant"]))
        self.cost_fun_params["power_sizing_constant"].value = self._compute_annuity_matrix(power_vec)
 
        self._update_new_capacity_decom_mask()
        self._update_existing_capacity_vec()
        return
 
    def get_hourly_flows(self):
        return self.flows.value
 
    def get_period_flows(self):
        flows_full = np.array(self.get_hourly_flows())
        return [flows_full[start:end]
                for start, end in zip(self.period_boundaries[:-1], self.period_boundaries[1:])]
 
    def get_period_costs(self):
        """Overrides Stock_Asset_STEVFNs.get_period_costs -- capital cost
        here is the SUM of two amortised streams (storage + power), not
        one, and there's no usage term."""
        M_storage = self.cost_fun_params["sizing_constant"].value
        M_power = self.cost_fun_params["power_sizing_constant"].value
        new_capacity = self.new_capacity.value
        if M_storage is None or M_power is None or new_capacity is None:
            return None
 
        new_capacity = np.array(new_capacity)
        period_storage_capital = np.array(M_storage) @ new_capacity
        derived_power_capacity = new_capacity / float(self.parameters_df["hours_storage"])
        period_power_capital = np.array(M_power) @ derived_power_capacity
 
        period_total = period_storage_capital + period_power_capital
        return np.array([period_total[p] / self._years_in_period(p) for p in range(self.num_periods)])
 
    def get_asset_sizes(self):
        asset_identity = self.asset_name + r"_location_" + str(self.source_node_location)
        return {asset_identity: self.size()}
 
 
class _PHS_Flow_Component(Asset_STEVFNs):
    """
    Shared scaffolding for Pumping_Asset / Turbine_Asset: hourly flow
    Variable, capacity-limit and ramp edges against the Reservoir's
    derived power capacity, and usage cost against the single shared
    usage_constant column. No capital cost, no capacity variable.
    """
    period = 1
    transport_time = 0
 
    capacity_node_type = "NULL"
    ramp_node_type_pos = "NULL"
    ramp_node_type_neg = "NULL"
 
    def _base_define_structure(self, asset_structure, reservoir):
        self.reservoir = reservoir
        self.asset_structure = asset_structure
        self.source_node_location = asset_structure["Location_1"]
        self.source_node_times = np.arange(asset_structure["Start_Time"] + self.transport_time,
                                            asset_structure["End_Time"] + self.transport_time,
                                            self.period)
        self.target_node_location = self.source_node_location
        self.target_node_times = np.arange(asset_structure["Start_Time"] + self.transport_time,
                                            asset_structure["End_Time"] + self.transport_time,
                                            self.period)
        self.number_of_edges = len(self.source_node_times)
 
        self._compute_period_counts()
        self.period_change_indices = self._get_period_change_indices()
        self.period_boundaries = self.period_change_indices + [self.number_of_edges]
 
        self.flows = cp.Variable(self.number_of_edges, nonneg=True, name=f"flows_{self.asset_name}")
        self.cost_fun_params = {
            "usage_constant": cp.Parameter(self.number_of_edges, nonneg=True,
                                            name=f"usage_cost_{self.asset_name}")}
        return
 
    def _build_capacity_limit_edges(self):
        """Caps hourly flow within each period at the reservoir's
        derived power capacity for that period."""
        for p in range(self.num_periods):
            start, end = self.period_boundaries[p], self.period_boundaries[p + 1]
            period_flows = self.flows[start:end]
 
            edge = Edge_STEVFNs()
            self.edges.append(edge)
            edge.attach_target_node(self.network.extract_node(
                self.target_node_location, self.capacity_node_type, p))
            edge.flow = self.reservoir.power_capacity(p) - cp.max(period_flows)
        return
 
    def _build_ramp_edges(self):
        """Ramp cap = derived power capacity[p] * inv_hours_storage --
        i.e. the plant can swing its full derived capacity within
        hours_storage hours. No independent ramp_rate parameter."""
        for t in range(self.number_of_edges - 1):
            p = self._period_index_for_edge(t + 1)
            ramp_cap = self.reservoir.power_capacity(p) * self.reservoir.inv_hours_storage
 
            pos_edge = Edge_STEVFNs()
            self.edges += [pos_edge]
            pos_edge.attach_target_node(self.network.extract_node(
                self.target_node_location, self.ramp_node_type_pos, self.target_node_times[t + 1]))
            pos_edge.flow = ramp_cap - (self.flows[t + 1] - self.flows[t])
 
            neg_edge = Edge_STEVFNs()
            self.edges += [neg_edge]
            neg_edge.attach_target_node(self.network.extract_node(
                self.target_node_location, self.ramp_node_type_neg, self.target_node_times[t + 1]))
            neg_edge.flow = ramp_cap - (self.flows[t] - self.flows[t + 1])
 
        if self.number_of_edges >= 2:
            t = self.number_of_edges - 1
            p = self._period_index_for_edge(0)
            ramp_cap = self.reservoir.power_capacity(p) * self.reservoir.inv_hours_storage
 
            pos_edge = Edge_STEVFNs()
            self.edges += [pos_edge]
            pos_edge.attach_target_node(self.network.extract_node(
                self.target_node_location, self.ramp_node_type_pos, self.target_node_times[0]))
            pos_edge.flow = ramp_cap - (self.flows[0] - self.flows[t])
 
            neg_edge = Edge_STEVFNs()
            self.edges += [neg_edge]
            neg_edge.attach_target_node(self.network.extract_node(
                self.target_node_location, self.ramp_node_type_neg, self.target_node_times[0]))
            neg_edge.flow = ramp_cap - (self.flows[t] - self.flows[0])
        return
 
    def build_cost(self):
        self.cost = cp.sum(cp.multiply(self.cost_fun_params["usage_constant"], self.flows))
        return
 
    def _update_usage_constant(self):
        """NPV discounted and expand to hourly cost profile"""
        sampled_days = int((self.number_of_edges / 24) / self.num_years)
        simulation_factor = 365 / sampled_days
        discount_rate = self.network.system_parameters_df.loc["discount_rate", "value"]
 
        raw_cost = float(self.parameters_df["usage_constant"])
        discount_factors = (1 / (1 + discount_rate)) ** np.arange(self.num_years)
        yearly_costs = raw_cost * discount_factors * simulation_factor
 
        year_indices = self._get_year_change_indices() + [self.number_of_edges]
        expanded_costs = np.zeros(self.number_of_edges)
        for i, (start, end) in enumerate(zip(year_indices[:-1], year_indices[1:])):
            expanded_costs[start:end] = yearly_costs[i]
 
        self.cost_fun_params["usage_constant"].value = expanded_costs
        return
 
    def _load_parameters_df(self, parameters_df):
        self.parameters_df = parameters_df
        return
 
    def get_hourly_flows(self):
        return self.flows.value
 
    def get_period_flows(self):
        flows_full = np.array(self.get_hourly_flows())
        return [flows_full[start:end]
                for start, end in zip(self.period_boundaries[:-1], self.period_boundaries[1:])]
 
    def get_period_costs(self):
        """Per-period annualised usage cost"""
        usage_vals = self.cost_fun_params["usage_constant"].value
        flow_vals = self.flows.value
        if usage_vals is None or flow_vals is None:
            return None
        period_usage = np.zeros(self.num_periods)
        for p, (start, end) in enumerate(zip(self.period_boundaries[:-1], self.period_boundaries[1:])):
            period_usage[p] = np.sum(usage_vals[start:end] * flow_vals[start:end])
        return np.array([period_usage[p] / self._years_in_period(p) for p in range(self.num_periods)])
 
    def get_period_capacity(self):
        """Derived power capacity (GW) available per period."""
        operating_energy = self.reservoir.get_operating_stock()
        if operating_energy is None:
            return None
        return operating_energy / float(self.parameters_df["hours_storage"])
 
    def get_asset_sizes(self):
        asset_identity = self.asset_name + r"_location_" + str(self.source_node_location)
        operating_energy = self.reservoir.get_operating_stock()
        size = None if operating_energy is None else operating_energy / float(self.parameters_df["hours_storage"])
        return {asset_identity: size}
 
 
class Pumping_Asset(_PHS_Flow_Component):
    """Edges from Grid -> Reservoir. Power capacity derived from the Reservoir optimised size."""
    asset_name = "Pumping"
    source_node_type = "EL"
    target_node_type = "PHS"
    ramp_node_type_pos = "Ramp_pump_pos"
    ramp_node_type_neg = "Ramp_pump_neg"
    capacity_node_type = "Pump_Capacity"
 
    @staticmethod
    def conversion_fun(flows, params):
        pumping_efficiency = params["pumping_conversion_eff"]
        return flows * pumping_efficiency
 
    def __init__(self):
        super().__init__()
        self.conversion_fun_params = {
            "pumping_conversion_eff": cp.Parameter(nonneg=True,
                                                     name=f"pumping_conv_efficiency_{self.asset_name}")}
        return
 
    def define_structure(self, asset_structure, reservoir):
        self._base_define_structure(asset_structure, reservoir)
        return
 
    def build_edges(self):
        self.edges = []
        for edge_number in range(self.number_of_edges):
            self.build_edge(edge_number)
        self._build_ramp_edges()
        self._build_capacity_limit_edges()
        return
 
    def _update_parameters(self):
        for parameter_name, parameter in self.conversion_fun_params.items():
            parameter.value = self.parameters_df[parameter_name]
        self._update_usage_constant()
        return
 
class Turbine_Asset(_PHS_Flow_Component):
    """Edges from Reservoir -> Grid. Power capacity derived from the Reservoir optimised size."""
    asset_name = "Turbine"
    source_node_type = "PHS"
    target_node_type = "EL"
    ramp_node_type_pos = "Ramp_turb_pos"
    ramp_node_type_neg = "Ramp_turb_neg"
    capacity_node_type = "Turbine_Capacity"
 
    @staticmethod
    def conversion_fun(flows, params):
        turbine_efficiency = params["turbine_conversion_eff"]
        return flows * turbine_efficiency
 
    def __init__(self):
        super().__init__()
        self.conversion_fun_params = {
            "turbine_conversion_eff": cp.Parameter(nonneg=True,
                                                     name=f"turbine_conv_efficiency_{self.asset_name}")}
        return
 
    def define_structure(self, asset_structure, reservoir):
        self._base_define_structure(asset_structure, reservoir)
        return
 
    def build_edges(self):
        self.edges = []
        for edge_number in range(self.number_of_edges):
            self.build_edge(edge_number)
        self._build_ramp_edges()
        self._build_capacity_limit_edges()
        return
 
    def _update_parameters(self):
        for parameter_name, parameter in self.conversion_fun_params.items():
            parameter.value = self.parameters_df[parameter_name]
        self._update_usage_constant()
        return
 
class PHS_Asset(Multi_Asset):
    """Country-level PHS multi-asset. Reservoir owns the sole capacity
    stock and all capital cost; Pumping/Turbine contribute only usage
    cost on their own flows, capped at the Reservoir's derived power
    capacity. Reservoir is built first so Pumping/Turbine can hold a
    live reference to it."""
    asset_name = "PHS"
    assets_class_dictionary = {
        "Reservoir": Reservoir_Asset,
        "Pumping": Pumping_Asset,
        "Turbine": Turbine_Asset,
    }
 
    @staticmethod
    def cost_fun(costs_dictionary, cost_fun_params):
        return sum(costs_dictionary.values())
 
    def define_structure(self, asset_structure):
        self.asset_structure = asset_structure
        self._define_asset_structures()
        self.target_node_location = self.assets_dictionary["Reservoir"].target_node_location
        return
 
    def _define_asset_structures(self):
        reservoir = self.assets_dictionary["Reservoir"]
        reservoir.network = self.network
        reservoir.define_structure(self.asset_structure)
 
        for name in ("Pumping", "Turbine"):
            asset = self.assets_dictionary[name]
            asset.network = self.network
            asset.define_structure(self.asset_structure, reservoir)
        return
 
    def _update_assets(self):
        for asset_name, asset in self.assets_dictionary.items():
            asset.update(self.parameters_df)
        return
 
    def asset_size(self):
        """Reservoir's period-indexed built energy capacity (GWh) -- the
        single headline size metric for the whole PHS system."""
        return self.assets_dictionary["Reservoir"].new_capacity.value
 
    def get_period_costs(self):
        """Sum of Reservoir's (storage + power) capital cost and
        Pumping/Turbine's usage costs."""
        component_costs = [asset.get_period_costs() for asset in self.assets_dictionary.values()]
        if any(c is None for c in component_costs):
            return None
        return np.sum(component_costs, axis=0)
 
    def get_period_capacity(self):
        """Reservoir energy capacity (GWh) per period, as PHS's headline
        capacity metric. (Pumping/Turbine's derived GW capacity is also
        available via their own get_period_capacity() if preferred.)"""
        return self.assets_dictionary["Reservoir"].get_new_capacity()
 
    def get_asset_sizes(self):
        asset_identity = self.asset_name + r"_location_" + str(self.target_node_location)
        return {asset_identity: self.asset_size()}
 