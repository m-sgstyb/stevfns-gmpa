#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compiling results for STEVFNs case studies and scenarios
"""

import os
import pandas as pd
import numpy as np

# --- Lookups derived from case-study input files --- #

def build_location_lookup(location_parameters_df):
    """dict: Network_Structure.csv Location_1/Location_2 index value ->
    ISO-2 country code, read from Location_Parameters.csv's
    'location_name' column.
    """
    return dict(zip(location_parameters_df["Location"], location_parameters_df["location_name"]))


def determine_scenario_type(network_structure_df):
    """'collab' if any asset class in this network involves transport
    between locations, else 'autarky'."""
    is_collab = network_structure_df["Asset_Class"].str.contains(
        "Transport", case=False, na=False
    ).any()
    return "collab" if is_collab else "autarky"


def load_readable_names(readable_names_path):
    """
    readable_names.csv: columns Asset_Class, Readable_Name.
    """
    return pd.read_csv(readable_names_path)

# --- Core compilation (per-year cost / emissions / capacity) --- #

def compile_scenario_results(my_network, network_structure_df, location_parameters_df,
                              readable_names_df, scenario_id, case_id,
                              start_year=2025, reinvestment_period_years=None):
    """
    Walks every asset in a solved my_network and returns one long-format
    DataFrame with to get costs and emissions data for result analysis

    scenario_id: pass my_network.scenario_name (the scenario folder name).
    case_id: pass case_study_name
    reinvestment_period_years: defaults to the network's own configured
        reinvestment_period (in years) if not supplied.
    """
    if reinvestment_period_years is None:
        reinvestment_period_years = int(
            my_network.system_parameters_df.loc["reinvestment_period", "value"] / 8760
        )

    location_lookup = build_location_lookup(location_parameters_df)
    scenario_type = determine_scenario_type(network_structure_df)

    all_records = []
    for asset in my_network.assets:
        try:
            asset_records = asset.get_results_records(
                readable_names_df, location_lookup, start_year, reinvestment_period_years
            )
        except Exception as e:
            print(f"[compile_results] Skipping asset "
                  f"{getattr(asset, 'asset_name', type(asset).__name__)} due to: {e}")
            continue
        all_records.extend(asset_records)

    results_df = pd.DataFrame(all_records)
    if results_df.empty:
        return results_df

    results_df.insert(0, "scenario_id", scenario_id)
    results_df.insert(1, "scenario_type", scenario_type)
    results_df.insert(2, "case_id", case_id)

    results_df = results_df[
        ["scenario_id", "scenario_type", "case_id", "country",
         "year", "technology", "metric", "unit", "value"]
    ]
    return results_df

# --- Splitting / aggregating into the final result file shapes --- #

def split_by_metric(results_df):
    """costs and emissions over time results share same 9-column schema
    Filter by metric"""
    costs_df = results_df[results_df["metric"] == "cost"].reset_index(drop=True)
    emissions_df = results_df[results_df["metric"] == "emissions"].reset_index(drop=True)
    return costs_df, emissions_df

def join_capacities(results_df):
    """Return one row per asset/year with new and stock capacities."""
    capacity_df = (
        results_df[
            results_df["metric"].isin(["new_capacity", "stock_capacity"])
        ]
        .pivot(
            index=[
                "scenario_id",
                "scenario_type",
                "case_id",
                "country",
                "year",
                "technology",
                "unit",
            ],
            columns="metric",
            values="value",
        )
        .reset_index()
        .rename_axis(None, axis=1)
    )
    return capacity_df

def aggregate_emissions_by_country(emissions_df):
    """emissions over time by country: no technology column, emissions
    reported summed across every technology, per country/year."""
    if emissions_df.empty:
        return emissions_df
    grouped = (
        emissions_df
        .groupby(["scenario_id", "scenario_type", "case_id", "country", "year", "metric", "unit"],
                  as_index=False)["value"]
        .sum()
    )
    return grouped


def aggregate_costs_by_technology(costs_df):
    """
    Cost per technology, country, sceanrio for dpacc
    trajectories result file
    """
    empty_cols = ["scenario_id", "scenario_type", "case_id",
                  "country", "technology_name", "technology_cost"]
    if costs_df.empty:
        return pd.DataFrame(columns=empty_cols)
 
    grouped = (
        costs_df
        .groupby(["scenario_id", "scenario_type", "case_id", "country", "technology"],
                  as_index=False)["value"]
        .sum()
    )
    grouped["technology_name"] = grouped["technology"] + " [" + grouped["country"].astype(str) + "]"
    grouped = grouped.rename(columns={"value": "technology_cost"})
    return grouped[empty_cols]

def get_capacities_by_technology(costs_df):
    """
    installed_cap_over_time.csv result file creation
    Need review over methodology for correct values
    """
    empty_cols = ["scenario_id", "scenario_type", "case_id",
                  "country", "technology_name", "technology_cost"]
    if costs_df.empty:
        return pd.DataFrame(columns=empty_cols)

    grouped = (
        costs_df
        .groupby(["scenario_id", "scenario_type", "case_id", "country", "technology"],
                  as_index=False)["value"]
        .sum()
    )
    grouped["technology_name"] = grouped["technology"] + " [" + grouped["country"].astype(str) + "]"
    grouped = grouped.rename(columns={"value": "technology_cost"})
    return grouped[empty_cols]

# --- Hourly flows per modelled reinvestment period, per asset --- #

def compile_hourly_flows(my_network, network_structure_df, location_parameters_df,
                          readable_names_df, scenario_id, case_id,
                          start_year=2025, reinvestment_period_years=None):
    """
    For every asset in my_network with get_period_flows gets the hourly
    per period flows for later plotting
    """
    if reinvestment_period_years is None:
        reinvestment_period_years = int(
            my_network.system_parameters_df.loc["reinvestment_period", "value"] / 8760
        )

    location_lookup = build_location_lookup(location_parameters_df)
    scenario_type = determine_scenario_type(network_structure_df)

    all_records = []
    for asset in my_network.assets:
        get_period_flows = getattr(asset, "get_period_flows", None)
        if get_period_flows is None:
            continue
        try:
            period_flows = get_period_flows()
        except Exception as e:
            print(f"[compile_results] Skipping hourly flows for asset "
                  f"{getattr(asset, 'asset_name', type(asset).__name__)} due to: {e}")
            continue
        if period_flows is None:
            continue

        technology = asset.get_results_technology_name(readable_names_df)
        country = asset.get_results_country(location_lookup)

        for period_index, hourly_values in enumerate(period_flows):
            if hourly_values is None:
                continue
            hourly_values = np.asarray(hourly_values, dtype=float)
            year = start_year + period_index * reinvestment_period_years
            for hour_index, flow_value in enumerate(hourly_values):
                all_records.append({
                    "scenario_id": scenario_id,
                    "scenario_type": scenario_type,
                    "case_id": case_id,
                    "country": country,
                    "technology": technology,
                    "year": year,
                    "hour": hour_index,
                    "flow": flow_value,
                })

    return pd.DataFrame(all_records, columns=[
        "scenario_id", "scenario_type", "case_id", "country",
        "technology", "year", "hour", "flow",
    ])

# --- Append-and-persist helper --- #

def append_and_save(df, filepath, key_columns=("scenario_id", "case_id")):
    """Appends df to the CSV at filepath; drops any existing
    rows whose key_columns match a row in df. Re-running a scenario
    overwrites its previous entry instead of duplicating it, while every
    other scenario already in the file is left untouched.
    """
    if df.empty:
        return
    if os.path.exists(filepath):
        existing_df = pd.read_csv(filepath)
        key_columns = [col for col in key_columns if col in existing_df.columns and col in df.columns]
        if not existing_df.empty and key_columns:
            new_keys = df[key_columns].drop_duplicates()
            merged = existing_df.merge(new_keys, on=key_columns, how="left", indicator=True)
            existing_df = existing_df[merged["_merge"].values == "left_only"].reset_index(drop=True)
        df = pd.concat([existing_df, df], ignore_index=True)
    df.to_csv(filepath, index=False)
    return