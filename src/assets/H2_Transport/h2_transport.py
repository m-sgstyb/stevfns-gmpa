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