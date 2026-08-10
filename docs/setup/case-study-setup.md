# Case Study Setup
---
 🚧 This site is currently under construction. Further detail will be added soon  🚧

After successful [Installation](../home/installation.md), and 
running of [Quick-Start](../home/quick-start.md) example, the following can be set up.

### Create a Case Study folder

In Data/Case_Study, create a new folder with your case study name. If you have selected a country, for example Indonesia, this may be something representative like `id-test`, or if you want multiple countries for collaboration, it could be `id-sg-collab`. Think of names that are simple but descriptive. 

!!! note
    Case Study folder naming convention

    For CLI ergonomics and visual separation, we recommend adhering to kebab-case (words separated by dashes) convention for naming new case study folders:
    
    - lower case only: try not to use capital leters ( use `id-sg-collab` instead of `ID-SG-Collab`)
    - avoid spaces or underscores

#### Necessary details
---

A case study needs four basic parts before it can be run:

1. Network_Structure.csv file: defines in which locations and which technologies will be modelled
2. At least one scenario folder (appropriately named) with:
	a. Asset_Paramters.csv
	b. Location_Parameters.csv
	c. System_Parameters.csv

For your initial test, System_Parameters.csv and Location_Parameters.csv can be copied from test-collab case study scenario. These include all the locations where asset data is readily available in the repository so you can use without additional data collection, as well as pre-determined system details (1-hour timesteps, 30-year project and 5% discount rates).

#### Network_Structure.csv
---

The `Network_Structure.csv` file defines where and which assets may be installed by the model.  

| Asset_Number | Asset_Class         | Location_1 | Location_2 | Start_Time | End_Time | Period | Transport_Time |
|--------------|---------------------|------------|------------|------------|----------|--------|----------------|
| 0            | EL_Demand           | 0          | 0          | 0          | 192      | 1      | 0              |
| 1            | RE_PV_Openfield_Lim | 0          | 0          | 0          | 192      | 1      | 0              |


- **Asset_Number:** This should be a continuous list starting at 0

- **Asset_Class:** This column should contain the asset name from the technologies or parts of the system that you want in the model, for example this table includes electricity demand and openfield PV

- **Location_1:** This is where the asset will be located.

- **Location_2:** This is equal to Location_1 if the asset is only in one location. For collaboration/linking assets, for example HVDC cables or ammonia shipping that connect two locations and can trade, Location_2 must be different to Location_1. (See the full `Network_Structure.csv` in test-collab)

- **Start_Time:** This is the timestep where the model will start sampling profile data from (demand or capacity factor profiles). Default is 0

- **End_Time:** `End_Time - Start_Time` determines how many timesteps will be sampled in total from profile assets, and therefore how many total timesteps will be modelled. In this example, 192 - 0 = 192. This is equivalent to sampling 8 days out of a year in the original single year version of STEVFNs, which will be sampled from input profiles evenly throught the annual profile to capture seasonal differences. In 
the time dependent implementation, the `End_Time - Start_Time` defines the total hours sampled across the entire project lifetime. If, for example,
the sample size is 12 days per year in a 10-year project, the defined parameters in
network structure should be a total of: $12 \cdot 24 \cdot 10 =\ 2,880\ hours$. If start time is 0, then end time would be 2,880 in this case.

- **Period:** This is how often the source is delivered (in this case, 1 hour as the smallest timestep in the model). For example, fuel shipping may only be dispatched every certain amount of days. For ammonia transport for example, ships do not depart every hour, so this parameter would be higher (See the full `Network_Structure.csv` in test-collab for NH3_Transport).

- **Transport_Time:** This is the time it takes to transport energy from one location to another. We assume electricity can be instantaneously generated and delivered. For ammonia transport for example, it takes a long time (magnitude of days) from the shipping to get from one point to another (See the full `Network_Structure.csv` in test-collab for NH3_Transport).

##### Technology selection
---


#### Asset_Parameters
---
Each scenario folder should have its own Asset_Parameters.csv
The first four columns of the `Asset_Paramters.csv` should be exactly the same as the `Network_Structure.csv`.

| Asset_Number | Asset_Class         | Location_1 | Location_2 | Asset_Type |
|--------------|---------------------|------------|------------|------------|
| 0            | EL_Demand           | 0          | 0          | 0          |
| 1            | RE_PV_Openfield_Lim | 0          | 0          | 0          |


The fifth column determines which asset type should be considered for installation in that location. This value should match the parameters relevant to your scenario from the `src/assets/<asset_name>/parameters.csv` file.

For example, for `RE_PV_Openfield_Lim` asset, the first row would look like this. 

| Type | sizing_constant | sizing_constant_unit | lifespan | lifespan_unit | RE_type | set_size | set_number | maximum_size | maximum_size_unit | location_name |
|------|-----------------|----------------------|----------|---------------|---------|----------|------------|--------------|-------------------|---------------|
| 0    | 0.51            | G$/GWp               | 262800   | h             | PVOUT   | 24       | 0          | 0.35339      | GWp               | SGP           |


In this case, the Type 0 open field PV asset is for Singapore (see location_name column). Therefore, it would follow that Location_1 and Location_2 columns from this case study network structure would correspond to the location for Singapore. Because the data already comes from pre-defined `Location_Parameters.csv`, this was intentional.

If you look at the `Location_Parameters.csv` from the test-collab case study, scenario BAU, you'll see row 0 for locations has the coordinates for SG. These coordinates have two purposes in the model setup:

1. Estimate distances between locations, "as the bird flies" for the estimation of shipping and HVDC transport distances
2. To find the correct capacity factor profiles for PV and Wind asset types, as these have a conventional naming format related to their coordinates.

!!! NOTE
    The capacity factor profiles will not necessarily correspond to the actual lat-lon values, they may be country averages to represent country potentials or other assumptions. 
    For the data currently in the repository, these represent country averages obtained through a modelling pipleine from GLAES/RESkit

#### Location_Parameters
---
Each scenario folder should have its own Location_Parameters.csv
This file defines the coordinates for locations and their abbreviation for ease of use. Currently, as GMPA models country-level, these are alpha-2 ISO 3166 country codes.

#### System_Parameters
---
Each scenario folder should have its own System_Parameters.csv
This file defines system-wide parameters, project lifetime in hours, discount rate for NPV cost calculations, and the timestep size.

