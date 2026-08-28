#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from ..Base_Trade_Assets import Trade_Stock_Asset_STEVFNs

class NH3_Transport_Asset(Trade_Stock_Asset_STEVFNs):
    """
    Ammonia shipping between two NH3 nodes in separate locations
    Lightweight sub class of shared Trade_Stock_Asset_STEVFNs
    """

    asset_name = "NH3_Transport"
    source_node_type = "NH3"
    target_node_type = "NH3"
    capacity_unit = "Gg/h"