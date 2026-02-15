#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Feb  9 11:13:27 2026

@author: Mónica Sagastuy-Breña

Script with plotting functions for testing assets
    1. Hourly dispatch plots
"""

import os
from collections import defaultdict
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

def simple_plot_pp_phs_demand_generic(my_network, location_parameters_df, output_folder,
                                      cmap_name="tab20", expected_timesteps=None, verbose=False):
    """
    Generic single-run plotting for PP (many subtypes), PHS, and Demand.
    - Skips assets with 'co2_budget' in the name (case-insensitive)
    - Reads flows from obj.flows.value (or obj.flows)
    - Detects PHS by 'phs' in asset_name OR by assets_dictionary keys/values containing pump/turb substrings
    - Each PP subtype (e.g. PP_COAL_CO2) gets its own color from the colormap.
    - PHS turbine drawn as opaque filled area; pumping as same color with lower alpha.
    - Saves one PNG per location with demand.
    """
    os.makedirs(output_folder, exist_ok=True)

    def _asset_name_lower(asset):
        return (getattr(asset, "asset_name", "") or "").strip()

    def _asset_name_key(asset):
        # normalized lowercase key for quick contains checks
        return _asset_name_lower(asset).lower()

    def _safe_get_flows_value(obj):
        """Return a 1D numpy array from obj.flows.value if possible, else obj.flows if possible, else None."""
        if obj is None:
            return None
        if not hasattr(obj, "flows"):
            return None
        flows = getattr(obj, "flows")
        # prefer `.value`
        if hasattr(flows, "value"):
            try:
                arr = np.asarray(flows.value).astype(float).flatten()
                return arr
            except Exception:
                pass
        try:
            arr = np.asarray(flows).astype(float).flatten()
            return arr
        except Exception:
            return None

    # Storage: per-location maps
    pp_by_loc = defaultdict(lambda: defaultdict(list))   # loc -> { pp_subtype_label -> [arrays...] }
    phs_pump_by_loc = defaultdict(list)                  # loc -> [pump arrays]
    phs_turb_by_loc = defaultdict(list)                  # loc -> [turbine arrays]
    demand_by_loc = {}                                   # loc -> demand array

    # ---- Collect all arrays ----
    for idx, asset in enumerate(my_network.assets):
        name_raw = _asset_name_lower(asset)
        name = name_raw  # keep case for subtype display
        name_key = _asset_name_key(asset)
        if not name:
            if verbose:
                print(f"asset idx {idx}: no name, skipping")
            continue

        # skip CO2_BUDGET assets
        if "co2_budget" in name_key:
            if verbose:
                print(f"asset '{name}' -> skipped (CO2_BUDGET)")
            continue

        # find location id
        loc = getattr(asset, "target_node_location", getattr(asset, "node_location", None))
        if loc is None:
            if verbose:
                print(f"asset '{name}' -> no location, skipping")
            continue

        # Demand (detect by 'demand' substring)
        if "demand" in name_key:
            arr = _safe_get_flows_value(asset)
            if arr is not None:
                demand_by_loc[loc] = arr
                if verbose:
                    print(f"asset '{name}' -> stored demand (loc {loc}, len {len(arr)})")
            else:
                if verbose:
                    print(f"asset '{name}' -> demand asset but no flows found")
            continue

        # Detect PHS: name contains 'phs' OR assets_dictionary keys/values include 'pump'/'turb'
        ad = getattr(asset, "assets_dictionary", None)
        ad_is_dict = isinstance(ad, dict)
        is_phs = False
        pump_obj = None
        turb_obj = None

        if "phs" in name_key:
            is_phs = True

        if ad_is_dict:
            # quick key substring match
            for k in ad.keys():
                kl = k.lower()
                if "pump" in kl and pump_obj is None:
                    pump_obj = ad[k]
                    is_phs = True
                if "turb" in kl and turb_obj is None:
                    turb_obj = ad[k]
                    is_phs = True
            # if keys didn't match, try values: pick first value with .flows for pump/turb roles
            if not (pump_obj and turb_obj):
                for k, v in ad.items():
                    if pump_obj is None and hasattr(v, "flows"):
                        # prefer ones whose key contains pump
                        pump_obj = pump_obj or v
                    if turb_obj is None and hasattr(v, "flows"):
                        turb_obj = turb_obj or v

        if is_phs:
            # attempt to extract arrays from chosen objects
            pump_arr = _safe_get_flows_value(pump_obj)
            turb_arr = _safe_get_flows_value(turb_obj)
            if verbose:
                print(f"asset '{name}' -> PHS detected (loc {loc}) pump={'yes' if pump_arr is not None else 'no'} turb={'yes' if turb_arr is not None else 'no'}")
            if pump_arr is not None:
                phs_pump_by_loc[loc].append(pump_arr)
            if turb_arr is not None:
                phs_turb_by_loc[loc].append(turb_arr)
            continue

        # Otherwise, classify as PP if name contains 'pp' OR startswith 'pp_'
        if "pp" in name_key or name_key.startswith("pp_") or name_key.startswith("pp"):
            # Use the raw asset name (normalized) as the PP subtype label so different PPs get different colors
            # Normalize label to a short readable token: remove spaces and keep as-is
            pp_label = name.strip()
            arr = _safe_get_flows_value(asset)
            if arr is not None:
                pp_by_loc[loc][pp_label].append(arr)
                if verbose:
                    print(f"asset '{name}' -> PP subtype '{pp_label}' stored (loc {loc}, len {len(arr)})")
            else:
                if verbose:
                    print(f"asset '{name}' -> classified as PP but no flows found")
            continue

        # If not matched, optionally try to treat other generation-like assets as PP (heuristic)
        # e.g., names containing 'plant' or 'generator'
        if "plant" in name_key or "generator" in name_key:
            pp_label = name.strip()
            arr = _safe_get_flows_value(asset)
            if arr is not None:
                pp_by_loc[loc][pp_label].append(arr)
                if verbose:
                    print(f"asset '{name}' -> treated as PP subtype '{pp_label}' (fallback)")
            continue

        # else ignore
        if verbose:
            print(f"asset '{name}' -> ignored (not demand, not PHS, not PP)")

    # ---- Now produce plots per location that have demand ----
    saved_paths = []
    all_locs_with_data = sorted(
        set(demand_by_loc.keys())
        | set(pp_by_loc.keys())
        | set(phs_pump_by_loc.keys())
        | set(phs_turb_by_loc.keys())
    )

    if verbose:
        print("Locations with any data:", all_locs_with_data)

    for loc in all_locs_with_data:
        if loc not in demand_by_loc:
            if verbose:
                print(f"loc {loc} has flows but no demand -> skipping plot")
            continue

        demand = demand_by_loc[loc]
        T = int(len(demand)) if expected_timesteps is None else int(expected_timesteps)

        def _norm(a):
            a = np.asarray(a).flatten()
            if a.shape[0] == T:
                return a.astype(float)
            if a.shape[0] > T:
                return a[:T].astype(float)
            return np.pad(a.astype(float), (0, T - a.shape[0]), constant_values=0.0)

        # Build PP totals per subtype and collect labels for color mapping
        pp_subtypes = sorted(pp_by_loc.get(loc, {}).keys())
        # flatten per-subtype totals
        pp_totals_by_subtype = {}
        for subtype in pp_subtypes:
            total = np.zeros(T, dtype=float)
            for arr in pp_by_loc[loc][subtype]:
                total += _norm(arr)
            pp_totals_by_subtype[subtype] = total

        # PHS totals
        turb_total = np.zeros(T, dtype=float)
        for a in phs_turb_by_loc.get(loc, []):
            turb_total += _norm(a)
        pump_total = np.zeros(T, dtype=float)
        for a in phs_pump_by_loc.get(loc, []):
            pump_total += _norm(a)

        # Setup color mapping for PP subtypes (consistent order)
        n_pp = max(1, len(pp_subtypes))
        cmap = plt.get_cmap(cmap_name)
        pp_colors = {}
        for i, subtype in enumerate(pp_subtypes):
            pp_colors[subtype] = cmap(float(i) / max(1, n_pp - 1))

        # Choose PHS base color: if there is a PP subtype called "PHS" use that color; else pick next cmap entry
        if "PHS" in pp_subtypes:
            phs_color = pp_colors["PHS"]
        else:
            # pick a color distinct from PP colors
            phs_color = cmap(float(len(pp_subtypes)) / max(1, n_pp - 1))

        # Start plotting
        x = np.arange(T)
        bottom = np.zeros(T, dtype=float)

        plt.figure(figsize=(12, 5))

        # Plot PP subtypes in stable order
        for subtype in pp_subtypes:
            arr = pp_totals_by_subtype[subtype]
            if not np.any(arr):
                continue
            c = pp_colors.get(subtype, cmap(0))
            label = subtype
            plt.fill_between(x, bottom, bottom + arr, color=c, label=label, edgecolor='none', alpha=1.0)
            bottom += arr

        # Plot PHS turbine (generation) using phs_color at full alpha
        if np.any(turb_total):
            plt.fill_between(x, bottom, bottom + turb_total, color=phs_color, label="PHS Turbine (discharge)", edgecolor='none', alpha=1.0)
            bottom += turb_total

        # Plot PHS pumping as translucent fill (same base color but lower alpha) to indicate directionality
        if np.any(pump_total):
            plt.fill_between(x, bottom, bottom + pump_total, color=phs_color, label="PHS Pumping (charge)", edgecolor='none', alpha=0.35)

        # Demand line
        plt.plot(x, _norm(demand), color="red", linestyle="--", linewidth=1.4, label="Demand")

        plt.xlabel("Timestep")
        plt.ylabel("Power")
        loc_name = location_parameters_df.iloc[loc]["location_name"]
        plt.title(f"{loc_name} — PP subtypes + PHS vs Demand")
        plt.grid(True, linestyle=":", alpha=0.4)
        plt.legend(loc="upper right", fontsize="small", ncol=2)
        plt.tight_layout()

        outpath = os.path.join(output_folder, f"stacked_{loc_name}.png")
        plt.savefig(outpath, dpi=300)
        plt.close()
        saved_paths.append(outpath)
        if verbose:
            print(f"[✓] Saved: {outpath}")

    # warn about locations with flows but no demand
    all_locations_with_any = set(list(pp_by_loc.keys()) + list(phs_pump_by_loc.keys()) + list(phs_turb_by_loc.keys()) + list(demand_by_loc.keys()))
    locations_without_plots = sorted([loc for loc in all_locations_with_any if loc not in demand_by_loc])
    if locations_without_plots:
        print("⚠️ The following location IDs had flows but no demand asset (no plot created):", locations_without_plots)

    return saved_paths



def export_results_csv(network, filepath, hours=720):
    """
    Very simple results export.
    Assumes all flows are already numpy arrays.
    """

    # --- DEMAND ---
    demand = None
    for asset in network.assets:
        if "Demand" in asset.asset_name:
            demand = asset.flows.value[:hours]
            break

    # --- POWER PLANTS (sum all PP assets) ---
    pp = np.zeros(hours)
    for asset in network.assets:
        if asset.asset_name.startswith("PP"):
            pp += asset.flows.value[:hours]

    # --- PHS ---
    pumping = None
    turbine = None
    soc = None

    for asset in network.assets:
        if asset.asset_name == "PHS":
            pumping = asset.assets_dictionary["Pumping"].flows.value[:hours]
            turbine = asset.assets_dictionary["Turbine"].flows.value[:hours]
            soc = asset.assets_dictionary["Reservoir"].flows.value[:hours]
            break

    # --- BUILD DATAFRAME ---
    df = pd.DataFrame({
        "time": np.arange(hours),
        "demand": demand,
        "pp": pp,
        "pumping": pumping,
        "turbine": turbine,
        "soc": soc
    })

    df.to_csv(filepath, index=False)
    return df
