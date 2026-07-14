# GMPA - STEVFNs modelling
![Logo](img/gmpa_logo.png)

This is the STEVFNs model generator fork from the original [STEVFNs model](https://github.com/OmNomNomzzz/STEVFNs/tree/main) containing modelling details used in the Global Mitigation Potential Atlas ([GMPA](https://mitigationatlas.org/)).

To set up case studies and run different tests, you need to clone this repository as instructed, and follow the setup instructions that follow. 

## Set up and first run

### 0. Requirements
> [!IMPORTANT] 
> The following should be installed before continuing

1. This project has shifted reliance on conda package managers to `uv` for simpler cross-OS collaboration and quicker setup. For more details on `uv` and follow installation instructions, see [Astral's uv documentation](https://docs.astral.sh/uv/) 

2. Install git: For detailed documentation on git, see [git's installation page](https://git-scm.com/install/)

### 1. Clone
In your terminal, navigate to a local directory where you will want to keep the STEVFNs repository folder. Once there, run

```
git clone https://github.com/m-sgstyb/stevfns-gmpa.git
```

This should take a minute or two and will create a stevfns-gmpa folder in that directory with all the files from the main branch in the repository.

### 2. Create your local branch

To avoid editing directly in the main branch, create your on local branch to test the model and roun your own case studies. Choose a branch name, such as "testing" or "custom_runs", from your command line replace <branch-name> with your chosen name and, run

```
git checkout -b <branch-name>
```
This will create a new branch where you can start playing with the model.

### 3. Set up required: virtual environment

This project relies on Python dependencies that are stored in pyproject.toml file. To create a virtual environment and install required dependencies there, run

```
uv sync
```
> [!NOTE]
> You should have installed `uv` as instructed in step 0. for this to work

### 4. Quick run pre-defined test_collab case study

The repository automatically comes with a case study defined for a two-country collaboration. This is located in Case_Study/test_collab. 

To run this case, from the repo root in your terminal, run

```
uv run python run_cases.py --name test_collab
```

Your terminal should start displaying this: 
```console
--- Running: test_collab with clarabel solver ---

========================== Building ==========================
Time taken to build network =  0.6059021949768066 s

================== Updating for Scenario BAU ==================

Time taken to update network =  0.011281967163085938 s
----------------- Scenario BAU Main Results ----------------------

Time taken to solve problem =  0.8200230598449707 s
optimal
Total cost to satisfy all demand =  101.25240164207851  Billion USD
Total emissions =  10.66361512 MtCO2e
------------------  All Scenarios Run  ------------------------
 Time to build network, run all scenarios, export and plot data 0.02396846612294515 min

All case studies completed successfully.
```

Once you have been able to run the pre-defined minimal case study, you can create your own and run the model.


## Custom Case Studies

### 1. Create a Case Study folder

In Data/Case_Study, create a new folder with your case study name. If you have selected a country, this may be something like "ID_test", or if you want multiple countries for collaboration, it could be "ID-SG_collab". Think of names that are simple but descriptive. 

### Necessary details

A case study needs four basic parts before it runs:

1. Network_Structure.csv file 
2. At least one scenario folder (appropriately named) with:
	a. Asset_Paramters.csv
	b. Location_Parameters.csv
	c. System_Parameters.csv

For your initial test, System_Parameters.csv and Location_Parameters.csv can be copied from test_collab case study scenario. These include all the locations where asset data is available in the repository so you can use without additional data collection, as well as pre-determined system details (1-hour timesteps, 30-year project and 5% discount rates).

#### Network_Structure.csv

The `Network_Structure.csv` file defines where and which assets may be installed by the model.  

| Asset_Number | Asset_Class         | Location_1 | Location_2 | Start_Time | End_Time | Period | Transport_Time |
|--------------|---------------------|------------|------------|------------|----------|--------|----------------|
| 0            | EL_Demand           | 0          | 0          | 0          | 192      | 1      | 0              |
| 1            | RE_PV_Openfield_Lim | 0          | 0          | 0          | 192      | 1      | 0              |


- Asset_Number: This should be a continuous list starting at 0

- Asset_Class: This column should contain the asset name from the technologies or parts of the system that you want in the model, for example this table includes electricity demand and openfield PV

- Location_1: This is where the asset will be located.

- Location_2: This is equal to Location_1 if the asset is only in one location. For collaboration/linking assets, for example HVDC cables or ammonia shipping that connect two locations and can trade, Location_2 must be different to Location_1. (See the full `Network_Structure.csv` in test_collab)

- Start_Time: This is the timestep where the model will start sampling profile data from (demand or capacity factor profiles). Default is 0

- End_Time: End_Time - Start_Time determines how many timesteps will be sampled in total from profile assets, and therefore how many total timesteps will be modelled. In this example, 192 - 0 = 192. This is equivalent to sampling 8 days out of a year, which will be sampled from input profiles evenly throught the annual profile to capture seasonal differences.

- Period: This is how often the source is delivered (in this case, 1 hour as the smalles timestep in the model). For example, fuel shipping may only be dispatched every certain amount of days. For ammonia transport for example, ships do not depart every hour, so this parameter would be higher (See the full `Network_Structure.csv` in test_collab for NH3_Transport).

- Transport_Time: This is the time it takes to transport energy from one location to another. We assume electricity can be instantaneously generated and delivered. For ammonia transport for example, it takes a long time (magnitude of days) from the shipping to get from one point to another (See the full `Network_Structure.csv` in test_collab for NH3_Transport).

#### scenario_folder/Asset_Parameters.csv

The first four columns of the `Asset_Paramters.csv` should be exactly the same as the `Network_Structure.csv`.

| Asset_Number | Asset_Class         | Location_1 | Location_2 | Asset_Type |
|--------------|---------------------|------------|------------|------------|
| 0            | EL_Demand           | 0          | 0          | 0          |
| 1            | RE_PV_Openfield_Lim | 0          | 0          | 0          |


The fifth column determines which asset type should be considered for installation in that location. This value should match the parameters relevant to your scenario from the `Code/Assets/<asset_name>/parameters.csv` file.

For example, for `RE_PV_Openfield_Lim` asset, the first row would look like this. 

| Type | sizing_constant | sizing_constant_unit | lifespan | lifespan_unit | RE_type | set_size | set_number | maximum_size | maximum_size_unit | location_name |
|------|-----------------|----------------------|----------|---------------|---------|----------|------------|--------------|-------------------|---------------|
| 0    | 0.51            | G$/GWp               | 262800   | h             | PVOUT   | 24       | 0          | 0.35339      | GWp               | SGP           |


In this case, the Type 0 open field PV asset is for Singapore (see location_name column). Therefore, it would follow that Location_1 and Location_2 columns from this case study network structure would correspond to the location for Singapore. Because the data already comes from pre-defined `Location_Parameters.csv`, this was intentional.

If you look at the `Location_Parameters.csv` from the test_collab case study, scenario BAU, you'll see row 0 for locations has the coordinates for SG. These coordinates have two purposes in the model setup:

1. Estimate distances between locations, "as the bird flies" for the estimation of shipping and HVDC transport distances
2. To find the correct capacity factor profiles for PV and Wind asset types, as these have a conventional naming format related to their coordinates.

> [!NOTE]
> The capacity factor profiles will not necessarily correspond to the actual lat-lon values, they may be country averages to represent country potentials or other assumptions. 
> For the data currently in the repository, these represent country averages obtained through a modelling pipleine from GLAES/RESkit

#### scenario_folder/Location_Parameters.csv

This file defines the coordinates for locations and their abbreviation for ease of use. Currently, as GMPA models country-level, these are alpha-2 ISO 3166 country codes.

#### scenario_folder/System_Parameters.csv

This file defines system-wide parameters, project lifetime in hours, discount rate for NPV cost calculations, and the timestep size.



