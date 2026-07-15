#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jul 29 15:32:10 2025

@author: Mónica Sagastuy-Breña
"""

import pandas as pd

# Load data
autarky_df = pd.read_csv('heatmap_autarky.csv')
collab_df = pd.read_csv('heatmap_collaboration.csv')

def filter_by_country(country_code):
    # Combine country columns for search
    autarky_filtered = autarky_df[
        autarky_df[['country_1', 'country_2', 'country_3', 'country_4']].apply(lambda row: country_code in row.values, axis=1)
    ].copy()

    collab_filtered = collab_df[
        collab_df[['country_1', 'country_2', 'country_3', 'country_4']].apply(lambda row: country_code in row.values, axis=1)
    ].copy()

    # Add a country combination key for merging
    def create_key(row):
        return tuple(sorted([str(c) for c in row[['country_1', 'country_2', 'country_3', 'country_4']].dropna()]))

    autarky_filtered['country_key'] = autarky_filtered.apply(create_key, axis=1)
    collab_filtered['country_key'] = collab_filtered.apply(create_key, axis=1)

    # Merge on country_key
    merged = pd.merge(
        autarky_filtered[['country_key', 'Mitigation_Cost($/tCO2e)']],
        collab_filtered[['country_key', 'Mitigation_Cost($/tCO2e)']],
        on='country_key',
        how='outer',
        suffixes=('_autarky', '_collaboration')
    )

    # Export to CSV
    output_filename = f"mitigation_cost_comparisons/{country_code}.csv"
    merged.to_csv(output_filename, index=False)

    print(f"Mitigation cost comparison for country: {country_code}")
    print(f"Exported to file: {output_filename}\n")
    print(merged)

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python compare_mitigation.py <country_code>")
    else:
        filter_by_country(sys.argv[1])


