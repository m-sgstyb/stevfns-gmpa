#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Feb  9 11:13:27 2026

@author: Mónica Sagastuy-Breña

Script with plotting functions for testing assets
    1. Hourly dispatch plots
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import cm

def plot_stacked_from_df(
    df,
    output_folder,
    filename="stacked_plot.png",
    time_col_candidates=("time", "timestep"),
    demand_col_candidates=("demand", "el_demand", "load"),
    phs_turb_substrs=("turb", "turbine"),
    phs_pump_substrs=("pump", "pumping"),
    cmap_name="Set1",
    expected_timesteps=None,
    figsize=(12,5),
    skip_zero_columns=True,
    verbose=False
):
    """
    Plot stacked generation from df, with PHS pumping drawn as negative area below zero.

    Parameters:
      - df: pandas DataFrame produced by export_results_csv
      - skip_zero_columns: if True, columns that are entirely zero are omitted from the stack/legend
    """

    os.makedirs(output_folder, exist_ok=True)

    # 1) detect time column
    cols_lower = [c.lower() for c in df.columns]
    time_col = None
    for cand in time_col_candidates:
        if cand in cols_lower:
            time_col = df.columns[cols_lower.index(cand)]
            break
    if time_col is None:
        time_col = df.columns[0]
        if verbose:
            print(f"No explicit time column found; using first column '{time_col}' as time.")

    # 2) detect demand column
    demand_col = None
    for cand in demand_col_candidates:
        if cand in cols_lower:
            demand_col = df.columns[cols_lower.index(cand)]
            break

    # 3) detect PHS turbine and pump columns
    phs_turb_cols = [c for c in df.columns if any(s in c.lower() for s in phs_turb_substrs)]
    phs_pump_cols = [c for c in df.columns if any(s in c.lower() for s in phs_pump_substrs)]
    # prefer to filter by 'phs' too if available
    phs_like = [c for c in df.columns if "phs" in c.lower()]
    if phs_like:
        phs_turb_cols = [c for c in phs_turb_cols if "phs" in c.lower()] or phs_turb_cols
        phs_pump_cols = [c for c in phs_pump_cols if "phs" in c.lower()] or phs_pump_cols

    # 4) determine generation columns (exclude time, demand, soc/reservoir and phs pump/turb)
    excluded = {time_col}
    if demand_col is not None:
        excluded.add(demand_col)
    for c in df.columns:
        if c.lower() in ("soc", "state_of_charge", "reservoir"):
            excluded.add(c)
    excluded.update(phs_turb_cols)
    excluded.update(phs_pump_cols)

    gen_cols = [c for c in df.columns if c not in excluded]

    if verbose:
        print("time_col:", time_col)
        print("demand_col:", demand_col)
        print("phs_turb_cols:", phs_turb_cols)
        print("phs_pump_cols:", phs_pump_cols)
        print("gen_cols (stacked):", gen_cols)

    # 5) plotting length and helper to normalize/pad/truncate
    T = expected_timesteps if expected_timesteps is not None else int(len(df))
    x = np.arange(T)

    def _series(c):
        arr = np.asarray(df[c].values).astype(float).flatten()
        if arr.shape[0] >= T:
            return arr[:T]
        return np.pad(arr, (0, T - arr.shape[0]), constant_values=0.0)

    # 6) prepare stacked arrays (filter zeros if skip_zero_columns)
    stacked_arrays = []
    labels = []
    for c in gen_cols:
        series = _series(c)
        if skip_zero_columns and not np.any(series):
            if verbose:
                print(f"skipping zero-only column: {c}")
            continue
        stacked_arrays.append(series)
        labels.append(c)

    # 7) colors
    cmap = cm.get_cmap(cmap_name)
    n = max(1, len(stacked_arrays))
    colors = [cmap(i / max(1, n - 1)) for i in range(n)]

    # 8) compute PHS totals
    phs_turb_total = np.zeros(T, dtype=float)
    for c in phs_turb_cols:
        s = _series(c)
        phs_turb_total += s

    phs_pump_total = np.zeros(T, dtype=float)
    for c in phs_pump_cols:
        s = _series(c)
        phs_pump_total += s

    # 9) draw plot
    plt.figure(figsize=figsize)
    bottom = np.zeros(T, dtype=float)

    # plot stacked generation layers
    for i, (arr, label) in enumerate(zip(stacked_arrays, labels)):
        if not np.any(arr):
            continue
        c = colors[i % len(colors)]
        plt.fill_between(x, bottom, bottom + arr, color=c, label=label, edgecolor='none', alpha=1.0)
        bottom += arr

    # plot phs turbine (discharge) on top of stack (positive)
    if np.any(phs_turb_total):
        # choose a PHS color distinct from the PP colors (or reuse a neutral one)
        phs_color = "#3D1186"
        plt.fill_between(x, bottom, bottom + phs_turb_total, color=phs_color,
                         label="PHS Turbine (discharge)", edgecolor='none', alpha=1.0)
        bottom += phs_turb_total

    # plot phs pumping as negative area below zero
    if np.any(phs_pump_total):
        # plotting negative area: from 0 down to -phs_pump_total
        phs_color = "#3D1186"
        neg = -phs_pump_total
        plt.fill_between(x, 0.0, neg, where=(neg < 0), facecolor=phs_color, alpha=0.35,
                         label="PHS Pumping (charge)", edgecolor='none', hatch='//')

    # demand line
    if demand_col is not None:
        demand = _series(demand_col)
        plt.plot(x, demand, color="red", linestyle="--", linewidth=1.4, label="Demand")

    # aesthetics
    plt.xlabel("Timestep")
    plt.ylabel("Power (MW)")
    plt.title("Stacked generation by technology (pumping shown negative)")
    plt.grid(True, linestyle=":", alpha=0.4)

    # legend: dedupe labels
    handles, labels_ = plt.gca().get_legend_handles_labels()
    by_label = dict(zip(labels_, handles))
    plt.legend(by_label.values(), by_label.keys(), loc="upper right", fontsize="small", ncol=2)

    plt.tight_layout()
    outpath = os.path.join(output_folder, filename)
    plt.savefig(outpath, dpi=300)
    plt.close()

    if verbose:
        print("Saved stacked plot to:", outpath)
    return outpath


