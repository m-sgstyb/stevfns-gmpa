#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import numpy as np
import cvxpy as cp
import pandas as pd
from ..network import Edge_STEVFNs
from .Base_Assets import Asset_STEVFNs

class Stock_Asset_STEVFNs(Asset_STEVFNs):
    """
    Base class for assets with a period-indexed capacity stock.

    self.new_capacity: period-indexed new-install decision Variable
    (shape (num_periods,)) -- always present, drives the stock-node chain
    (_build_stock_edges).

    self.flows: hourly Variable if the asset has real hourly dispatch
    (e.g. PP_CO2), else defaults to cp.Constant(0) (e.g. PV/wind, whose
    hourly generation is a derived expression on edges, not an
    independent decision variable). Subclasses that need real hourly
    dispatch overwrite self.flows and cost_fun_params['usage_constant']
    with actual Variable/Parameter after calling _define_period_structure.

    cost_fun(new_capacity, flows, params) is the single shared contract
    for every stock asset: capital cost on new_capacity (via
    cost_multiplier) + usage cost on flows (via usage_constant). Both
    default to Constant(0) placeholders, so the formula naturally
    collapses to capital-only for assets with no hourly cost term,
    without needing a per-subclass build_cost override. build_cost()
    itself is defined once, here, and not overridden by subclasses --
    single extension point for the whole stock-asset family, same as
    Asset_STEVFNs.build_cost() is for the base family.

    decommission_mode controls ONLY existing_capacity_vec's decay.
    new_capacity is always retired via a fixed hard-lifetime mask.
    """
    asset_name = "Stock_Asset_STEVFNs"
    stock_node_type = "NULL"
    decommission_mode = "decay_rate"

    @staticmethod
    def cost_fun(new_capacity, flows, params):
        capital_cost = cp.sum(cp.multiply(new_capacity, params["sizing_constant"]))
        usage_cost = cp.sum(cp.multiply(params["usage_constant"], flows))
        return capital_cost + usage_cost

    def build_cost(self):
        self.cost = self.cost_fun(self.new_capacity, self.flows, self.cost_fun_params)
        return

    def _define_period_structure(self, asset_structure):
        """Call from subclass define_structure(). Sets up new_capacity,
        carryover_out, and default (no-op) flows/usage_constant --
        subclasses with real hourly dispatch overwrite the latter two
        afterward."""
        self._compute_period_counts()
        self.period_start_years = np.arange(self.num_periods) * self.reinvestment_period

        self.new_capacity = cp.Variable(shape=(self.num_periods,), nonneg=True,
                                         name=f"new_capacity_{self.asset_name}")
        self.carryover_out = cp.Variable(shape=(self.num_periods,), nonneg=True,
                                          name=f"carryover_{self.asset_name}")

        self.flows = cp.Constant(0)   # default: no independent hourly dispatch variable

        self.cost_fun_params = {
            "sizing_constant": cp.Parameter(shape=(self.num_periods,), nonneg=True,
                                             name=f"sizing_constant_{self.asset_name}"),
            "usage_constant": cp.Constant(0),   # default: no usage cost term
        }
        self.decom_mask_param = cp.Parameter(shape=(self.num_periods, self.num_periods), nonneg=True,
                                              name=f"decom_mask_{self.asset_name}")
        self.existing_capacity_vec = cp.Parameter(shape=(self.num_periods,), nonneg=True,
                                                    name=f"existing_capacity_vec_{self.asset_name}")
        return

    def _build_stock_edges(self):
        decommission_out = self.decom_mask_param @ self.new_capacity

        for p in range(self.num_periods):
            stock_node = self.network.extract_node(self.stock_node_location,
                                                     self.stock_node_type, p)
            stock_node.curtailment = False

            install_edge = Edge_STEVFNs()
            self.edges.append(install_edge)
            install_edge.attach_target_node(stock_node)
            install_edge.flow = self.new_capacity[p]

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
        return

    def _update_new_capacity_decom_mask(self):
        asset_lifetime = getattr(self, "_asset_lifetime", None) or float(self.parameters_df["lifespan"] / 8760)
        lifetime_periods = max(int(round(asset_lifetime / self.reinvestment_period)), 1)
        decom_mask = np.zeros((self.num_periods, self.num_periods))
        for p in range(self.num_periods):
            k = p - lifetime_periods
            if 0 <= k < self.num_periods:
                decom_mask[p, k] = 1
        self.decom_mask_param.value = decom_mask
        return

    def _get_lifetime_periods(self):
        """Number of whole reinvestment periods a cohort remains in
        service (shared by the decommission mask and the annual-repayment
        window, so the two stay consistent)."""
        asset_lifetime = float(self.parameters_df["lifespan"] / 8760)
        self._asset_lifetime = asset_lifetime
        lifetime_periods = max(int(round(asset_lifetime / self.reinvestment_period)), 1)
        self._lifetime_periods = lifetime_periods
        return lifetime_periods

    def _update_sizing_constant(self, sizing_constant_vec):
        """
        Amortised, NPV-discounted per-period sizing-cost multiplier, fed
        to the objective via cost_fun_params['sizing_constant'].

        sizing_constant_vec: per-period raw capex ($/unit capacity),
        BEFORE amortisation or discounting -- from a per-period profile
        (PV) or a broadcast scalar baseline (PP_CO2).

        """
        lifetime_periods = self._lifetime_periods if hasattr(self, "_lifetime_periods") else self._get_lifetime_periods()
        asset_lifetime = self._asset_lifetime
        interest_rate = float(self.parameters_df["interest_rate"])
        discount_rate = float(self.network.system_parameters_df.loc["discount_rate", "value"])

        amort_factor = (interest_rate * (1 + interest_rate) ** asset_lifetime) / \
                        ((1 + interest_rate) ** asset_lifetime - 1)
        annuity_factor = (1 - (1 + discount_rate) ** (-asset_lifetime)) / discount_rate
        period_discount = (1 + discount_rate) ** (-self.period_start_years.astype(float))

        self.cost_fun_params["sizing_constant"].value = (
            sizing_constant_vec * amort_factor * annuity_factor * period_discount
        )
        return

    def _update_existing_capacity_vec(self):
        existing_capacity = float(self.parameters_df["existing_capacity"])
        if self.decommission_mode == "decay_rate":
            decay_rate = float(self.parameters_df["existing_capacity_decay_rate"])
            retention = (1 - decay_rate) ** np.arange(self.num_periods)
        elif self.decommission_mode == "profile":
            retention = self._existing_capacity_profile_retention()
        else:
            raise ValueError(f"Unknown decommission_mode: {self.decommission_mode}")
        self.existing_capacity_vec.value = existing_capacity * retention
        return

    def _existing_capacity_profile_retention(self):
        profile_filename = self.parameters_df["existing_capacity_profile_filename"] + ".csv"
        profile_path = os.path.join(self.parameters_folder, "profiles", profile_filename)
        profile_df = pd.read_csv(profile_path)
        location = self.parameters_df["location_name"]
        rows = profile_df[profile_df["location_name"] == location].sort_values("period_index")
        period_retention = rows["retention_fraction"].to_numpy(dtype=float)
        if period_retention.size != self.num_periods:
            raise ValueError(
                f"existing_capacity retention profile for location='{location}' in "
                f"{profile_filename} has {period_retention.size} matching rows, "
                f"expected {self.num_periods} (one per reinvestment period)."
            )
        return np.cumprod(period_retention)

    def get_new_capacity(self):
        return None if self.new_capacity.value is None else np.array(self.new_capacity.value)

    def get_operating_stock(self):
        return None if self.carryover_out.value is None else np.array(self.carryover_out.value)

    def size(self):
        return self.new_capacity.value

    def asset_size(self):
        return self.new_capacity.value