import pandas as pd
import os
import shutil
import subprocess
import sys

def add_new_country():
    # File paths
    input_csv_path = 'new_country_input.csv'
    location_params_path = 'Data/Case_Study/0_BASEAUTARKY/BAU/Location_Parameters.csv'

    # Check if input file exists
    if not os.path.exists(input_csv_path):
        print(f"Error: {input_csv_path} not found.")
        return

    # Read input data
    try:
        new_country_df = pd.read_csv(input_csv_path)
    except Exception as e:
        print(f"Error reading {input_csv_path}: {e}")
        return

    # Check if country already exists
    if os.path.exists(location_params_path):
        try:
            loc_df = pd.read_csv(location_params_path)
            existing_countries = loc_df['location_name'].astype(str).values
            for _, row in new_country_df.iterrows():
                if row['country_code'] in existing_countries:
                    print(f"Country {row['country_code']} already exists in {location_params_path}. Skipping.")
                    return
        except Exception as e:
            print(f"Error checking existing countries: {e}")
            return

    if new_country_df.empty:
        print("Error: Input CSV is empty.")
        return

    # Read existing location parameters
    try:
        location_params_df = pd.read_csv(location_params_path)
    except Exception as e:
        print(f"Error reading {location_params_path}: {e}")
        return

    # Get the last location ID
    if not location_params_df.empty:
        last_id = location_params_df['Location'].max()
    else:
        last_id = -1

    new_locations = []
    country_id_map = {}
    
    # Process each new country
    for index, row in new_country_df.iterrows():
        new_id = last_id + 1
        last_id = new_id
        country_id_map[row['country_code']] = new_id
        
        new_entry = {
            'Location': new_id,
            'lat': row['lat'],
            'lon': row['lon'],
            'location_name': row['country_code']
        }
        new_locations.append(new_entry)
        print(f"Added {row['country_code']} with Location ID: {new_id}")

    # Append new locations
    if new_locations:
        new_locations_df = pd.DataFrame(new_locations)
        # Ensure columns match
        new_locations_df = new_locations_df[location_params_df.columns]
        
        # Check if file ends with newline
        with open(location_params_path, 'rb+') as f:
            f.seek(0, 2)  # Seek to end of file
            if f.tell() > 0:
                f.seek(-1, 2)
                last_char = f.read(1)
                if last_char != b'\n':
                    f.write(b'\n')

        # Append to file
        new_locations_df.to_csv(location_params_path, mode='a', header=False, index=False)
        print(f"Successfully added {len(new_locations)} new locations to {location_params_path}")

    # Process assets
    assets_csv_path = 'new_country_assets_input.csv'
    if os.path.exists(assets_csv_path):
        process_assets(assets_csv_path, new_country_df)

    # Process BAU_No_Action
    process_case_study_folder(new_country_df, country_id_map, 'BAU_No_Action')
    # Process Least_Cost_Emissions
    process_case_study_folder(new_country_df, country_id_map, 'Least_Cost_Emissions')

    # Run Simulations
    print("\nRunning BAU_No_Action simulation...")
    try:
        subprocess.run([sys.executable, "run_cases.py", "bau"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running BAU simulation: {e}")

    print("\nRunning Least_Cost_Emissions simulation...")
    try:
        subprocess.run([sys.executable, "run_cases.py", "least"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running Least Cost simulation: {e}")

    # Run Carbon Budget Generation
    print("\nGenerating Carbon Budget...")
    try:
        # Run generate_carbon_budget.py and pass 'n' to the prompt
        # Script expects to be run from Code/Automations due to relative paths
        automations_dir = os.path.join(os.getcwd(), 'Code', 'Automations')
        subprocess.run(
            [sys.executable, "generate_carbon_budget.py"],
            input="n\n",
            text=True,
            check=True,
            cwd=automations_dir
        )
    except subprocess.CalledProcessError as e:
        print(f"Error running Carbon Budget generation: {e}")

    # Process Autarky Case Study
    process_autarky_case(new_country_df, country_id_map)

    # Run Update Scripts
    print("\nRunning Update Scripts...")
    automations_dir = os.path.join(os.getcwd(), 'Code', 'Automations')
    
    # Run update_aut_scenarios.py
    for _, row in new_country_df.iterrows():
        country_code = row['country_code']
        print(f"Running update_aut_scenarios.py for {country_code}...")
        try:
            subprocess.run(
                [sys.executable, "update_aut_scenarios.py", country_code],
                check=True,
                cwd=automations_dir
            )
        except subprocess.CalledProcessError as e:
            print(f"Error running update_aut_scenarios.py: {e}")

    # Run update_co2_budget_asset_types.py
    print("Running update_co2_budget_asset_types.py...")
    try:
        subprocess.run(
            [sys.executable, "update_co2_budget_asset_types.py"],
            check=True,
            cwd=automations_dir
        )
    except subprocess.CalledProcessError as e:
        print(f"Error running update_co2_budget_asset_types.py: {e}")

    # Run Autarky Simulation
    for _, row in new_country_df.iterrows():
        country_code = row['country_code']
        print(f"\nRunning Autarky simulation for {country_code}...")
        try:
            subprocess.run(
                [sys.executable, "run_cases.py", country_code],
                check=True,
                cwd=os.getcwd()
            )
        except subprocess.CalledProcessError as e:
            print(f"Error running Autarky simulation for {country_code}: {e}")

    # Run Prepare Data for Website
    print("\nRunning prepare_data_for_website.py...")
    try:
        subprocess.run(
            [sys.executable, "prepare_data_for_website.py"],
            check=True,
            cwd=automations_dir
        )
    except subprocess.CalledProcessError as e:
        print(f"Error running prepare_data_for_website.py: {e}")

def process_autarky_case(new_country_df, country_id_map):
    base_source_dir = 'Data/Case_Study/0_BASEAUTARKY'
    
    if not os.path.exists(base_source_dir):
        print(f"Warning: Source directory {base_source_dir} not found. Skipping Autarky processing.")
        return

    for _, row in new_country_df.iterrows():
        country_code = row['country_code']
        country_id = country_id_map.get(country_code)
        
        if country_id is None:
            print(f"Warning: No ID found for {country_code}, skipping Autarky processing.")
            continue

        target_dir = os.path.join('Data/Case_Study', f'Autarky_{country_code}')
        
        # Copy directory
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir)
        shutil.copytree(base_source_dir, target_dir)
        print(f"Copied Autarky case from {base_source_dir} to {target_dir}")
        
        # Update Network_Structure.csv
        net_struct_path = os.path.join(target_dir, 'Network_Structure.csv')
        if os.path.exists(net_struct_path):
            try:
                df = pd.read_csv(net_struct_path)
                df['Location_1'] = country_id
                df['Location_2'] = country_id
                df.to_csv(net_struct_path, index=False)
                print(f"Updated {net_struct_path}")
            except Exception as e:
                print(f"Error updating {net_struct_path}: {e}")

        # Update BAU/Asset_Parameters.csv
        bau_asset_path = os.path.join(target_dir, 'BAU', 'Asset_Parameters.csv')
        if os.path.exists(bau_asset_path):
            try:
                df = pd.read_csv(bau_asset_path)
                df['Location_1'] = country_id
                df['Location_2'] = country_id
                # Change Asset_Type to country_id where Asset_Class is not CO2_Budget
                df.loc[df['Asset_Class'] != 'CO2_Budget', 'Asset_Type'] = country_id
                # Ensure Asset_Type is integer
                df['Asset_Type'] = df['Asset_Type'].astype(int)
                df.to_csv(bau_asset_path, index=False)
                print(f"Updated {bau_asset_path}")
            except Exception as e:
                print(f"Error updating {bau_asset_path}: {e}")



def process_case_study_folder(new_country_df, country_id_map, folder_name):
    base_dir = os.path.join('Data/Case_Study', folder_name)
    source_country = 'JP'
    
    if not os.path.exists(os.path.join(base_dir, source_country)):
        print(f"Warning: Source directory {os.path.join(base_dir, source_country)} not found. Skipping {folder_name} processing.")
        return

    import shutil

    for _, row in new_country_df.iterrows():
        country_code = row['country_code']
        country_id = country_id_map.get(country_code)
        
        if country_id is None:
            print(f"Warning: No ID found for {country_code}, skipping {folder_name} processing.")
            continue

        target_dir = os.path.join(base_dir, country_code)
        
        # Copy directory
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir)
        shutil.copytree(os.path.join(base_dir, source_country), target_dir)
        print(f"Copied {folder_name} from {source_country} to {country_code}")
        
        # Update Asset_Parameters.csv
        asset_params_path = os.path.join(target_dir, 'Asset_Parameters.csv')
        if os.path.exists(asset_params_path):
            try:
                df = pd.read_csv(asset_params_path)
                # Change Asset_Type to country_id where Asset_Class is not CO2_Budget
                df.loc[df['Asset_Class'] != 'CO2_Budget', 'Asset_Type'] = country_id
                # Ensure Asset_Type is integer
                df['Asset_Type'] = df['Asset_Type'].astype(int)
                df.to_csv(asset_params_path, index=False)
                print(f"Updated {asset_params_path}")
            except Exception as e:
                print(f"Error updating {asset_params_path}: {e}")
        
        # Update Location_Parameters.csv
        loc_params_path = os.path.join(target_dir, 'Location_Parameters.csv')
        if os.path.exists(loc_params_path):
            try:
                df = pd.read_csv(loc_params_path)
                # Update lat, lon, location_name
                # Location ID should remain 0 as per user request
                # df['Location'] = country_id
                df['lat'] = row['lat']
                df['lon'] = row['lon']
                df['location_name'] = country_code
                df.to_csv(loc_params_path, index=False)
                print(f"Updated {loc_params_path}")
            except Exception as e:
                print(f"Error updating {loc_params_path}: {e}")

def process_assets(assets_csv_path, new_country_df):
    try:
        assets_df = pd.read_csv(assets_csv_path)
    except Exception as e:
        print(f"Error reading {assets_csv_path}: {e}")
        return

    if assets_df.empty:
        print("Warning: Assets CSV is empty.")
        return
    
    # Create a mapping of country code to lat/lon
    country_coords = {}
    for _, row in new_country_df.iterrows():
        country_coords[row['country_code']] = (row['lat'], row['lon'])

    for _, row in assets_df.iterrows():
        asset_name = row['asset_name']
        asset_dir = os.path.join('Code', 'Assets', asset_name)
        params_path = os.path.join(asset_dir, 'parameters.csv')
        
        if not os.path.exists(params_path):
            print(f"Warning: Parameters file not found for {asset_name} at {params_path}")
            continue
            
        try:
            params_df = pd.read_csv(params_path)
        except Exception as e:
            print(f"Error reading {params_path}: {e}")
            continue
            
        # Prepare new rows for each new country
        new_rows = []
        for country_code, (lat, lon) in country_coords.items():
            new_row = row.copy()
            new_row['location_name'] = country_code
            
            # Remove columns not in the target parameters file
            # But first, handle profile if needed
            if 'profile_path' in row and pd.notna(row['profile_path']):
                profile_src = row['profile_path']
                re_type = row.get('RE_type')
                
                # Determine profile destination based on asset type
                if 'Demand' in asset_name:
                    # Demand Asset Logic
                    # Expected format: profiles/[COUNTRY_CODE]_2050_GW.csv
                    # We need to construct the filename. 
                    # Check parameters.csv to see if it expects a specific column for filename
                    # In EL_Demand/parameters.csv, there is 'profile_filename' column.
                    
                    # Default year
                    year = '2050' 
                    # Try to extract year from source filename if possible, or use default
                    
                    dest_filename = f"{country_code}_{year}_GW.csv"
                    dest_dir = os.path.join(asset_dir, 'profiles')
                    if not os.path.exists(dest_dir):
                        os.makedirs(dest_dir)
                    
                    dest_path = os.path.join(dest_dir, dest_filename)
                    
                    # Update row data if 'profile_filename' is a column
                    if 'profile_filename' in params_df.columns:
                        # The parameters file seems to store the filename WITHOUT extension in some cases?
                        # Let's check the example: SGP_2050_GW (no .csv)
                        # So we should strip extension for the CSV entry
                        new_row['profile_filename'] = dest_filename.replace('.csv', '')
                    
                    # Copy file
                    if os.path.exists(profile_src):
                        import shutil
                        shutil.copy2(profile_src, dest_path)
                        print(f"Copied demand profile to {dest_path}")
                    else:
                        print(f"Warning: Source profile {profile_src} not found.")
                        
                elif pd.notna(re_type):
                    # RE Asset Logic
                    # Calculate rounded coordinates
                    import numpy as np
                    
                    r_lat = np.int64(np.round((lat) / 0.5)) * 0.5
                    r_lat = min(r_lat, 90.0)
                    r_lat = max(r_lat, -90.0)
                    
                    r_lon = np.int64(np.round((lon) / 0.625)) * 0.625
                    r_lon = min(r_lon, 179.375)
                    r_lon = max(r_lon, -180.0)
                    
                    profile_dir_name = re_type # e.g. PVOUT or WINDOUT
                    
                    # Construct destination path
                    dest_dir = os.path.join(asset_dir, 'profiles', profile_dir_name, f'lat{r_lat}')
                    if not os.path.exists(dest_dir):
                        os.makedirs(dest_dir)
                        
                    dest_filename = f'{profile_dir_name}_lat{r_lat}_lon{r_lon}.csv'
                    dest_path = os.path.join(dest_dir, dest_filename)
                    
                    # Copy file
                    if os.path.exists(profile_src):
                        import shutil
                        shutil.copy2(profile_src, dest_path)
                        print(f"Copied RE profile to {dest_path}")
                    else:
                        print(f"Warning: Source profile {profile_src} not found.")
                else:
                    print(f"Warning: Unknown profile type for {asset_name}. Skipping profile copy.")

            # Filter columns to match target
            valid_cols = [col for col in new_row.index if col in params_df.columns]
            filtered_row = new_row[valid_cols]
            
            # Ensure all required columns are present (fill with defaults or NaN if missing in input but present in target)
            # For now, we assume input has what's needed or we rely on pandas alignment
            
            # We need to construct a DataFrame to append. 
            # It's safer to create a dict and then DataFrame
            row_dict = filtered_row.to_dict()
            
            # Add any missing columns from params_df as NaN (or handle specifically if needed)
            for col in params_df.columns:
                if col not in row_dict:
                    # Special handling for Type/ID if it's an auto-increment integer?
                    # The existing files seem to have 'Type' as an ID.
                    if col == 'Type':
                         if not params_df.empty and pd.api.types.is_numeric_dtype(params_df['Type']):
                             last_type_id = params_df['Type'].max()
                             # This logic is tricky if we are adding multiple countries. 
                             # We should probably handle this outside the loop or dynamically.
                             # For now, let's assume we append and fix IDs later or rely on max()
                             pass 
                    else:
                        row_dict[col] = None # or some default
            
            new_rows.append(row_dict)

        if new_rows:
            new_rows_df = pd.DataFrame(new_rows)
            
            # Handle Type ID auto-increment
            if 'Type' in params_df.columns and pd.api.types.is_numeric_dtype(params_df['Type']):
                start_id = params_df['Type'].max() + 1 if not params_df.empty else 0
                new_rows_df['Type'] = range(start_id, start_id + len(new_rows_df))
            
            # Align columns
            new_rows_df = new_rows_df[params_df.columns]
            
            # Check for newline
            with open(params_path, 'rb+') as f:
                f.seek(0, 2)
                if f.tell() > 0:
                    f.seek(-1, 2)
                    last_char = f.read(1)
                    if last_char != b'\n':
                        f.write(b'\n')

            new_rows_df.to_csv(params_path, mode='a', header=False, index=False)
            print(f"Added {len(new_rows_df)} rows to {params_path}")


if __name__ == "__main__":
    add_new_country()
