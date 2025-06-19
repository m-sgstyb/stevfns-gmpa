# GMPA - STEVFNs modelling
![Logo](gmpa_logo.png)

This is the STEVFNs model generator branch containing modelling details for the GMPA. For the general details of the model generator and how to install, see main. To run case studies in this branch, you need to clone the STEVFNs repository as instructed and fetch all remote branches. You will then be able to pull GMPA branch and have a local version of it to work with. 


## Workflow

> [!NOTE]
> The workflow detailed below relates to case study creation and running the model; it assumes that all data inputs for assets (costs, renewable energy profiles, etc.) have been already been created. It also assumes that the countries we are modelling for are already in the Location Parameters, and that the scenarios for said countries in baseline case studies have been created. Comprehensive documentation of how this is done will be prepared for upcoming phases of the project.

### 1. Run baseline case studies
The assumptions for GMPA at its latest stage use a BAU and Least Cost baseline to generate a specific country's emissions reduction profile. In STEVFNs/Data/Case_Study there will be two folders named BAU_No_Action and Least_Cost_Emissions. In these, scenario folders for the countries currently covered in GMPA can be found. By running BAU and LC, we obtain the emissions data to create 11 scenarios of emissions reduction towards 0 MtCO<sub>2</sub>e

To run:
* Open main.py in an editor
* Change case_study_name to "BAU_No_Action" 
* If in an IDE, run directly. If you want to run through CLI, open a terminal and navigate to STEVFNs in your local repo
> [!IMPORTANT]
> Before running any python script, be sure to have activated your conda environment with python and the dependencies installed. See [Installation](https://github.com/OmNomNomzzz/STEVFNs/blob/main/README.md#installation) in main branch

```
python main.py
```
* Repeat for case_study_name = "Least_Cost_Emissions"

This will have created total_data_unrounded.csv and total_data.csv inside the case study folders.

### 2. Create emissions reduction profiles
Based on the BAU (assumes a more limited technology mix) and Least cost (assumes extensive technology mix including e.g. short term and long term storage) emissions, we need to create the "carbon budget" scenarios. We model 11 scenarios from the baseline to 0 for all case studies. These can be calculated through STEVFNs/Code/Automations/generate_carbon_budget.py script.

To run:
* In the terminal, navigate to STEVFNs/Code/Automations, and run
```
python generate_carbon_budget.py
```
* This will automatically create a budget profile or update existing values for single countries based on the most recent total_data files in BAU and Least_Cost. 
* It will then prompt the user to answer whether collaboration emissions should also be created. If yes, enter "y" and click return
* The user will be prompted to enter a comma-separated list of 2-4 countries with a small example. If the collaborations between Germany, France and Turkey are desired to be modelled, the user should enter the two-letter ISO abbreviations as:
```
DE,FR,TR
```
This will create all the possible collaborations between these countries, which will be printed in the terminal. The CO2_Budget profile should also be saved in STEVFNs/Code/Assets/CO2_Budget/parameters.csv file.

> [!NOTE] 
> To create collaboration emissions reduction profiles, the individual countries' emissions should have been calculated in BAU_No_Action and Least_Cost_Emissions case studies. 

### 3. Update CO2_Budget Asset type in Asset_Parameters.csv

Each scenario in the case studies has an Asset_Parameters.csv to define which asset data to use for each country and scenario modelled. The CO2_Budget values that are created in step 2 need to be updated in the single country and multi-country case study folders/scenario folder/Asset_Paramters.csv.

* In the terminal, navigate to STEVFNs/Code/Automations, and run
```
python update_co2_budget_asset_types.py
```

### 4. Create collaboration case study folders
> [!NOTE] 
> To create the case study folders for multiple countries, both in autarky and collaboration formats, the CO<sub>2</sub> budget for those collaborations must have already been created. If they have not, the user must re-run generate_carbon_budget.py, allow for all single country values to be updated and say yes when prompted to create for a collaboration.

To follow on the example of modelling the possible combinations of Germany, France and Turkey done in step 2:

* In the terminal, navigate to STEVFNs/Code/Automations, and run
```
python generate_collab_case_studies.py . DE FR TR
```
Note that in this case, the list is only separated by spaces. The order does not matter, the script will automatically be created with alphabetical combinations as a convention.

For this command to work as written, user needs to be in local/path/to/STEVFNs/Code/Automations. Otherwise, the script will display the usage instructions, which show
```
python generate_collab_case_studies.py <root_dir> [DE FR TR ...]
```
If in another folder, the user may type out the path to the Automations folder and the list of countries afterwards.
 
### 5. Run case studies
* Open main.py and edit the case_study_name to the string of the case study you want to run, and run the file.
* Repeat for any case study that needs to be run

> [!TIP]
> As the number of assets in a network increases, so does the build and sovle time of the problem. The current version of GMPA samples only 720 hours of a year to allow for quick solves. Increasing the sample size will impact running times. A few estimates of how long it should take for 720 hours:
> 1. Single country case studies should take under 2 minutes to solve all 11 scenarios
> 2. Two countries without collaboration should take under 5 minutes to solve all 11 scenarios
> 3. Four countries collaborating should take around 11 minutes to solve all 11 scenarios