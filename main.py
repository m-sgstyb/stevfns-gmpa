#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pandas as pd
import time
import os
import cvxpy as cp
import sys
import warnings
 
warnings.simplefilter(action='ignore', category=FutureWarning) # To silence pandas concat future warning
"""FutureWarning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated.
In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes.
To retain the old behavior, exclude the relevant entries before the concat operation.
total_data_df = pd.concat([total_data_df, t_df], ignore_index=True)"""
 
from src.network.network import Network_STEVFNs
from src.results import GMPA_Results
from src.plotting import GMPA_plot_mitigation_curve
from src.plotting import testing_plots
from src.results.compile_results import (
    load_readable_names, compile_scenario_results, split_by_metric,
    join_capacities, aggregate_emissions_by_country, aggregate_costs_by_technology,
    compile_hourly_flows, append_and_save,
)

def main():
    #### Define Input Files ####
    case_study_name = os.getenv("CASE_STUDY_NAME")
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
        my_network.scenario_name = os.path.basename(scenario_folder)
 
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

        ### Node diagnostics
        # for idx, node in my_network.nodes_df.items():
        #     n_in, n_out = len(node.input_edges), len(node.output_edges)
        #     if n_in == 0 or n_out == 0:
        #         location, node_type, node_time = idx
        #         print(f"location={location} type={node_type} time={node_time}: "
        #             f"inputs={n_in} outputs={n_out}")

        ### Print status, key results and save output files ############
        print(f"----------------- Scenario {my_network.scenario_name} Main Results ----------------------\n")
        print("Time taken to solve problem = ", end_time - start_time, "s")
        print(my_network.problem.solution.status)
        if my_network.problem.value == float("inf"):
            continue
        print("Total cost to satisfy all demand = ", my_network.problem.value, " Billion USD")
        print("Total emissions = ", my_network.assets[3].asset_size(), "MtCO2e")

        # --- Export results --- #
        
        readable_names_df = load_readable_names(
        os.path.join(base_folder, "src", "results", "readable_names.csv"))
        dpacc_trajectories_filename = os.path.join(data_folder, "dpacc-trajectories.csv")
        hourly_flows_filename = os.path.join(data_folder, "hourly-flows.csv")

        scenario_results_df = compile_scenario_results(
            my_network=my_network,
            network_structure_df=network_structure_df,
            location_parameters_df=location_parameters_df,
            readable_names_df=readable_names_df,
            scenario_id=my_network.scenario_name,
            case_id=case_study_name, # change for just collab name later or re define the convention for GMPA results
            start_year=2025,
        )

        costs_df, emissions_df = split_by_metric(scenario_results_df)
        capacities_df = join_capacities(scenario_results_df)
        emissions_by_country_df = aggregate_emissions_by_country(emissions_df)
        technology_trajectories_df = aggregate_costs_by_technology(costs_df)
        append_and_save(technology_trajectories_df, dpacc_trajectories_filename)

        hourly_flows_df = compile_hourly_flows(
            my_network=my_network,
            network_structure_df=network_structure_df,
            location_parameters_df=location_parameters_df,
            readable_names_df=readable_names_df,
            scenario_id=my_network.scenario_name,
            case_id=case_study_name,
            start_year=2025,
        )
        append_and_save(hourly_flows_df, hourly_flows_filename)
        append_and_save(costs_df, os.path.join(data_folder, "costs-over-time.csv"))
        append_and_save(capacities_df, os.path.join(data_folder, "installed-cap-over-time.csv"))
        append_and_save(emissions_df, os.path.join(data_folder, "emissions-over-time.csv"))
        append_and_save(emissions_by_country_df, os.path.join(data_folder, "emissions-over-time-by-country.csv"))
        print("pv carryover", my_network.assets[1].carryover_out.value)
    
    final_time = time.time()

    print("------------------  All Scenarios Run  ------------------------\n",
          "Time to build network, run all scenarios, export and plot data",
          (final_time - start_time0)/60, "min")
 
 
 
if __name__ == "__main__":
    main()
 