#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import numpy as np
import pandas as pd
import cvxpy as cp
from ..Base_Vehicle_Assets import Base_Vehicle_Asset_STEVFNs
from ...network import Edge_STEVFNs

class VEH_EL_FRT_Asset(Base_Vehicle_Asset_STEVFNs):
    """
    Class of Freight Electric Vehicle
    """
    asset_name = "VEH_EL_FRT"
    source_node_type = "NULL" # Edge to freight demand node
    target_node_type = "FRT" # Edge to freight demand node
    
    el_source_node_type = "EL" # Charging EV hourly edges
    batt_node_type = "FRT_VEH_BESS" # Charging EV hourly edges
    batt_cap_node_type = "FRT_EV_BESS_Cap"
    charge_limit_node_type = "FRT_EV_Charge_Limit"
    period = 1
    transport_time = 0

    def __init__(self):
        super().__init__()
        self.conversion_fun_params_2 = cp.Parameter(nonneg=True,
                                                    name=f"charge_efficiency_{self.asset_name}")
        return

    def define_structure(self, asset_structure):
        super().define_structure(asset_structure)
        self.batt_node_location = self.source_node_location
        self.charge = cp.Variable(self.number_of_edges, nonneg=True,
                                  name=f"charge_{self.asset_name}")
        self.soc_carry = cp.Variable(self.number_of_edges, nonneg=True,
                                     name=f"soc_carry_{self.asset_name}")
        self.charge_efficiency_param = cp.Parameter(nonneg=True,
                                                    name=f"charge_efficiency_{self.asset_name}")
        self.energy_intensity_param = cp.Parameter(nonneg=True,
                                                   name=f"energy_intensity_{self.asset_name}")
        self.battery_energy_per_capacity_param = cp.Parameter(nonneg=True,
                                                              name=f"battery_energy_per_capacity_{self.asset_name}")
        self.charge_rate_per_capacity_param = cp.Parameter(nonneg=True,
                                                           name=f"charge_rate_per_capacity_{self.asset_name}")
        return

    def build_edges(self):
        super().build_edges()
        self._build_charging_edges()
        self._build_drive_drain_edges()
        self._build_soc_carry_edges()
        self._build_battery_capacity_limit_edges()
        self._build_charge_rate_limit_edges()
        return

    def _build_charging_edges(self):
        """ EL grid -> EV fleet battery pool, per sampled hour"""
        self._charge_edges = []
        for t in range(self.number_of_edges):
            edge = Edge_STEVFNs()
            self.edges.append(edge)
            self._charge_edges.append(edge)
            edge.attach_source_node(self.network.extract_node(
                self.source_node_location, self.el_source_node_type, self.source_node_times[t]
            ))
            edge.attach_target_node(self.network.extract_node(
                self.batt_node_location, self.batt_node_type, t
            ))
            edge.flow = self.charge[t] * self.charge_efficiency_param
        return

    def _build_drive_drain_edges(self):
        """Driving draws down from the fleet's battery pool
        NULL target node (sink)"""
        for t in range(self.number_of_edges):
            edge = Edge_STEVFNs()
            self.edges.append(edge)
            edge.attach_source_node(self.network.extract_node(
                self.batt_node_location, self.batt_node_type, t
            ))
            edge.flow = self.flows[t] * self.energy_intensity_param

    def _build_soc_carry_edges(self):
        """Pooled fleet EV batteries' SOC carried hour to hour
        """
        for t in range(self.number_of_edges):
            t_next = t + 1
                       
    def _build_battery_capacity_limit_edges(self):
        """Pooled EV battery capacity scales with the operating fleet (stock)
        Checked at each reinvestment period's peak SOC"""
        for p in range(self.num_periods):
            start, end = self.period_boundaries[p], self.period_boundaries[p + 1]
            period_soc = self.soc_carry[start:end]
 
            edge = Edge_STEVFNs()
            self.edges.append(edge)
            edge.attach_target_node(self.network.extract_node(
                self.batt_node_location, self.batt_cap_node_type, p))
            edge.flow = (self.carryover_out[p] * self.battery_energy_per_capacity_param
                         - cp.max(period_soc))
        return

    def _build_charge_rate_limit_edges(self):
        """Maximum charging rate constraint charge[t] <= carryover_out[p] *
        charge_rate_per_capacity"""
        for p in range(self.num_periods):
            start, end = self.period_boundaries[p], self.period_boundaries[p + 1]
            period_charge = self.charge[start:end]
 
            edge = Edge_STEVFNs()
            self.edges.append(edge)
            edge.attach_target_node(self.network.extract_node(
                self.batt_node_location, self.charge_limit_node_type, p))
            edge.flow = (self.carryover_out[p] * self.charge_rate_per_capacity_param
                         - cp.max(period_charge))
        return

    def _update_parameters(self):
        super()._update_parameters()
        self.charge_efficiency_param.value = float(self.parameters_df["charge_efficiency"])
        self.battery_energy_per_capacity_param.value = float(self.parameters_df["battery_energy_per_capacity"])
        self.charge_rate_per_capacity_param.value = float(self.parameters_df["charge_rate_per_capacity"])
        self._update_energy_intensity_param()
        return
        
    def _update_energy_intensity_param(self):
        """Convert units for energy intensity via load factor
        energy intensity [=] GWh / mveh-km"""
        input_energy_intensity = float(self.parameters_df["energy_intensity"]) # GWh/mtkm
        load_factor = float(self.parameters_df["load_factor"]) # mton/mveh
        self.energy_intensity_param.value = input_energy_intensity * load_factor
        return