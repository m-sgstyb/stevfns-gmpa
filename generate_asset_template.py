import os
import pandas as pd
import numpy as np

def generate_template(source_country='JP', target_country='JC'):
    assets_dir = os.path.join('Code', 'Assets')
    all_assets_data = []
    all_columns = set(['asset_name', 'profile_path', 'RE_type'])

    # Japan's approximate coordinates for profile search (from previous exploration)
    # Lat: 35.5, Lon: 139.375
    source_lat = 35.5
    source_lon = 139.375

    # Allowed assets whitelist
    allowed_assets = [
        'RE_PV_Openfield_Lim', 'RE_PV_Rooftop_Lim', 'RE_PV_Openfield_BAU',
        'RE_WIND_Onshore_Lim_0', 'RE_WIND_Onshore_Lim_1', 'RE_WIND_Onshore_Lim_2', 'RE_WIND_Onshore_Lim_3', 'RE_WIND_Onshore_Lim_4',
        'RE_WIND_Onshore_Lim_5', 'RE_WIND_Onshore_Lim_6', 'RE_WIND_Onshore_Lim_7', 'RE_WIND_Onshore_Lim_8', 'RE_WIND_Onshore_Lim_9',
        'RE_WIND_Onshore_BAU_0', 'RE_WIND_Onshore_BAU_1', 'RE_WIND_Onshore_BAU_2', 'RE_WIND_Onshore_BAU_3', 'RE_WIND_Onshore_BAU_4',
        'RE_WIND_Onshore_BAU_5', 'RE_WIND_Onshore_BAU_6', 'RE_WIND_Onshore_BAU_7', 'RE_WIND_Onshore_BAU_8', 'RE_WIND_Onshore_BAU_9',
        'RE_WIND_Offshore_Lim_0', 'RE_WIND_Offshore_Lim_1', 'RE_WIND_Offshore_Lim_2', 'RE_WIND_Offshore_Lim_3', 'RE_WIND_Offshore_Lim_4',
        'RE_WIND_Offshore_Lim_5', 'RE_WIND_Offshore_Lim_6', 'RE_WIND_Offshore_Lim_7', 'RE_WIND_Offshore_Lim_8', 'RE_WIND_Offshore_Lim_9',
        'HYDRO', 'PP_CO2', 'BESS',
        'EL_to_HTH', 'EL_to_NH3', 'NH3_Storage', 'NH3_to_EL', 'NH3_to_HTH', 'FF_to_HTH',
        'EL_Demand', 'HTH_Demand'
    ]

    # Iterate through all assets
    for asset_name in sorted(os.listdir(assets_dir)):
        if asset_name not in allowed_assets:
            continue
            
        if asset_name == 'CO2_Budget': # Redundant check but safe
            continue
            
        asset_path = os.path.join(assets_dir, asset_name)
        if not os.path.isdir(asset_path):
            continue
            
        params_path = os.path.join(asset_path, 'parameters.csv')
        if not os.path.exists(params_path):
            continue
            
        try:
            params_df = pd.read_csv(params_path)
            # Add columns to master list, filtering out 'Unnamed' columns
            valid_columns = [col for col in params_df.columns if not str(col).startswith('Unnamed')]
            all_columns.update(valid_columns)
            
            # Create a row for this asset
            row_data = {'asset_name': asset_name}
            
            # Find source country data
            # Check for 'JP' or 'JPN'
            source_row = params_df[params_df['location_name'].isin([source_country, 'JPN', 'Japan'])]
            
            if not source_row.empty:
                source_data = source_row.iloc[0].to_dict()
                
                # Copy data to row_data, filtering out Unnamed
                for k, v in source_data.items():
                    if k in valid_columns:
                        # Replace country code if it's a string
                        if isinstance(v, str):
                            if v == source_country:
                                row_data[k] = target_country
                            elif v == 'JPN':
                                row_data[k] = target_country # or 'JCN'? Let's stick to target_country for simplicity or user instruction
                            elif v == 'Japan':
                                row_data[k] = target_country
                            else:
                                row_data[k] = v
                        else:
                            row_data[k] = v
                            
                # Handle Profile Path
                # Check for RE assets
                if 'RE_' in asset_name or 'PV' in asset_name or 'WIND' in asset_name:
                    re_type = None
                    if 'PV' in asset_name:
                        re_type = 'PVOUT'
                    elif 'WIND' in asset_name:
                        re_type = 'WINDOUT'
                    
                    if re_type:
                        row_data['RE_type'] = re_type
                        # Construct expected profile path
                        # Code/Assets/[ASSET]/profiles/[TYPE]/lat[LAT]/[TYPE]_lat[LAT]_lon[LON].csv
                        # Japan's lat is approx 35.5. Let's look for ANY file in lat35.5 first.
                        
                        found_profile = None
                        
                        # Try to find a profile in lat35.5 directory
                        lat_dir = os.path.join(asset_path, 'profiles', re_type, f'lat{source_lat}')
                        if os.path.exists(lat_dir):
                            for file in os.listdir(lat_dir):
                                if file.endswith('.csv') and 'lat35.5' in file:
                                    # Found a candidate!
                                    found_profile = os.path.join(lat_dir, file)
                                    break
                        
                        if not found_profile:
                             # Fallback: Check if the hardcoded path actually exists
                             fallback_path = os.path.join(asset_path, 'profiles', re_type, f'lat{source_lat}', f'{re_type}_lat{source_lat}_lon{source_lon}.csv')
                             if os.path.exists(fallback_path):
                                 found_profile = fallback_path

                        if found_profile:
                            row_data['profile_path'] = found_profile

                # Check for Demand assets
                elif 'Demand' in asset_name:
                    # Construct expected profile path
                    # Code/Assets/[ASSET]/profiles/[COUNTRY]_[YEAR]_GW.csv
                    # Try 2050 then 2019
                    for year in ['2050', '2019']:
                        # Try JPN first as that seems common for demand files
                        test_path = os.path.join(asset_path, 'profiles', f'JPN_{year}_GW.csv')
                        if os.path.exists(test_path):
                            row_data['profile_path'] = test_path
                            break
                        
                        test_path = os.path.join(asset_path, 'profiles', f'{source_country}_{year}_GW.csv')
                        if os.path.exists(test_path):
                            row_data['profile_path'] = test_path
                            break

            else:
                # No source data found, skip this asset
                continue
            
            all_assets_data.append(row_data)
            
        except Exception as e:
            print(f"Error reading {asset_name}: {e}")

    # Create DataFrame with all columns
    # Convert set to sorted list, ensuring key columns are first
    sorted_columns = ['asset_name', 'profile_path', 'RE_type'] + sorted([c for c in all_columns if c not in ['asset_name', 'profile_path', 'RE_type', 'location_name', 'Type']])
    
    template_df = pd.DataFrame(all_assets_data, columns=sorted_columns)
    
    # Ensure integer fields are cast to int (handling NaNs if any)
    # Dynamic detection: check if all non-null values in a column are integers
    for col in template_df.columns:
        if pd.api.types.is_numeric_dtype(template_df[col]):
            # Drop NaNs for check
            non_na = template_df[col].dropna()
            if len(non_na) > 0:
                # Check if all values are integers (e.g. 1.0, 24.0)
                is_integer = np.all(non_na % 1 == 0)
                if is_integer:
                    # Fill NaNs with 0 and cast to int
                    template_df[col] = template_df[col].fillna(0).astype(int)
    
    # Save to CSV
    output_file = 'new_country_assets_input.csv'
    template_df.to_csv(output_file, index=False)
    print(f"Generated template {output_file} with {len(template_df)} assets and {len(sorted_columns)} columns.")

if __name__ == "__main__":
    generate_template()
