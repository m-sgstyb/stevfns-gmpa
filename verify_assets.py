import os
import pandas as pd

def verify_assets(source_country='JP', target_country='JC'):
    assets_dir = 'Code/Assets'
    issues = []
    
    print(f"Verifying assets for {target_country} based on {source_country}...")
    
    # Allowed assets whitelist
    allowed_assets = [
        'RE_PV_Openfield_Lim', 'RE_PV_Rooftop_Lim',
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

    for asset_name in sorted(os.listdir(assets_dir)):
        if asset_name not in allowed_assets:
            continue

        if asset_name == 'CO2_Budget':
            continue
            
        asset_path = os.path.join(assets_dir, asset_name)
        if not os.path.isdir(asset_path):
            continue
            
        params_path = os.path.join(asset_path, 'parameters.csv')
        if not os.path.exists(params_path):
            continue
            
        try:
            df = pd.read_csv(params_path)
            
            # Check if source country exists
            source_exists = not df[df['location_name'].isin([source_country, 'JPN', 'Japan'])].empty
            
            if source_exists:
                # Check if target country exists
                target_exists = not df[df['location_name'] == target_country].empty
                
                if not target_exists:
                    issues.append(f"MISSING PARAMETERS: {asset_name} has {source_country} but missing {target_country}")
                else:
                    # Check profiles if applicable
                    # RE Assets
                    if 'RE_' in asset_name or 'PV' in asset_name or 'WIND' in asset_name:
                        re_type = 'PVOUT' if 'PV' in asset_name else ('WINDOUT' if 'WIND' in asset_name else None)
                        if re_type:
                            # Check if SOURCE has a profile first
                            # We assume source is JP (lat35.5)
                            source_lat_dir = os.path.join(asset_path, 'profiles', re_type, 'lat35.5')
                            source_has_profile = False
                            if os.path.exists(source_lat_dir):
                                for f in os.listdir(source_lat_dir):
                                    if f.endswith('.csv'):
                                        source_has_profile = True
                                        break
                            
                            if source_has_profile:
                                target_profile_dir = os.path.join(asset_path, 'profiles', re_type, 'lat36.0')
                                if not os.path.exists(target_profile_dir) or not os.listdir(target_profile_dir):
                                    issues.append(f"MISSING PROFILE: {asset_name} (RE) missing profile in {target_profile_dir} (Source had one)")
                            else:
                                # print(f"Info: {asset_name} has no source profile for JP, skipping target check.")
                                pass
                    
                    # Demand Assets
                    elif 'Demand' in asset_name:
                        target_profile = os.path.join(asset_path, 'profiles', f'{target_country}_2050_GW.csv')
                        if not os.path.exists(target_profile):
                            issues.append(f"MISSING PROFILE: {asset_name} (Demand) missing profile {target_profile}")

        except Exception as e:
            issues.append(f"ERROR: Could not verify {asset_name}: {e}")

    if issues:
        print("\nIssues found:")
        for issue in issues:
            print(issue)
    else:
        print("\nAll assets verified successfully! Every asset with JP data has corresponding JC data.")

if __name__ == "__main__":
    verify_assets()
