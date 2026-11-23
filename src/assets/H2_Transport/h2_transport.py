#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from ..Base_Trade_Assets import Trade_Stock_Asset_STEVFNs

class H2_Transport_Asset(Trade_Stock_Asset_STEVFNs):
    """
    Hydrogen shipping between two NH3 nodes in separate locations
    Lightweight sub class of shared Trade_Stock_Asset_STEVFNs
    """

    asset_name = "H2_Transport"
    source_node_type = "H2"
    target_node_type = "H2"
    capacity_unit = "Gg/h"
    hours_per_day = 24 # hard-coded

    def define_structure(self, asset_structure):
        self.departure_interval = float(asset_structure["Period"])
        self.voyage_length = float(asset_structure["Transport_Time"])
        if self.voyage_length < 0:
            raise ValueError(f"{self.asset_name}: Transport_Time (voyage length in hours) must be"
                             f">= 0; got {self.voyage_length}")
        # get the departure slot interval from network structure
        slot_interval = self._dep_slot_interval(self.departure_interval)
        # Derive base structure of departure slots
        slot_structure = asset_structure.copy()
        slot_structure["Period"] = slot_interval
        slot_structure["Transport_Time"] = 0 
        super().define_structure(slot_structure)
        self.asset_structure = asset_structure
        self.slot_interval = slot_interval

        if self.number_of_edges % self.num_years != 0:
            raise ValueError(f"{self.asset_name}: {self.number_of_edges} shipping departure slots cannot be"
                             f"split into {self.num_years} equal years. Check Start_Time/End_Time parameters.")
        self.edges_per_year = self.number_of_edges // self.num_years

        # Define periodic steady-state: arrival shifted by the voyage length left after whole days
        # Wraps inside the same sampled day
        phase = int(round(self.voyage_length)) % self.hours_per_day
        start = int(asset_structure["Start_Time"])
        relative_hours = self.source_node_times - start
        day_start = (relative_hours // self.hours_per_day) * self.hours_per_day
        hour_of_day = relative_hours % self.hours_per_day
        self.target_node_times = (start + day_start +
                               (hour_of_day + phase) % self.hours_per_day).astype(int)
        print(f"[{self.asset_name} {self.source_node_location}->{self.target_node_location}] "
              f"Period={self.departure_interval:g} h, Transport_Time={self.voyage_length:g} h: "
              f"{self.edges_per_year} departure slot(s) per sampled year, "
              f"arrival shifted {phase} h inside each day.")

    def _dep_slot_interval(self, period):
        """
        Hours between shipping departure slots on the sampled timeline
            period - departure interval in hours
        """
        if period < 1 or abs(period - round(period)) > 1e-9:
            raise ValueError(f"{self.asset_name}: Period (hours between ship departures) must be"
                             f"a whole number >= 1, got {period}")
        period = int(round(period))
        if period <= self.hours_per_day:
            if self.hours_per_day % period != 0:
                raise ValueError(f"{self.asset_name}: Period (hours between ship departures)={period} h must divide  24 h"
                                 f"(1, 2, 3, 4, 6, 8, 12) or be a whole number of days (24, 48, etc.)"
                                 )
            return period
        if period % self.hours_per_day != 0:
            raise ValueError(f"{self.asset_name}: Period (hours between ship departures)={period} h must be a whole number of days "
                             f" when longer than 24 h (e.g. 48, 72, 96)")
        return self.hours_per_day

    def _get_year_change_indices(self):
        """
        Override edge indexes from parent. Edge index at which the model year starts
        """
        self.year_change_indices = [y * self.edges_per_year for y in range(self.num_years)]
        return list(self.year_change_indices)