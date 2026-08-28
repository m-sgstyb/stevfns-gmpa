#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from ..Base_Trade_Assets import Trade_Stock_Asset_STEVFNs

class EL_Transport_Asset(Trade_Stock_Asset_STEVFNs):
    """
    HVDC interconnector between two EL grid nodes in separate locations
    Lightweight sub class of shared Trade_Stock_Asset_STEVFNs
    """

    asset_name = "EL_Transport"
    source_node_type = "EL"
    target_node_type = "EL"
    capacity_unit = "GW"