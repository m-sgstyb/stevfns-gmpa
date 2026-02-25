#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Nov  4 17:38:43 2021

@author: aniqahsan
"""

import pandas as pd
import time
import os
import cvxpy as cp
import sys
import warnings

warnings.simplefilter(action='ignore', category=FutureWarning) # To silence pandas concat future warning
"""FutureWarning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes. To retain the old behavior, exclude the relevant entries before the concat operation.
  total_data_df = pd.concat([total_data_df, t_df], ignore_index=True)"""

from Code.Network.Network import Network_STEVFNs
from Code.Results import GMPA_Results
from Code.Plotting import GMPA_plot_mitigation_curve
from Code.Plotting import testing_plots

#### Define Input Files ####
case_study_name = "02_testing_industry"
# case_study_name = os.getenv("CASE_STUDY_NAME")
if not case_study_name:
    raise ValueError("CASE_STUDY_NAME environment variable not set. Exiting.")

base_folder = os.path.dirname(__file__)
data_folder = os.path.join(base_folder, "Data")
case_study_folder = os.path.join(data_folder, "Case_Study", case_study_name)
scenario_folders_list = [x[0] for x in os.walk(case_study_folder)][1:]
network_structure_filename = os.path.join(case_study_folder, "Network_Structure.csv")
results_filename = os.path.join(case_study_folder, "total_data.csv")
website_total_data_filename = os.path.join(case_study_folder, "total_data_unrounded.csv")
capacities_filename = os.path.join(case_study_folder, "capacities_total_data.csv")
unrounded_results_filename = os.path.join(case_study_folder, "internal_total_data.csv")


### Read Input Files ###

network_structure_df = pd.read_csv(network_structure_filename)

### Build Network ###
print("========================== Building ==========================")
start_time0 = time.time()
my_network = Network_STEVFNs()
my_network.build(network_structure_df)


end_time = time.time()
print("Time taken to build network = ", end_time - start_time0, "s")
# total_df = pd.DataFrame()
# total_df_1 = pd.DataFrame()

for counter1 in range(len(scenario_folders_list)):
# for counter1 in range(1):
    # Read Input Files ###
    scenario_folder = scenario_folders_list[-1-counter1]
    asset_parameters_filename = os.path.join(scenario_folder, "Asset_Parameters.csv")
    location_parameters_filename = os.path.join(scenario_folder, "Location_Parameters.csv")
    system_parameters_filename = os.path.join(scenario_folder, "System_Parameters.csv")
    
    asset_parameters_df = pd.read_csv(asset_parameters_filename)
    location_parameters_df = pd.read_csv(location_parameters_filename)
    system_parameters_df = pd.read_csv(system_parameters_filename)
    my_network.scenario_name = os.path.basename(scenario_folder)
    print(f"\n================== Updating for Scenario {my_network.scenario_name} ==================\n")
    ### Update Network Parameters ###
    start_time = time.time()
    
    my_network.update(location_parameters_df, asset_parameters_df, system_parameters_df)
    # my_network.scenario_name = os.path.basename(scenario_folder)
    
    end_time = time.time()
    print("Time taken to update network = ", end_time - start_time, "s")
    
    ### Run Simulation ###
    start_time = time.time()
    solver_name = os.getenv("SOLVER_NAME", "CLARABEL").upper() # Make Clarabel default if running without wrapper run_cases.py
    if solver_name == "CLARABEL":
        my_network.problem.solve(solver=cp.CLARABEL, max_iter=100000, ignore_dpp=True)
    elif solver_name == "MOSEK":
        my_network.problem.solve(solver=cp.MOSEK, ignore_dpp=True)
    else:
        raise ValueError(f"Unknown solver: {solver_name}")
    # my_network.problem.solve(solver = cp.CLARABEL, max_iter=10000, ignore_dpp=True) # ignore_dpp=True because problem has too many params
    # my_network.problem.solve(solver = cp.MOSEK, ignore_dpp=True)
    end_time = time.time()
    
    ### Print status, key results and save output files ############
    print(f"----------------- Scenario {my_network.scenario_name} Main Results ----------------------\n")
    print("Time taken to solve problem = ", end_time - start_time, "s")
    print(my_network.problem.solution.status)
    if my_network.problem.value == float("inf"):
        continue
    print("Total cost to satisfy all demand = ", my_network.problem.value, " Billion USD")
    print("Total emissions = ", my_network.assets[0].asset_size(), "MtCO2e")

    ### Export cost results to pandas dataframe per scenario and concat all scenarios
    t_df = GMPA_Results.export_total_data(my_network, location_parameters_df, asset_parameters_df)
    t1_df = GMPA_Results.export_total_data_not_rounded(my_network, location_parameters_df, asset_parameters_df)
    capacities_df = GMPA_Results.export_total_data_capacities(my_network, location_parameters_df, asset_parameters_df)
    web_td_df = GMPA_Results.export_total_data_website(my_network, location_parameters_df, asset_parameters_df)
    if counter1 == 0:
        total_df = t_df
        total_df_1 = t1_df
        total_cap_df = capacities_df
        web_total_df = web_td_df
    else:
        total_df = pd.concat([total_df, t_df], ignore_index=True)
        total_df_1 = pd.concat([total_df_1, t1_df], ignore_index=True)
        total_cap_df = pd.concat([total_cap_df, capacities_df], ignore_index=True)
        web_total_df = pd.concat([web_total_df, web_td_df], ignore_index=True)
        
        
    
        
# #### Save Result
total_df.to_csv(results_filename, index=False, header=True)
total_df_1.to_csv(unrounded_results_filename, index=False, header=True)
total_cap_df.to_csv(capacities_filename, index=False, header=True)
# Exports total_data_unrounded with wind bins aggregated into one asset
web_total_df.to_csv(website_total_data_filename, index=False, header=True)
    

#### Plot data
# Run the plotting script after main processing
base_cases = ["BAU_No_Action", "Least_Cost_Emissions"]
if case_study_name not in base_cases:
    dpacc_name = os.path.join(case_study_folder, "mitigation_curve.png")
    subplots_name = os.path.join(case_study_folder, "dpacc_subplots.png")
    GMPA_plot_mitigation_curve.mitigation_curve(
        website_total_data_filename,
        dpacc_name,
        case_study_name,
        countries=["KE", "NG", "CO", "PE", "KR", "VN", "LA", "TH", "PH", "ID", "MY", "FR","AU",
                   "DE", "FR", "TR", "MA"],
    )
    GMPA_plot_mitigation_curve.dpacc_subplots(
        website_total_data_filename,
        capacities_filename,
        subplots_name,
        case_study_name,
        countries=["KE", "NG", "CO", "PE", "KR", "VN", "LA", "TH", "PH", "ID", "MY","AU",
                   "DE", "FR", "TR", "MA"],
    )


if "testing" in case_study_name:
    output_folder = os.path.join(base_folder, "Code", "Plotting", "Testing_Plots")
    csv_results = os.path.join(base_folder, "Code", "Plotting", "Testing_Plots", "hourly_flows.csv")
    results_df = testing_plots.export_results_csv(my_network, csv_results, hours=720)
    testing_plots.plot_stacked_from_df(results_df, output_folder)
        
final_time = time.time()
print("------------------  All Scenarios Run  ------------------------\n",
      "Time to build network, run all scenarios, export and plot data",
      (final_time - start_time0)/60, "min")
   