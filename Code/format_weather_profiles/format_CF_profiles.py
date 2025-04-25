#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Sep 14 14:37:30 2024

@author: Mónica Sagastuy-Breña

This script is specific to GMPA Pilot and 2nd phases and with the workflow for
Climate Analytics processed renewables data, hardcoded for this specitic format.

It reads the RES analysis files for capacity factor profiles for PV and Wind obtained
by Climate Analytics, prepares and saves them as STEVFNs inputs directly into their asset folders.


PLEASE NOTE: The function for wind is hardcoded to average out 10 binned profiles into one
If a wind file has a different format, or does not exist, this function will not work
and the profile will have to be handled manually.
Please contact Mónica if this arises.

Methodology:
    1. In Box, go to Modelling > res_analysis and download the folders named for the countries
    that need STEVFNs-formatted renewable energy profiles
    2. Save those folders (named by three-letter ISO abbreviation per country) into the
    raw_from_Box > res_analysis folder in STEVFNs repo
    3. Edit the list defined after the functions in this script to include those countries
    4. Run both of the functions
    
    5. Check that the Asset Folders for:
        RE_PV_Openfield_Lim
        RE_PV_Openfield_BAU
        RE_PV_Rooftop_Lim
        
        RE_WIND_Onshore_Lim
        RE_WIND_Onshore_BAU
        RE_WIND_Offshore_Lim
     Have created new folders with the renewable data processed as required.

