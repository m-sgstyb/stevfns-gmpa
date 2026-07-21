#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jun 25 11:44:26 2025

@author: Mónica Sagastuy-Breña
Wrapper script to run main.py through CLI and not edit the script with hard coded details
"""

import subprocess
from itertools import combinations
import os
import argparse
import sys

def generate_case_study_names(countries, sub_only=False):
    """
    For GMPA-standardised ISO-2 country code case study names
    """

    countries = sorted([c.upper() for c in countries])
    case_study_names = []

    if len(countries) == 1:
        case_study_names.append(f"Autarky_{countries[0]}")
    elif len(countries) == 4 and not sub_only:
        joined = '-'.join(countries)
        case_study_names.append(f"{joined}_Autarky")
        case_study_names.append(f"{joined}_Collab")
        for r in range(2, 4):  # combinations of 2 and 3
            for combo in combinations(countries, r):
                joined_combo = '-'.join(combo)
                case_study_names.append(f"{joined_combo}_Autarky")
                case_study_names.append(f"{joined_combo}_Collab")
    elif len(countries) in [2, 3] or (len(countries) == 4 and sub_only):
        joined = '-'.join(countries)
        case_study_names.append(f"{joined}_Autarky")
        case_study_names.append(f"{joined}_Collab")
    else:
        raise ValueError("Enter 1, 2, 3, or 4 ISO country codes.")
    return case_study_names

def print_summary(error_log, success_message):
    if error_log:
        print("\nSUMMARY OF FAILED CASE STUDIES:")
        for case_name, error in error_log:
            print(f"- {case_name}: {error}")
    else:
        print(f"\n{success_message}")

def run_case(case_name, solver_name, error_log):
    print(f"\n--- Running: {case_name} with {solver_name} solver ---\n")
    env = os.environ.copy()
    env["CASE_STUDY_NAME"] = case_name
    env["SOLVER_NAME"] = solver_name.upper()
    try:
        subprocess.run([sys.executable, "main.py"], check=True, env=env)
    except subprocess.CalledProcessError as e:
        print(f"Error in {case_name}: {e}. Continuing...\n")
        error_log.append((case_name, str(e)))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run GMPA scenarios via CLI.")
    parser.add_argument(
        "input",
        nargs="+",
        help=(
            "1-4 ISO country codes, 'bau' / 'least', or (with --name) "
            "one or more literal, case-sensitive case study names."
        ),
    )
    parser.add_argument("--solver", choices=["mosek", "clarabel"], default="clarabel",
                         help="Choose solver (default: clarabel)")
    parser.add_argument("--sub", action="store_true",
                         help="Only run the specific country combo provided (no sub-combinations)")
    parser.add_argument(
        "--name", "--literal", dest="literal_name", action="store_true",
        help=(
            "Treat the input(s) as exact, case-sensitive case study name(s) "
            "to run directly, skipping country-code parsing/generation entirely."
        ),
    )
    args = parser.parse_args()
 
    error_log = []
 
    # --- Literal case study name mode (custom case study names) ---
    if args.literal_name:
        for case_name in args.input:
            run_case(case_name, args.solver, error_log)
        print_summary(error_log, "All case studies completed successfully.")
        sys.exit(1 if error_log else 0)
 
    # --- GMPA 'bau' / 'least' mode ---
    if len(args.input) == 1 and args.input[0].lower() in ["bau", "least"]:
        mapping = {
            "bau": "BAU_No_Action",
            "least": "Least_Cost_Emissions"
        }
        case_study_name = mapping[args.input[0].lower()]
        run_case(case_study_name, args.solver, error_log)
        print_summary(error_log, "Base scenario completed successfully.")
        sys.exit(1 if error_log else 0)
 
    # --- GMPA country-code combination mode ---
    try:
        case_study_list = generate_case_study_names(args.input, sub_only=args.sub)
    except ValueError as e:
        print(f"Input error: {e}")
        sys.exit(1)
 
    for case in case_study_list:
        run_case(case, args.solver, error_log)
 
    print_summary(error_log, "All case studies completed successfully.")
    sys.exit(1 if error_log else 0)
