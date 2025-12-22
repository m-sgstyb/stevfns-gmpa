"""
Workflow script to run collaboration scenarios for a set of countries.
This script automates the generation of carbon budgets, case studies, 
running simulations, and preparing data for the website.
"""

import csv
import sys
import subprocess
import os

def run_collab_workflow(input_csv):
    """
    Reads country combinations from a CSV and executes the full collaboration workflow.
    
    Steps for each combination:
    1. Generate Carbon Budget (Code/Automations/generate_carbon_budget.py)
    2. Generate Collab Case Studies (Code/Automations/generate_collab_case_studies.py)
    3. Run Simulations (run_cases.py)
    4. Prepare Data for Website (Code/Automations/prepare_data_for_website.py)
    """
    try:
        with open(input_csv, 'r') as f:
            reader = csv.reader(f)
            rows = list(reader)
    except Exception as e:
        print(f"Error reading {input_csv}: {e}")
        return

    automations_dir = os.path.join(os.getcwd(), 'Code', 'Automations')

    for row in rows:
        countries = [c.strip().upper() for c in row if c.strip()]
        
        if len(countries) < 2:
            print(f"Skipping row {row}: need at least 2 countries.")
            continue
        
        print(f"\nProcessing collaboration for: {', '.join(countries)}")
        
        # Step 1: Generate Carbon Budget
        print("Running generate_carbon_budget.py...")
        countries_str = ",".join(countries)
        input_str = f"y\n{countries_str}\nn\n"
        
        try:
            subprocess.run(
                [sys.executable, "generate_carbon_budget.py"],
                input=input_str,
                text=True,
                check=True,
                cwd=automations_dir
            )
        except subprocess.CalledProcessError as e:
            print(f"Error running generate_carbon_budget.py: {e}")
            continue

        # Step 2: Generate Collab Case Studies
        print("Running generate_collab_case_studies.py...")
        args = [sys.executable, "generate_collab_case_studies.py", "."] + countries
        try:
            subprocess.run(
                args,
                check=True,
                cwd=automations_dir
            )
        except subprocess.CalledProcessError as e:
            print(f"Error running generate_collab_case_studies.py: {e}")
            continue

        # Step 3: Run Cases
        print("Running run_cases.py...")
        args = [sys.executable, "run_cases.py"] + countries
        try:
            subprocess.run(
                args,
                check=True,
                cwd=os.getcwd()
            )
        except subprocess.CalledProcessError as e:
            print(f"Error running run_cases.py: {e}")
            continue

    # Step 4: Prepare Data for Website
    print("\nRunning prepare_data_for_website.py...")
    try:
        subprocess.run(
            [sys.executable, "prepare_data_for_website.py"],
            check=True,
            cwd=automations_dir
        )
    except subprocess.CalledProcessError as e:
        print(f"Error running prepare_data_for_website.py: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_collab_workflow.py <input_csv>")
        sys.exit(1)
    
    input_csv = sys.argv[1]
    run_collab_workflow(input_csv)