"""

import pandas as pd
import numpy as np
import os


CODE_DIR = os.path.split(os.getcwd())[0]
stevfns_inputs = os.path.join(CODE_DIR, "Assets")

root_dir = os.path.dirname(__file__)
location_parameters_filename = os.path.join(root_dir, 'lat–lon-data.csv')
raw_data_folder = os.path.join(root_dir, "raw_from_Box")


# onshore_wind_folder = os.path.join(stevfns_inputs, "RE_WIND_Onshore_Lim", "profiles", "WINDOUT")
# offshore_wind_folder = os.path.join(stevfns_inputs, "RE_WIND_Offshore_Lim", "profiles", "WINDOUT")
rooftop_pv_folder = os.path.join(stevfns_inputs, "RE_PV_Rooftop_Lim", "profiles", "PVOUT")
openfield_pv_folder = os.path.join(stevfns_inputs, "RE_PV_Openfield_Lim", "profiles", "PVOUT")

# BAU folders to save profiles there as well
onshore_windbau_folder = os.path.join(stevfns_inputs, "RE_WIND_Onshore_BAU", "profiles", "WINDOUT")
openfield_pvbau_folder = os.path.join(stevfns_inputs, "RE_PV_Openfield_BAU", "profiles", "PVOUT")

# Get locations coordinates to format capacity factor profiles
lat_lon_df = pd.read_csv(location_parameters_filename)
lat_lon_df = lat_lon_df.set_index('type')
lat_lon_df = lat_lon_df.T
lat_lon_df.columns = lat_lon_df.iloc[0]


land_locked_countries = ['LAO']
pilot_countries = ['IDN', 'LAO', 'PHL', 'BRN', 'KHM', 'SGP', 'THA', 'VNM', 'MYS']

def get_pv_inputs(countries):
    '''
    
    Parameters
    ----------
    countries : LIST
        DESCRIPTION: List of countries to get PV data from. Each country is a string of
        two-letter ISO abbreviation, all caps. e.g. to get PV data for Great Britain,
        Kenya and South Africa in one go countries = ['GBR', 'KEN', 'ZAF']

    Returns
    -------
    None.

    '''
    
    for country in countries:
    
        lat = lat_lon_df.loc['lat', f'{country}']
        lat = np.int64(np.round((lat) / 0.5)) * 0.5
        lat = min(lat,90.0)
        lat = max(lat,-90.0)
        
        lon = lat_lon_df.loc['lon', f'{country}']
        lon = np.int64(np.round((lon) / 0.625)) * 0.625
        lon = min(lon, 179.375)
        lon = max(lon, -180.0)

        '''
        OPENFIELD PV
        '''
        
        # Extract CF profile for openfield PV, Climate Analytics format
        PVopen_CF_df = pd.read_csv(os.path.join(raw_data_folder, 'res_analysis',
                                                f'{country}', 'pvopenfield', 'capacity_factor_binned.csv'))
        PVopen_CF_df = PVopen_CF_df.T
        PVopen_CF_df = PVopen_CF_df.drop('region', axis=0)
        
        # The below works for the formats in Pilot Phase
        # PVopen_CF_df = PVopen_CF_df.drop([0, 1], axis=1)
        # PVopen_CF_df = PVopen_CF_df.drop('Unnamed: 0', axis=0)
        
        # Find/create directory for openfield PV profiles
        pv_of_dir = os.path.join(openfield_pv_folder, f'lat{lat}')
        if not os.path.exists(pv_of_dir):
            os.makedirs(pv_of_dir) 
        pv_of_filename = os.path.join(pv_of_dir, f'PVOUT_lat{lat}_lon{lon}.csv')
        
        # save formatted files into PV Openfield Lim and PV Openfield BAU asset folders
        PVopen_CF_df.to_csv(pv_of_filename, index=False, header=False)
        
        pv_ofbau_dir = os.path.join(openfield_pvbau_folder, f'lat{lat}')
        if not os.path.exists(pv_ofbau_dir):
            os.makedirs(pv_ofbau_dir)
        PVopen_CF_df.to_csv(os.path.join(pv_ofbau_dir, f'PVOUT_lat{lat}_lon{lon}.csv'),
                            index=False, header=False)
        
        '''
        ROOFTOP PV
        '''
        
        # Extract CF profile for rooftop PV, Climate Analytics format
        PVroof_CF_df = pd.read_csv(os.path.join(raw_data_folder, 'res_analysis',
                                                f'{country}', 'pvrooftop', 'capacity_factor_binned.csv'))
        PVroof_CF_df = PVroof_CF_df.T
        PVroof_CF_df = PVroof_CF_df.drop('region', axis=0)
        # PVroof_CF_df = PVroof_CF_df.drop([0, 1], axis=1)
        # PVroof_CF_df = PVroof_CF_df.drop('Unnamed: 0', axis=0)
        
        # Find/create directory for openfield PV profiles
        pv_rt_dir = os.path.join(rooftop_pv_folder, f'lat{lat}')
        if not os.path.exists(pv_rt_dir):
            os.makedirs(pv_rt_dir) 
        pv_rt_filename = os.path.join(pv_rt_dir, f'PVOUT_lat{lat}_lon{lon}.csv')
        
        # Save csv with correct format
        PVroof_CF_df.to_csv(pv_rt_filename, index=False, header=False)
    
    return


def get_wind_inputs(countries, scenario):
    '''
    Parameters
    ----------
    countries : LIST
        DESCRIPTION: List of countries to get WIND data from. Each country is a string of
        three-letter ISO abbreviation, all caps. e.g. to get WIND data for United States,
        Kenya and South Africa in one go countries = ['USA', 'KEN', 'ZAF']
    scenario : STR
        scenario from CA projections of CAPEX ('high', 'medium', or 'low', all lowercase) 
        that we want the wind cost data for
        
    Returns
    -------
    None.

    '''
    
    for country in countries:
        print(country)
        lat = lat_lon_df.loc['lat', f'{country}']
        lat = np.int64(np.round((lat) / 0.5)) * 0.5
        lat = min(lat,90.0)
        lat = max(lat,-90.0)
        
        lon = lat_lon_df.loc['lon', f'{country}']
        lon = np.int64(np.round((lon) / 0.625)) * 0.625
        lon = min(lon, 179.375)
        lon = max(lon, -180.0)

        '''
        ONSHORE WIND
        '''
        # Extract and format CF profile for Onshore wind
        WindOnshore_CF_df = pd.read_csv(os.path.join(raw_data_folder, 'res_analysis',
                                                f'{country}', 'windonshore', 'capacity_factor_binned.csv'), header=None)
        WindOnshore_CF_df = WindOnshore_CF_df.drop([0,1], axis=1) # remove region and group columns
        WindOnshore_CF_df = WindOnshore_CF_df.drop([0], axis=0) # remove only datetime row
        WindOnshore_CF_df = WindOnshore_CF_df.T
        WindOnshore_CF_df = WindOnshore_CF_df.astype(float)
        WindOnshore_CF_df.columns = list(range(len(WindOnshore_CF_df.columns)))
        # print(WindOnshore_CF_df)
        if country not in land_locked_countries:
            # Extract and format CF profile for Offshore wind only for not land locked countries
            WindOffshore_CF_df = pd.read_csv(os.path.join(raw_data_folder, 'res_analysis',
                                                    f'{country}', 'windoffshore', 'capacity_factor_binned.csv'), header=None)
            WindOffshore_CF_df = WindOffshore_CF_df.drop([0,1], axis=1) # remove region and group columns
            WindOffshore_CF_df = WindOffshore_CF_df.drop([0], axis=0)  # remove only datetime row
            WindOffshore_CF_df = WindOffshore_CF_df.T
            WindOffshore_CF_df = WindOffshore_CF_df.astype(float)
            WindOffshore_CF_df.columns = list(range(len(WindOffshore_CF_df.columns)))

        for group in range(len(WindOnshore_CF_df.columns)):
            
            onshore_wind_folder = os.path.join(stevfns_inputs, f"RE_WIND_Onshore_Lim_{group}", "profiles", "WINDOUT")
            
            # Find/create directory for onshore wind profiles in STEVFNs 
            wind_on_dir = os.path.join(onshore_wind_folder, f'lat{lat}')
            if not os.path.exists(wind_on_dir):
                os.makedirs(wind_on_dir)
            wind_on_filename = os.path.join(wind_on_dir, f'WINDOUT_lat{lat}_lon{lon}.csv')
            WindOnshore_CF_df[group].to_csv(wind_on_filename, index=False, header=False)
            
            
            max_capacities_on_df = pd.read_csv(os.path.join(raw_data_folder, 'res_analysis',
                                          f'{country}', 'windonshore', 'capacity_binned.csv'), header=None)
            wind_on_capex_df = pd.read_csv(os.path.join(raw_data_folder, 'res_analysis',
                                          f'{country}', 'windonshore', 'capex_binned.csv'), header=None)
            wind_on_capex_df.columns = wind_on_capex_df.iloc[0]
            wind_on_capex_df = wind_on_capex_df[1:]
            wind_on_capex_df = wind_on_capex_df.reset_index(drop=True)
            
            # Get capex value for onshore  wind
            wind_on_capex_array = wind_on_capex_df .loc[(wind_on_capex_df['scenario'] == f'{scenario}') & 
                                                (wind_on_capex_df['group'].astype(int) == group),
                                                2050].values
            wind_on_capex_value = float(wind_on_capex_array[0]) / 1000 # convert units

            # Get max capacities for onshore and offshore wind
            if country in pilot_countries:
                max_capacities_on_df.columns = max_capacities_on_df.iloc[0]
                max_capacities_on_df = max_capacities_on_df[1:].reset_index(drop=True)
                max_capacities_on_df['group'] = max_capacities_on_df['group'].astype(int)
                wind_on_max_cap_value = float(max_capacities_on_df.loc[max_capacities_on_df['group'] == group, 'capacity'].iloc[0])
        
            else:
                max_capacities_on_df.columns = max_capacities_on_df.iloc[0]
                max_capacities_on_df = max_capacities_on_df[1:].reset_index(drop=True)
                max_capacities_on_df['group'] = max_capacities_on_df['group'].astype(int)
                wind_on_max_cap_value = float((max_capacities_on_df.loc[max_capacities_on_df['group'] == group, 2050].iloc[0]) / 1000000)
            
            # Find parameters.csv files and input data
            wind_on_parameters_filename = os.path.join(stevfns_inputs, f"RE_WIND_Onshore_Lim_{group}", 'parameters.csv')
           
            wind_on_parameters_df = pd.read_csv(wind_on_parameters_filename)
            
            # Change the value for CAPEX
            wind_on_parameters_df.loc[wind_on_parameters_df['location_name'] == country,
                                      'sizing_constant'] = wind_on_capex_value
            
            wind_on_parameters_df.loc[wind_on_parameters_df['location_name'] == country,
                                      'maximum_size'] = wind_on_max_cap_value

            # print(wind_on_parameters_df)
            wind_on_parameters_df.to_csv(os.path.join(stevfns_inputs, f"RE_WIND_Onshore_Lim_{group}", 'parameters.csv'), index=False)
           
        if country not in land_locked_countries:
            offshore_wind_folder = os.path.join(stevfns_inputs, f"RE_WIND_Offshore_Lim_{group}", "profiles", "WINDOUT")
            
            for group in range(len(WindOffshore_CF_df.columns)):
                # Find/create directory for offshore wind profiles in STEVFNs if the country is not land locked
                wind_off_dir = os.path.join(offshore_wind_folder, f'lat{lat}')
                if not os.path.exists(wind_off_dir):
                    os.makedirs(wind_off_dir)
                wind_off_filename = os.path.join(wind_off_dir, f'WINDOUT_lat{lat}_lon{lon}.csv')
                WindOffshore_CF_df[group].to_csv(wind_off_filename, index=False, header=False)
                
                max_capacities_off_df = pd.read_csv(os.path.join(raw_data_folder, 'res_analysis',
                                              f'{country}', 'windoffshore', 'capacity_binned.csv'), header=None)
                wind_off_capex_df = pd.read_csv(os.path.join(raw_data_folder, 'res_analysis',
                                              f'{country}', 'windoffshore', 'capex_binned.csv'), header=None)
                wind_off_capex_df.columns = wind_off_capex_df.iloc[0]
                wind_off_capex_df = wind_off_capex_df[1:]
                wind_off_capex_df = wind_off_capex_df.reset_index(drop=True)
                wind_off_capex_array = wind_off_capex_df .loc[(wind_off_capex_df['scenario'] == f'{scenario}') & 
                                                    (wind_off_capex_df['group'].astype(int) == group),
                                                     2050].values
                wind_off_capex_value = float(wind_off_capex_array[0]) / 1000 # convert units
                
                # Get max capacities for onshore and offshore wind
                if country in pilot_countries:
                    max_capacities_off_df.columns = max_capacities_off_df.iloc[0]
                    max_capacities_off_df = max_capacities_off_df[1:].reset_index(drop=True)
                    max_capacities_off_df['group'] = max_capacities_off_df['group'].astype(int)
                    wind_off_max_cap_value = float(max_capacities_off_df.loc[max_capacities_off_df['group'] == group, 'capacity'].iloc[0])
                else:
                    max_capacities_off_df.columns = max_capacities_off_df.iloc[0]
                    max_capacities_off_df = max_capacities_off_df[1:].reset_index(drop=True)
                    max_capacities_off_df['group'] = max_capacities_off_df['group'].astype(int)
                    wind_off_max_cap_value = float((max_capacities_off_df.loc[max_capacities_off_df['group'] == group, 2050].iloc[0]) / 1000000)
                
                # Find parameters.csv files and input data
                wind_off_parameters_filename = os.path.join(stevfns_inputs, f"RE_WIND_Offshore_Lim_{group}", 'parameters.csv')
               
                wind_off_parameters_df = pd.read_csv(wind_off_parameters_filename)
                
                # Change the value for CAPEX
                wind_off_parameters_df.loc[wind_off_parameters_df['location_name'] == country,
                                          'sizing_constant'] = wind_off_capex_value

                wind_off_parameters_df.loc[wind_off_parameters_df['location_name'] == country,
                                          'maximum_size'] = wind_off_max_cap_value
                
                # print(wind_on_parameters_df)
                wind_off_parameters_df.to_csv(os.path.join(stevfns_inputs, f"RE_WIND_Offshore_Lim_{group}", 'parameters.csv'), index=False)
            
    return

def get_average_wind_inputs(countries, scenario):
    '''
    Averages every two bins of wind data and writes results to STEVFNs input folders
    for both onshore and offshore wind.

    Parameters
    ----------
    countries : list of str
        ISO3 country codes (e.g., ['USA', 'KEN'])
    scenario : str
        CAPEX scenario ('high', 'medium', or 'low')

    Returns
    -------
    None
    '''
    for country in countries:
        print(country)
        lat = lat_lon_df.loc['lat', country]
        lon = lat_lon_df.loc['lon', country]

        lat = np.int64(np.round(lat / 0.5)) * 0.5
        lon = np.int64(np.round(lon / 0.625)) * 0.625
        lat = min(max(lat, -90.0), 90.0)
        lon = min(max(lon, -180.0), 179.375)

        # === ONSHORE DATA ===
        WindOnshore_CF_df = pd.read_csv(os.path.join(raw_data_folder, 'res_analysis', country, 'windonshore', 'capacity_factor_binned.csv'), header=None).drop([0, 1], axis=1).drop([0], axis=0).T.astype(float)
        WindOnshore_CF_df.columns = list(range(WindOnshore_CF_df.shape[1]))

        wind_on_capex_df = pd.read_csv(os.path.join(raw_data_folder, 'res_analysis', country, 'windonshore', 'capex_binned.csv'), header=None)
        wind_on_capex_df.columns = wind_on_capex_df.iloc[0]
        wind_on_capex_df = wind_on_capex_df[1:].reset_index(drop=True)
        wind_on_capex_df['group'] = wind_on_capex_df['group'].astype(int)

        max_capacities_on_df = pd.read_csv(os.path.join(raw_data_folder, 'res_analysis', country, 'windonshore', 'capacity_binned.csv'), header=None)
        max_capacities_on_df.columns = max_capacities_on_df.iloc[0]
        max_capacities_on_df = max_capacities_on_df[1:].reset_index(drop=True)
        max_capacities_on_df['group'] = max_capacities_on_df['group'].astype(int)

        # === OFFSHORE DATA ===
        if country not in land_locked_countries:
            WindOffshore_CF_df = pd.read_csv(os.path.join(raw_data_folder, 'res_analysis', country, 'windoffshore', 'capacity_factor_binned.csv'), header=None).drop([0, 1], axis=1).drop([0], axis=0).T.astype(float)
            WindOffshore_CF_df.columns = list(range(WindOffshore_CF_df.shape[1]))

            wind_off_capex_df = pd.read_csv(os.path.join(raw_data_folder, 'res_analysis', country, 'windoffshore', 'capex_binned.csv'), header=None)
            wind_off_capex_df.columns = wind_off_capex_df.iloc[0]
            wind_off_capex_df = wind_off_capex_df[1:].reset_index(drop=True)
            wind_off_capex_df['group'] = wind_off_capex_df['group'].astype(int)

            max_capacities_off_df = pd.read_csv(os.path.join(raw_data_folder, 'res_analysis', country, 'windoffshore', 'capacity_binned.csv'), header=None)
            max_capacities_off_df.columns = max_capacities_off_df.iloc[0]
            max_capacities_off_df = max_capacities_off_df[1:].reset_index(drop=True)
            max_capacities_off_df['group'] = max_capacities_off_df['group'].astype(int)

        # === BIN AVERAGING ===
        for group in range(0, 10, 2):
            avg_group = group // 2

            # --- Onshore ---
            avg_on_cf = (WindOnshore_CF_df[group] + WindOnshore_CF_df[group + 1]) / 2.0
            on_cf_dir = os.path.join(stevfns_inputs, f"RE_WIND_Onshore_Lim_{avg_group}", "profiles", "WINDOUT", f'lat{lat}')
            os.makedirs(on_cf_dir, exist_ok=True)
            avg_on_cf.to_csv(os.path.join(on_cf_dir, f'WINDOUT_lat{lat}_lon{lon}.csv'), index=False, header=False)

            on_capex_vals = wind_on_capex_df.loc[
                (wind_on_capex_df['scenario'] == scenario) &
                (wind_on_capex_df['group'].isin([group, group + 1])),
                'capex_2050'].astype(float) / 1000
            avg_on_capex = on_capex_vals.mean()

            if country in pilot_countries:
                on_cap_vals = max_capacities_on_df.loc[max_capacities_on_df['group'].isin([group, group + 1]), 'capacity'].astype(float)
            else:
                on_cap_vals = max_capacities_on_df.loc[max_capacities_on_df['group'].isin([group, group + 1]), '2050'].astype(float) / 1e6
            total_on_cap = on_cap_vals.sum()

            on_param_file = os.path.join(stevfns_inputs, f"RE_WIND_Onshore_Lim_{avg_group}", 'parameters.csv')
            on_param_df = pd.read_csv(on_param_file)
            on_param_df.loc[on_param_df['location_name'] == country, 'sizing_constant'] = avg_on_capex
            on_param_df.loc[on_param_df['location_name'] == country, 'maximum_size'] = total_on_cap
            on_param_df.to_csv(on_param_file, index=False)

            # --- Offshore ---
            if country not in land_locked_countries:
                avg_off_cf = (WindOffshore_CF_df[group] + WindOffshore_CF_df[group + 1]) / 2.0
                off_cf_dir = os.path.join(stevfns_inputs, f"RE_WIND_Offshore_Lim_{avg_group}", "profiles", "WINDOUT", f'lat{lat}')
                os.makedirs(off_cf_dir, exist_ok=True)
                avg_off_cf.to_csv(os.path.join(off_cf_dir, f'WINDOUT_lat{lat}_lon{lon}.csv'), index=False, header=False)

                off_capex_vals = wind_off_capex_df.loc[
                    (wind_off_capex_df['scenario'] == scenario) &
                    (wind_off_capex_df['group'].isin([group, group + 1])),
                    'capex_2050'].astype(float) / 1000
                avg_off_capex = off_capex_vals.mean()

                if country in pilot_countries:
                    off_cap_vals = max_capacities_off_df.loc[max_capacities_off_df['group'].isin([group, group + 1]), 'capacity'].astype(float)
                else:
                    off_cap_vals = max_capacities_off_df.loc[max_capacities_off_df['group'].isin([group, group + 1]), '2050'].astype(float) / 1e6
                total_off_cap = off_cap_vals.sum()

                off_param_file = os.path.join(stevfns_inputs, f"RE_WIND_Offshore_Lim_{avg_group}", 'parameters.csv')
                off_param_df = pd.read_csv(off_param_file)
                off_param_df.loc[off_param_df['location_name'] == country, 'sizing_constant'] = avg_off_capex
                off_param_df.loc[off_param_df['location_name'] == country, 'maximum_size'] = total_off_cap
                off_param_df.to_csv(off_param_file, index=False)

    return



#%%
# countries = ['SGP']
countries = ['KOR', 'VNM', 'THA', 'KHM', 'IDN', 'SGP', 'BRA', 'BRN', 'CHL', 'COL', 'EGY', 'KEN',
              'LAO', 'MAR', 'MYS', 'NGA', 'PER', 'PHL', 'ZAF']
# countries_avg = ['VNM', 'THA', 'KHM', 'IDN']


# get_pv_inputs(countries)
get_wind_inputs(countries, 'high')
# get_average_wind_inputs(countries_avg, 'high')