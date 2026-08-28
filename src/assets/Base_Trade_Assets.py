#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import numpy as np
import cvxpy as cp
from .Base_Stock_Assets import Stock_Asset_STEVFNs
from ..network import Edge_STEVFNs

class Trade_Stock_Asset_STEVFNs(Stock_Asset_STEVFNs):
    """Base class for delayed-availability trade assets.
    Inherited by NH3_Transport, H2_Transport and EL_Transport asset
    To vary parameter value per trade technology class"""

    asset_name = "Trade_Stock_Asset_STEVFNs"
    source_node_type = "NULL"
    target_node_type = "NULL"
    decommission_mode = "decay_rate"
    capacity_unit = "GW"
    # Subclasses may hardcode a delay instead of reading from parameters.csv:
    construction_delay_years = None

    def define_structure(self, asset_structure):
        self.asset_structure = asset_structure
        self.source_node_location = asset_structure["Location_1"]
        self.target_node_location = asset_structure["Location_2"]

        self.sampled_hourly_timesteps = np.arange(asset_structure["Start_Time"],
                                            asset_structure["End_Time"],
                                            1) # For sampled days calculation in update usage constant
        self.source_node_times = np.arange(asset_structure["Start_Time"],
                                            asset_structure["End_Time"],
                                            asset_structure["Period"])
        self.target_node_times = (self.source_node_times + asset_structure["Transport_Time"]) \
            % asset_structure["End_Time"]
        self.number_of_edges = len(self.source_node_times)
        self.hourly_sample_full = len(self.sampled_hourly_timesteps) # Sampled hourly edges

        # per-route-unique node types so two routes sharing a source/target
        # location don't accidentally pool their capacity stock
        self.stock_node_location = self.source_node_location # Keeping stock node location to source loc in trade config
        self.stock_node_type = f"{self.asset_name}_Stock_from_{self.source_node_location}_to_{self.target_node_location}"
        self.capacity_node_location = self.source_node_location # Keeping capacity node location to source loc in trade config
        self.capacity_node_type = f"{self.asset_name}_Capacity_from_{self.source_node_location}_to_{self.target_node_location}"

        self._define_period_structure(asset_structure)
        self.period_change_indices = self._get_period_change_indices()
        self.period_boundaries = self.period_change_indices + [self.number_of_edges]

        # bidirectional hourly dispatch: [0:N) forward, [N:2N) reverse
        self.flows = cp.Variable(self.number_of_edges * 2, nonneg=True,
                                  name=f"flows_{self.asset_name}")
        self.cost_fun_params["usage_constant"] = cp.Parameter(self.number_of_edges * 2, nonneg=True,
                                                                name=f"usage_constant_{self.asset_name}")
        self.conversion_fun_params = {"conversion_factor": cp.Parameter(nonneg=True,
                                                                          name=f"conversion_factor_{self.asset_name}")}
        self.delay_periods = 0  # resolved numerically each scenario update via _update_delay_periods
        return

    def _update_delay_periods(self):
        delay_years = self.construction_delay_years
        if delay_years is None:
            delay_years = float(self.parameters_df["construction_delay"])  # years
        self.delay_periods = int(np.ceil(delay_years / self.reinvestment_period)) if delay_years > 0 else 0
        return

    def build_edges(self):
        self.edges = []
        for edge_number in range(self.number_of_edges):
            self.build_edge(edge_number)
            self.build_edge_opposite(edge_number)
        self._build_stock_edges()
        self._build_capacity_limit_edges()
        return

    def build_edge(self, edge_number):
        source_node_time = self.source_node_times[edge_number]
        target_node_time = self.target_node_times[edge_number]
        new_edge = Edge_STEVFNs()
        self.edges.append(new_edge)
        new_edge.attach_source_node(self.network.extract_node(
            self.source_node_location, self.source_node_type, source_node_time))
        new_edge.attach_target_node(self.network.extract_node(
            self.target_node_location, self.target_node_type, target_node_time))
        new_edge.flow = self.flows[edge_number]
        new_edge.conversion_fun = self.conversion_fun
        new_edge.conversion_fun_params = self.conversion_fun_params
        return

    def build_edge_opposite(self, edge_number):
        source_node_time = self.source_node_times[edge_number]
        target_node_time = self.target_node_times[edge_number]
        new_edge = Edge_STEVFNs()
        self.edges.append(new_edge)
        new_edge.attach_source_node(self.network.extract_node(
            self.target_node_location, self.target_node_type, source_node_time))
        new_edge.attach_target_node(self.network.extract_node(
            self.source_node_location, self.source_node_type, target_node_time))
        new_edge.flow = self.flows[self.number_of_edges + edge_number]
        new_edge.conversion_fun = self.conversion_fun
        new_edge.conversion_fun_params = self.conversion_fun_params
        return

    def _build_stock_edges(self):
        """Same accounting as Stock_Asset_STEVFNs, except a cohort invested in
        period k lands in the stock node at period k + delay_periods
        If this falls beyond model horizon, dropped"""
        decommission_out = self.decom_mask_param @ self.new_capacity

        for p in range(self.num_periods):
            stock_node = self.network.extract_node(self.stock_node_location,
                                                     self.stock_node_type, p)
            stock_node.curtailment = False

            decom_edge = Edge_STEVFNs()
            self.edges.append(decom_edge)
            decom_edge.attach_source_node(stock_node)
            decom_edge.flow = decommission_out[p]

            existing_edge = Edge_STEVFNs()
            self.edges.append(existing_edge)
            existing_edge.attach_target_node(stock_node)
            existing_edge.flow = self.existing_capacity_vec[p]

            if p > 0:
                prev_stock_node = self.network.extract_node(self.stock_node_location,
                                                              self.stock_node_type, p - 1)
                carry_in_edge = Edge_STEVFNs()
                self.edges.append(carry_in_edge)
                carry_in_edge.attach_source_node(prev_stock_node)
                carry_in_edge.attach_target_node(stock_node)
                carry_in_edge.flow = self.carryover_out[p - 1]

            if p == self.num_periods - 1:
                carry_out_edge = Edge_STEVFNs()
                self.edges.append(carry_out_edge)
                carry_out_edge.attach_source_node(stock_node)
                carry_out_edge.flow = self.carryover_out[p]

            # delayed install: cohort decided in period k starts operating at k + delay_periods == p
            k = p - self.delay_periods
            if 0 <= k < self.num_periods:
                install_edge = Edge_STEVFNs()
                self.edges.append(install_edge)
                install_edge.attach_target_node(stock_node)
                install_edge.flow = self.new_capacity[k]
        return

    def _build_capacity_limit_edges(self):
        """Caps both directions' hourly dispatch within each period at that
        period's available stock (carryover_out[p])"""
        n = self.number_of_edges # sampled hours in one direction, to index reverse flows
        for p in range(self.num_periods):
            start, end = self.period_boundaries[p], self.period_boundaries[p + 1]
            fwd = self.flows[start:end]
            rev = self.flows[n + start:n + end]
            period_flows = cp.hstack([fwd, rev])

            edge = Edge_STEVFNs()
            self.edges.append(edge)
            edge.attach_target_node(self.network.extract_node(
                self.capacity_node_location, self.capacity_node_type, p))
            edge.flow = self.carryover_out[p] - cp.max(period_flows)
        return

    def _get_period_change_indices(self):
        """Overrides Base_Assets' days-per-year approximation, which
        computes hours_per_period as
            int(number_of_edges / 24 / num_years) * 24 * reinvestment_period
        -- integer-truncates to 0 whenever this asset's sampled hourly
        count works out to LESS THAN ONE representative day per year, which
        collapses every period boundary to 0 and leaves every period but
        the last with zero hourly timesteps. That's silent for most code
        paths but fatal for _build_capacity_limit_edges' cp.max(), which
        can't reduce an empty array (the crash you hit).

        This instead splits number_of_edges into num_periods proportional,
        contiguous chunks directly -- no days/year assumption, so it can't
        produce an empty period as long as number_of_edges >= num_periods.
        """
        if self.number_of_edges < self.num_periods:
            raise ValueError(
                f"{self.asset_name} ({self.source_node_location}->{self.target_node_location}): "
                f"number_of_edges ({self.number_of_edges}) < num_periods ({self.num_periods}) -- "
                f"every reinvestment period needs at least one sampled hourly timestep "
                f"for the capacity-limit edge's cp.max() to be well-defined. Increase the "
                f"sampled timesteps for this asset or coarsen reinvestment_period."
            )
        edges_per_period = self.number_of_edges / self.num_periods
        self.period_change_indices = [int(round(p * edges_per_period)) for p in range(self.num_periods)]
        return self.period_change_indices
    
    def _update_new_capacity_decom_mask(self):
        """Decommission after start of operation, not at investment"""
        asset_lifetime = getattr(self, "_asset_lifetime", None) or float(self.parameters_df["lifespan"] / 8760)
        lifetime_periods = max(int(round(asset_lifetime / self.reinvestment_period)), 1)
        decom_mask = np.zeros((self.num_periods, self.num_periods))
        for p in range(self.num_periods):
            k = p - lifetime_periods - self.delay_periods
            if 0 <= k < self.num_periods:
                decom_mask[p, k] = 1
        self.decom_mask_param.value = decom_mask
        return

    def _update_distance(self):
        """Estimate distance between two coordinates to be linked
        Assumption "as-the-bird-flies"""
        lat_lon_0 = self.network.lat_lon_df.iloc[int(self.source_node_location)]
        lat_lon_1 = self.network.lat_lon_df.iloc[int(self.target_node_location)]
        lat_0 = lat_lon_0["lat"] / 180 * np.pi
        lat_1 = lat_lon_1["lat"] / 180 * np.pi
        lon_d = (lat_lon_1["lon"] - lat_lon_0["lon"]) / 180 * np.pi
        a = np.sin((lat_1 - lat_0) / 2) ** 2 + np.cos(lat_0) * np.cos(lat_1) * np.sin(lon_d / 2) ** 2
        c = 2 * np.arctan2(a ** 0.5, (1 - a) ** 0.5)
        R = 6.371  # Mm, earth radius
        self.distance = R * c
        return

    def _update_usage_constant(self):
        """Distance-scaled $/unit-flow cost, expanded to an hourly vector
        (both directions), NPV-discounted per simulated year -- mirrors
        PP_CO2's _update_usage_constant but keeps the distance term."""
        sampled_days = int((self.hourly_sample_full / 24) / self.num_years)
        simulation_factor = 365 / sampled_days
        discount_rate = float(self.network.system_parameters_df.loc["discount_rate", "value"])

        raw_cost = (float(self.parameters_df["usage_constant_1"]) +
                    float(self.parameters_df["usage_constant_2"]) * self.distance)
    
        discount_factors = (1 / (1 + discount_rate)) ** np.arange(self.num_years)
        yearly_costs = raw_cost * discount_factors * simulation_factor

        year_indices = self._get_year_change_indices() + [self.number_of_edges]
        expanded = np.zeros(self.number_of_edges)
        for i, (start, end) in enumerate(zip(year_indices[:-1], year_indices[1:])):
            expanded[start:end] = yearly_costs[i]

        self.cost_fun_params["usage_constant"].value = np.concatenate([expanded, expanded])
        return

    def _load_baseline_capex(self):
        """Scalar distance-scaled baseline capex, broadcast to a per-period
        vector so it can go through the shared NPV amortisation pipeline."""
        baseline_capex = (float(self.parameters_df["sizing_constant_1"]) +
                           float(self.parameters_df["sizing_constant_2"]) * self.distance)
        return np.full(self.num_periods, baseline_capex)

    def _update_parameters(self):
        self._update_distance()
        self._update_delay_periods()
        conversion_factor = 1 - (float(self.parameters_df["conversion_factor_1"]) +
                                  float(self.parameters_df["conversion_factor_2"]) * self.distance)
        self.conversion_fun_params["conversion_factor"].value = conversion_factor
        self._update_usage_constant()
        sizing_constant_vec = self._load_baseline_capex()
        self._get_lifetime_periods()
        self._update_sizing_constant(sizing_constant_vec)
        self._update_new_capacity_decom_mask()
        self._update_existing_capacity_vec()
        return

    @staticmethod
    def conversion_fun(flows, params):
        conversion_factor = params["conversion_factor"]
        return conversion_factor * flows
    
    def get_hourly_flows(self):
        return np.array(self.flows.value)

    def get_period_flows(self):
        flows_full = self.get_hourly_flows()
        n = self.number_of_edges
        fwd, rev = flows_full[:n], flows_full[n:]
        idx = self.period_boundaries
        return [(fwd[s:e], rev[s:e]) for s, e in zip(idx[:-1], idx[1:])]

    def get_period_costs(self):
        """Overrides Stock_Asset_STEVFNs.get_period_costs to sum usage cost
        over both direction halves of self.flows per period."""
        M = self.cost_fun_params["sizing_constant"].value
        new_capacity = self.new_capacity.value
        if M is None or new_capacity is None:
            return None
        period_capital = np.array(M) @ np.array(new_capacity)

        usage_param = self.cost_fun_params.get("usage_constant")
        period_usage = np.zeros(self.num_periods)
        if usage_param is not None and getattr(usage_param, "value", None) is not None \
                and self.flows.value is not None:
            usage_vals = np.array(usage_param.value)
            flow_vals = np.array(self.flows.value)
            n = self.number_of_edges
            for p, (start, end) in enumerate(zip(self.period_boundaries[:-1], self.period_boundaries[1:])):
                fwd_cost = np.sum(usage_vals[start:end] * flow_vals[start:end])
                rev_cost = np.sum(usage_vals[n + start:n + end] * flow_vals[n + start:n + end])
                period_usage[p] = fwd_cost + rev_cost

        period_total = period_capital + period_usage
        return np.array([period_total[p] / self._years_in_period(p) for p in range(self.num_periods)])

    def get_period_capacity(self):
        return self.get_operating_stock()

    def get_asset_sizes(self):
        asset_identity = (self.asset_name + r"_" + str(self.source_node_location) +
                           r"_to_" + str(self.target_node_location))
        return {asset_identity: self.size()}