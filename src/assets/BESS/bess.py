#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import numpy as np
import cvxpy as cp
from ..Base_Stock_Assets import Stock_Asset_STEVFNs
from ...network import Edge_STEVFNs


class BESS_Asset(Stock_Asset_STEVFNs):
    """
    Time-dependent Battery Energy Storage System (BESS), 1-hour duration
    (power rating == peak charge/discharge capacity)
    Decommissioning at lifetime, ignoring degradation component
    """

    asset_name = "BESS"
    source_node_type = "NULL"
    target_node_type = "NULL"
    stock_node_type = "BESS_Stock"
    capacity_unit = "GWh" # 1h duration (storage == peak charge/discharge capacity)

    decommission_mode = "decay_rate" # for pre existing capacity before optimisation
    period = 1
    transport_time = 0

    def define_structure(self, asset_structure):
        self.asset_structure = asset_structure
        self.el_node_location = asset_structure["Location_1"]
        self.stock_node_location = asset_structure["Location_1"]

        # base-class bookkeeping expects these
        # Needed for result extraction pipeline
        self.source_node_location = asset_structure["Location_1"]
        self.target_node_location = asset_structure["Location_1"]

        self.hourly_times = np.arange(asset_structure["Start_Time"],
                                       asset_structure["End_Time"], self.period)
        self.number_of_edges = len(self.hourly_times)

        self._define_period_structure(asset_structure)  # new_capacity, carryover_out, decom_mask, etc.
        self.period_change_indices = self._get_period_change_indices()
        self.period_boundaries = self.period_change_indices + [self.number_of_edges]

        self.charge_flow = cp.Variable(self.number_of_edges, nonneg=True,
                                        name=f"charge_{self.asset_name}")
        self.discharge_flow = cp.Variable(self.number_of_edges, nonneg=True,
                                           name=f"discharge_{self.asset_name}")
        self.soc = cp.Variable(self.number_of_edges, nonneg=True,
                                name=f"soc_{self.asset_name}")

        # combined throughput: only used for the shared usage-cost term
        self.flows = self.charge_flow + self.discharge_flow

        self.cost_fun_params = {
            "sizing_constant": cp.Parameter(shape=(self.num_periods, self.num_periods),
                                             nonneg=True, name=f"sizing_constant_{self.asset_name}"),
            "usage_constant": cp.Parameter(self.number_of_edges, nonneg=True,
                                            name=f"usage_constant_{self.asset_name}"),
            "terminal_charge": cp.Parameter(shape=(self.num_periods,), nonneg=True,   # limit end of project install bias
                                            name=f"terminal_charge_{self.asset_name}"),
        }
        self.conversion_fun_params = {
            "charge_efficiency": cp.Parameter(nonneg=True, name=f"charge_eff_{self.asset_name}"),
            "discharge_efficiency": cp.Parameter(nonneg=True, name=f"discharge_eff_{self.asset_name}"),
        }
        # per-edge retention = (1 - self_discharge_rate) ** gap_hours[t], one entry
        # per SOC continuity edge (number_of_edges - 1 of them, see _build_soc_edges)
        self.soc_retention = cp.Parameter(self.number_of_edges - 1, nonneg=True,
                                           name=f"soc_retention_{self.asset_name}")

        self._compute_soc_gap_hours()
        return

    def _compute_soc_gap_hours(self):
        """Real-hour distance represented by each SOC continuity edge:
        1 for a true intra-representative-day hour-to-hour step, and the
        full representative-day spacing for the step that jumps from the
        last modelled hour of one representative day to the first hour of
        the next"""
        hours_per_day = 24
        hours_per_year = 8760
        days_per_year = int((self.number_of_edges / hours_per_day) / self.num_years)
        day_spacing_hours = hours_per_year / days_per_year  # real hours between sampled-day starts

        gap_hours = np.ones(self.number_of_edges)
        for t in range(self.number_of_edges):
            if (t + 1) % hours_per_day == 0:  # last modelled hour of a representative day
                gap_hours[t] = day_spacing_hours - hours_per_day + 1
        self.soc_gap_hours = gap_hours
        return

    def build_edges(self):
        self.edges = []
        self._build_dispatch_edges()
        self._build_soc_edges()
        self._build_soc_feasibility_edges()
        self._build_stock_edges()
        self._build_capacity_limit_edges()
        return

    def _build_dispatch_edges(self):
        self._charge_edges, self._discharge_edges = [], []
        for t in range(self.number_of_edges):
            time = self.hourly_times[t]
            soc_node = self.network.extract_node(self.stock_node_location, "BESS_SOC", time)
            soc_node.curtailment = False  # equality constraint at node

            charge_edge = Edge_STEVFNs()
            self.edges.append(charge_edge)
            self._charge_edges.append(charge_edge)
            charge_edge.attach_source_node(self.network.extract_node(
                self.el_node_location, "EL", time))
            charge_edge.attach_target_node(soc_node)
            charge_edge.flow = self.conversion_fun_params["charge_efficiency"] * self.charge_flow[t]

            discharge_edge = Edge_STEVFNs()
            self.edges.append(discharge_edge)
            self._discharge_edges.append(discharge_edge)
            discharge_edge.attach_source_node(soc_node)
            discharge_edge.attach_target_node(self.network.extract_node(
                self.el_node_location, "EL", time))
            discharge_edge.flow = self.discharge_flow[t] / self.conversion_fun_params["discharge_efficiency"]
        return

    def _build_soc_edges(self):
        """State-of-charge continuity, BESS_SOC(t) -> BESS_SOC(t+1),
        gap-scaled at representative-day boundaries.

        Destination nodes of a gap edge (gap > 1) have curtailment
        overridden back to True (it defaults False for every hourly SOC
        node in _build_dispatch_edges, for the normal equality balance),
        so excess input above what the standard capacity-limit edge
        allows is simply discarded -- this is what implements the 100%
        SOC clip."""
        self._soc_edges = []
        self._jump_edge_indices = []
        charge_eff = self.conversion_fun_params["charge_efficiency"]
        discharge_eff = self.conversion_fun_params["discharge_efficiency"]
        self._net_rate = charge_eff * self.charge_flow - self.discharge_flow / discharge_eff

        for t in range(self.number_of_edges - 1):
            gap = self.soc_gap_hours[t]

            edge = Edge_STEVFNs()
            self.edges.append(edge)
            self._soc_edges.append(edge)
            edge.attach_source_node(self.network.extract_node(
                self.stock_node_location, "BESS_SOC", self.hourly_times[t]))
            edge.attach_target_node(self.network.extract_node(
                self.stock_node_location, "BESS_SOC", self.hourly_times[t + 1]))
            if gap <= 1.0:
                edge.flow = self.soc_retention[t] * self.soc[t] # self.soc[t] cp.Variable for soc balance
            else:
                # Limit soc to 100% of soc capacity ("curtail" additional "charge" from linear
                # extrapolation between time gap jumps)
                edge.target_node.curtailment = True
                edge.flow = self.soc_retention[t] * self.soc[t] + self._net_rate[t] * (gap - 1)
                self._jump_edge_indices.append(t)
        return

    def _build_soc_feasibility_edges(self):
        """Lower-bound (0% SOC) limit for the gap-jump edges: stops the
        model from ever choosing boundary-hour dispatch whose linear
        extrapolation would imply the battery running past empty during
        the skipped days."""
        for t in self._jump_edge_indices:
            gap = self.soc_gap_hours[t]
            edge = Edge_STEVFNs()
            self.edges.append(edge)
            edge.attach_target_node(self.network.extract_node(
                self.stock_node_location, "BESS_Jump_Feasibility", t)) # new node type
            edge.flow = self.soc_retention[t] * self.soc[t] + self._net_rate[t] * (gap - 1)
        return

    def _build_capacity_limit_edges(self):
        """Period-level capacity caps: soc not allowed to exceed installed bess capacity
           capped at carryover_out[p]."""
        for p in range(self.num_periods):
            start, end = self.period_boundaries[p], self.period_boundaries[p + 1]
            series = self.soc
            node_type = "BESS_SOC_Capacity"
            edge = Edge_STEVFNs()
            self.edges.append(edge)
            edge.attach_target_node(self.network.extract_node(
                self.stock_node_location, node_type, p))
            edge.flow = self.carryover_out[p] - cp.max(series[start:end])
        return

    def _update_usage_constant(self):
        sampled_days = int((self.number_of_edges / 24) / self.num_years)
        simulation_factor = 365 / sampled_days
        discount_rate = self.network.system_parameters_df.loc["discount_rate", "value"]

        raw_cost = float(self.parameters_df["usage_constant"])  # $/unit throughput (charge+discharge)
        discount_factors = (1 / (1 + discount_rate)) ** np.arange(self.num_years)
        yearly_costs = raw_cost * discount_factors * simulation_factor

        year_indices = self._get_year_change_indices() + [self.number_of_edges]
        expanded_costs = np.zeros(self.number_of_edges)
        for i, (start, end) in enumerate(zip(year_indices[:-1], year_indices[1:])):
            expanded_costs[start:end] = yearly_costs[i]

        self.cost_fun_params["usage_constant"].value = expanded_costs
        return

    def _load_baseline_capex(self):
        """Scalar baseline capex ($/unit capacity), broadcast into a
        per-period vector so it flows through the same
        _update_sizing_constant() amortisation/NPV pipeline as base stock asset."""

        baseline_capex = float(self.parameters_df["sizing_constant"])
        return np.full(self.num_periods, baseline_capex)

    def _update_soc_retention(self):
        self_discharge_rate = float(self.parameters_df["self_discharge_rate"])
        hourly_retention = 1.0 - self_discharge_rate
        gaps = self.soc_gap_hours[:self.number_of_edges - 1]  # one gap per continuity edge
        self.soc_retention.value = hourly_retention ** gaps
        return

    def _update_parameters(self):
        self.conversion_fun_params["charge_efficiency"].value = float(self.parameters_df["charge_efficiency"])
        self.conversion_fun_params["discharge_efficiency"].value = float(self.parameters_df["discharge_efficiency"])
        self._update_soc_retention()
        self._update_usage_constant()

        sizing_constant_vec = self._load_baseline_capex()
        self._get_lifetime_periods()
        self._update_sizing_constant(sizing_constant_vec)
        self._update_decommission_mask()
        self._update_existing_capacity_vec()
        return

    def _update_decommission_mask(self):
        self._update_new_capacity_decom_mask()
        return

    # --- Result extraction ---

    def get_hourly_flows(self):
        return {
            "charge": self.charge_flow.value,
            "discharge": self.discharge_flow.value,
            "soc": self.soc.value,
        }

    def get_period_flows(self):
        all_flows = self.get_hourly_flows()
        # script method to get period flows for plotting and internal review 
        return

    def get_period_capacity(self):
        return None if self.carryover_out.value is None else np.array(self.carryover_out.value)

    def get_asset_sizes(self):
        asset_identity = self.asset_name + r"_location_" + str(self.stock_node_location)
        return {asset_identity: self.size()}