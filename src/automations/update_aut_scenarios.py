#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Aug 12 11:50:25 2025

@author: Mónica Sagastuy-Breña

Update Asset_Parameters.csv, Location_Parameters.csv, and System_Parameters.csv
for Autarky_XX scenario folders based on the BAU folder.

Usage:
    python update_autarky.py XX,YY,ZZ
"""


import os
import sys
import pandas as pd
import numpy as np

# Define the root folder (script is in STEVFNs/Code/Automations)
script_folder = os.path.dirname(os.path.abspath(__file__))

# Path to the Data/Case_Study data folder
base_folder = os.path.abspath(
    os.path.join(script_folder, "..", "..", "Data", "Case_Study")
)

base_scenario_name = "BAU"

def update_autarky_country(country_code):
    """Updates all scenario folders for a single Autarky country case."""
    sc_case_study_folder = os.path.join(base_folder, f"Autarky_{country_code}")

    # Paths to BAU files
    sc_asset_filename = os.path.join(sc_case_study_folder, base_scenario_name, "Asset_Parameters.csv")
    sc_location_filename = os.path.join(sc_case_study_folder, base_scenario_name, "Location_Parameters.csv")
    sc_system_filename = os.path.join(sc_case_study_folder, base_scenario_name, "System_Parameters.csv")

    # Read base data
    base_asset_df = pd.read_csv(sc_asset_filename)
    base_locs_df = pd.read_csv(sc_location_filename)
    base_sys_df = pd.read_csv(sc_system_filename)

    # Loop through scenarios 90, 80, ..., 0
    for counter1, scenario_value in enumerate(reversed(np.arange(0, 100, 10))):
        scenario_name = str(scenario_value)
        scenario_folder = os.path.join(sc_case_study_folder, scenario_name)
        os.makedirs(scenario_folder, exist_ok=True)

        # Asset Parameters
        new_asset_df = base_asset_df.copy()
        asset_type_list = list(new_asset_df["Asset_Type"])
        asset_type_list[0] = new_asset_df["Asset_Type"][0] + counter1 + 1
        new_asset_df["Asset_Type"] = asset_type_list
        new_asset_df.to_csv(os.path.join(scenario_folder, "Asset_Parameters.csv"), index=False)

        # Location Parameters
        base_locs_df.to_csv(os.path.join(scenario_folder, "Location_Parameters.csv"), index=False)

        # System Parameters
        base_sys_df.to_csv(os.path.join(scenario_folder, "System_Parameters.csv"), index=False)

    print(f"✅ Updated Autarky_{country_code}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python update_autarky.py XX,YY,ZZ")
        sys.exit(1)

    country_codes = [code.strip().upper() for code in sys.argv[1].split(",")]

    for code in country_codes:
        update_autarky_country(code)