def export_results_csv(network, filepath, hours=720):
    """
    Export hourly flows for all assets in the network into a CSV.
    - One column per asset (asset.asset_name). If duplicate names occur, a suffix is appended.
    - For assets with a gen_profile (e.g. Nuclear or RE), uses flows * gen_profile.
    - For Multi_Asset (assets_dictionary), exports each subasset as AssetName_SubassetName.
    - Skips SOC for PHS (or any subasset named 'Reservoir' or 'SOC' by convention).
    - Attempts several fallbacks (scalar flows, vector flows, get_plot_data).
    """

    cols = {"time": np.arange(hours)}
    name_counts = {}  # to ensure unique column names

    def unique_name(base):
        cnt = name_counts.get(base, 0)
        name_counts[base] = cnt + 1
        return base if cnt == 0 else f"{base}_{cnt}"

    for asset in network.assets:
        # --- SKIP CO2_Budget entirely ---
        if asset.asset_name == "CO2_Budget":
            continue
        base_name = str(asset.asset_name)
        # Helper: attempt to construct a series from a (possibly scalar) cvxpy variable/parameter
        def to_series_from_value(val):
            """Take a numeric scalar or array-like and return np.array of length `hours` (or shorter)."""
            if val is None:
                return None
            # cvxpy Parameter/Variable .value may be numpy array or scalar
            try:
                if np.isscalar(val):
                    return np.full(hours, float(val))
                arr = np.array(val)
                # If arr is 0-d, treat as scalar
                if arr.ndim == 0:
                    return np.full(hours, float(arr))
                return arr[:hours]
            except Exception:
                return None

        # 1) If asset has a gen_profile (Parameter with .value) and flows scalar or vector:
        try:
            gen_profile_val = None
            if hasattr(asset, "gen_profile"):
                gp = getattr(asset, "gen_profile")
                # cp.Parameter has .value; if not set, skip
                gen_profile_val = getattr(gp, "value", None)
                if gen_profile_val is not None:
                    gen_profile_val = np.array(gen_profile_val)[:hours]
            # get flows.value if present
            fv = getattr(asset, "flows", None)
            fv_val = getattr(fv, "value", None) if fv is not None else None

            # Case A: gen_profile present and numeric:
            if gen_profile_val is not None:
                # flows may be scalar or vector; handle both
                if fv_val is None:
                    # no numeric flows -> cannot compute; try get_plot_data below
                    flow_series = None
                else:
                    # scalar flows -> multiply scalar * gen_profile
                    if np.isscalar(fv_val) or (isinstance(fv_val, np.ndarray) and fv_val.ndim == 0):
                        flow_series = float(fv_val) * gen_profile_val
                    else:
                        # fv_val is an array: multiply elementwise (truncate to hours)
                        flow_series = np.array(fv_val)[:hours] * gen_profile_val
                if flow_series is not None:
                    colname = unique_name(base_name)
                    cols[colname] = flow_series
                    continue  # next asset

            # Case B: No gen_profile — try to read flows.value direct
            if fv_val is not None:
                series = to_series_from_value(fv_val)
                if series is not None:
                    colname = unique_name(base_name)
                    cols[colname] = series[:hours]
                    continue

            # Case C: Multi-asset aggregator (e.g. PHS). Export subassets individually
            if hasattr(asset, "assets_dictionary") and isinstance(asset.assets_dictionary, dict):
                for subname, sub in asset.assets_dictionary.items():
                    # Skip reservoir SOC column if user doesn't want it (common name 'Reservoir' or 'SOC')
                    if subname.lower().startswith("reservoir") or subname.lower() == "soc":
                        continue
                    sval = getattr(sub, "flows", None)
                    sval_val = getattr(sval, "value", None) if sval is not None else None
                    # If sub has gen_profile, handle analogous to above
                    s_gp_val = getattr(sub, "gen_profile", None)
                    s_gp_val = getattr(s_gp_val, "value", None) if s_gp_val is not None else None
                    if s_gp_val is not None and sval_val is not None:
                        # multiply scalar or vector appropriately
                        if np.isscalar(sval_val):
                            series = float(sval_val) * np.array(s_gp_val)[:hours]
                        else:
                            series = np.array(sval_val)[:hours] * np.array(s_gp_val)[:hours]
                    elif sval_val is not None:
                        series = to_series_from_value(sval_val)
                    else:
                        # fallback to sub.get_plot_data if present
                        series = None
                        if hasattr(sub, "get_plot_data"):
                            try:
                                pdv = sub.get_plot_data()
                                series = np.array(pdv)[:hours]
                            except Exception:
                                series = None
                    if series is not None:
                        colname = unique_name(f"{base_name}_{subname}")
                        cols[colname] = series[:hours]
                continue

            # Case D: fallback to asset.get_plot_data() if available
            if hasattr(asset, "get_plot_data"):
                try:
                    pdv = asset.get_plot_data()
                    if pdv is not None:
                        series = np.array(pdv)[:hours]
                        colname = unique_name(base_name)
                        cols[colname] = series
                        continue
                except Exception:
                    pass
            # If we reach here, we couldn't extract flows for this asset
            print(f"export_results_csv: skipping asset '{base_name}' — no numeric flow data found.")
        except Exception as e:
            print(f"export_results_csv: error extracting asset '{base_name}': {e}")
            continue
        
    # for name, arr in cols.items():
    #     print("COLUMN:", name)
    #     if arr is None:
    #         print("  -> value is None")
    #         continue
    #     try:
    #         a = np.array(arr)
    #         print("  dtype:", a.dtype, "shape:", a.shape)
    #         # show first/last few values
    #         print("  sample:", a.flatten()[:3], "...", a.flatten()[-3:])
    #     except Exception as e:
    #         print("  -> cannot convert to array:", e)
    # Construct DataFrame in deterministic column order: time first, then sorted asset columns
    df = pd.DataFrame(cols)
    # Ensure time is first col
    cols_order = ["time"] + [c for c in df.columns if c != "time"]
    df = df[cols_order]

    df.to_csv(filepath, index=False)
    return df

