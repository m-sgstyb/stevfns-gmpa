# DIY-Kit Automation Notes
### Updates

1. I have drafted a `0_BASE_AUTARKY` folder to use as the baseline to copy files from and determine full `Location_Parameters.csv` as the previous pipeline for `GMPA_full_automation` did, applying to new assets and the time dependent version.
2. I updated the script at `src/automations/generate_co2_budget.py` has been updated to align with time dependent budget trajectories. The automations for `add_country.py` and `run_collab_workflow.py` will still link to the same hook for the whole pipeline. This script (`generate_co2_budget.py`) currently has hard-coded entries for specific case studies to test, the end goal is that the addition of a new country will automate it based on assumptions
> [!WARNING] 
> This is blocked by being able to automatically determine the final emissions reduction pathway based on the addition of a new country. Can we have an intermediary step to start testing that uses the hard coded values for a specific case study to begin testing while we build that on our end?
3. I have sent through a Mexico DIY Kit. I included as well a new_country_input.csv for reference to begin testing.
4. The old DIY Kit template has explicit paths within the csv where the RE and demand profiles are saved etc. The new DIY kits do not inherently have this, so they should be automatically generated based on conventions. e.g. for RE given the coordinates from user input in the portal, and the RE profiles provided in the `XX_hourly_profile_data.csv`, the file directory and name 

### Worked example file tree
The DIY Kit shared for Mexico, and the input from users/CMS admin in the webtool for country code and coordinates, should generate the following:

- `data/Case_Study/Autarky_MX/` case study folder, with `Network_Structure.csv` based on that in `0_BASE_AUTARKY`. Convention is currently that the location number will match the asset type row in each asset's parameters.csv. The sample is in dev/time-dep branch of this repository

> [!IMPORTANT]
> 1. The scenario folders to be generated inside the new case study folder depend on generate_carbon_budget.py definition. For testing, we could create a 2C and 2.5C with the current hard-coded values given in generate_carbon_budget.py
> 2. The manually created worked example includes one scenario folder only. NOTE that the Asset_Type for CO2_Budget is 0, but this number should be determined within the generate_co2_budget.py, and there will be different values for each scenario folder
- `src/assets/<each_asset_in_Network_Structure.csv>/parameters.csv` : new row, with Asset_Number equal to the new row for Location_Parameters.csv file, that inputs the asset parameters from the DIY kit into a horizontal line by country. See `BESS/parameters.csv` for reference example. The values from DIY kit are now in row 31 of this STEVFNs input file. **NOTE** existing_capacity is 0. If a value for a parameter from the parameters.csv file columns is not in the DIY Kit, input 0 as default fallback for now
- For profile-dependent assets (RE assets, EL_Demand, CEM_Demand, STL_Demand), the addition of the parameter row in parameters.csv applies, but also requires the creation of a profile file. Profiles should be in the `src/assets/<demand_asset>/profiles/` folder, and follow each assets naming convention. RE profiles follow the convention with latitude and longitude. EL_Demand convention will now be `XX_el_demand.csv` (without the year and unit in the name, as it was in the previous version), and should extend the 219,000 hours:
	- (a) by copying a 219,000 row profile the user provided, if provided in full
	- (b) by extending a 8760 profile by copying the same year 25 times
	`XX_cem_demand.csv`, `XX_stl_demand.csv`, `XX_frt_demand.csv`, `XX_pgr_demand.csv` represent the industry and transport demands, respectively. These are annual, rather than hourly, the user should provide the full length profile assumptions. The FRT and PGR demand may be provided as a scalar in the DIY Kit's `XX_asset_parameters.csv` , and the model will expand it to constant future parameter, but the explicit profiles may be provided as well (example included in the DIY Kit annual profiles)


> [!NOTE] 
> For **EL_Transport**, **H2_Transport**, **NH3_Transport** assets, the autarky case study does not need them, therefore, they should be ignored from DIY kit's asset_parameters CSV file in the add_country pipeline. The data for this will be relevant for collaboration scenarios only, and we will have to use one version for each pair. 
> In general, GMPA will use a single asset type for all transport models in the global models, but users should be able to determine the parameters for these assets in their private models.

### Next steps
1. Mónica: finalising the brands of assets for the diy-kit-test Case Study, to enable a quick test run of a full version without automation. (This involves adding 219,000 hourly profiles for all RE assets for the Asset_Types that correspond.)
2. We can start with adding country automation, before moving onto adding collaborations pipeline
3. Markytech: Could you please help me review the old workflow relevant details and determine a path of action, so we can identify together which further specific tasks are needed from both sides and we can start building a plan and time estimates accordingly. 

#### Suggested starting point

[Original GMPA_full_automation guide for add_country pipeline](https://github.com/OmNomNomzzz/STEVFNs/blob/GMPA_full_automation/add_country_flow.md)