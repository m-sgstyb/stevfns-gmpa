# GMPA - STEVFNs modelling
![Logo](img/gmpa_logo.png)

## Set up
This is the STEVFNs model generator branch containing modelling details for the GMPA. For the general details of the model generator see main branch.
To run case studies in this branch, you need to clone the STEVFNs repository as instructed and fetch all remote branches. You will then be able to pull GMPA branch and have a local version of it to work with. 

You will need to have the conda package manager installed for a clean handling of environments and dependencies for the model. See [Conda](https://docs.conda.io/projects/conda/en/latest/user-guide/index.html) for details on this.

### 1. Clone and fetch
In your terminal, navigate to a local directory where you will want to keep the STEVFNs repository folder. Once there, run

```
git clone https://github.com/OmNomNomzzz/STEVFNs.git
```

This should take a minute or two and will create a STEVFNs folder in that directory with all the files from the main branch in the repository. To fetch all branches online, navigate into that folder through `cd STEVFNs` and run:
```
git fetch
```
```
git checkout -b GMPA origin/GMPA
```

This should display:
```
branch 'GMPA' set up to track 'origin/GMPA'.
Switched to a new branch 'GMPA'
```
Once you are in your local GMPA branch, you will need to create a conda environment with a few dependencies to be able to run the models. This can be done through conda and the environment.yaml file.

```
 conda env create -f env/environment.yaml
```
This will create the stevfns environment with CVXPY and other required dependencies to run the model. You can activate the environment as 
```
conda activate stevfns
```
Once active, you will be able to run all the scripts described in the New Workflow below.

> [!IMPORTANT]
> Basic git handling is required to collaborate in this branch. By running the model as described below for case studies assigned to you, there should not be any merge conflicts onto the branch.
> Ensure that ONLY ONE person in the team has already done steps 1. and 2. for all the collaborations in the modelling tracker.
> Ensure that you DO NOT change any python script directly, and you are only adding result files when running the case studies.
> ALWAYS run `git pull` from your STEVFNs repo in GMPA branch and ensure you're working in the correct branch before doing anything.
> Once done with runs, commit and push your updates to the remote branch.

## New Workflow

> [!NOTE]
> The workflow detailed below relates to case study creation and running the model as of June, 2025; it assumes that all data inputs for assets (costs, renewable energy profiles, etc.) have been already been created. It also assumes that the countries we are modelling for are already in the Location Parameters, and that the scenarios for said countries in baseline case studies have been created. Comprehensive documentation of how this is done will be prepared for upcoming phases of the project.

### 0. Update Autarky_XX folders
This step updates all `Asset_Parameters.csv`, `Location_Parameters.csv`, and `System_Parameters.csv` files in every emissions-constraint scenario folder (`90`, `80`, ..., `0`) for one or more Autarky case studies.

#### Prerequisites

Before running this update, ensure:

1. You have manually created or updated the Network_Structure.csv file in the Autarky_XX folder(s) you need to update scenarios for
2. You have also manually created or updated the `Asset_Parameters.csv`, `Location_Parameters.csv`, and `System_Parameters.csv` in the BAU scenario folder
3. **Data structure requirements**  
- The `Asset_Parameters.csv` file in each `Autarky_XX/BAU` folder must have the correct **energy mix**, **location parameters**, and **asset type values** for the case study.  
- The `Network_Structure.csv` file in each `Autarky_XX` folder must also have the correct **energy mix**, **locations**, and **start time, end time** matching the intended configuration.  

These must be verified and updated before running this step, as the script will replicate these values into all scenario folders.

### Parameters

XX,YY,ZZ — Comma-separated list of two-letter ISO country codes (case-insensitive, no spaces required but allowed).

Example:

```
python update_aut_scenarios.py SG,MY,ZA
```
This will update:
```
STEVFNs/Data/Case_Study/Autarky_SG
STEVFNs/Data/Case_Study/Autarky_MY
STEVFNs/Data/Case_Study/Autarky_ZA
```
creating or overwriting scenario folders:
```
90, 80, 70, ..., 0
```
inside each Autarky folder, copying data from the BAU folder.

### 1. Run baseline case studies
This step should be done first by a single person in the team, and all others running case studies should pull these changes before running case studies.

The assumptions for GMPA at its latest stage use a BAU and Least Cost baseline to generate a specific country's emissions reduction profile. In STEVFNs/Data/Case_Study there will be two folders named BAU_No_Action and Least_Cost_Emissions. In these, scenario folders for the countries currently covered in GMPA can be found. By running BAU and LC, we obtain the emissions data to create 11 scenarios of emissions reduction towards 0 MtCO<sub>2</sub>e

The python wrapper, run_cases.py has been created to run main.py through CLI commands and not edit this script to avoid conflicts when several people are working on the modelling.

To run the baseline case studies, BAU_No_Action and Least_Cost_Emissions:

1. In terminal, navigate to your local STEVFNs folder
2. Run conda activate stevfns to ensure you're in the environment with required dependencies
3. Run the following commands (wait until one case study ends to run the next)
(a) for BAU_No_Action
```
python run_cases.py bau
```
(b) for Least_Cost_Emissions
```
python run_cases.py least
```

There is a solver flag included in the wrapper to manually define which solver the model will use to optimise each case study. The default if none is specified is CLARABEL, and the wrapper currently works only with MOSEK and CLARABEL, as we have gotten good results in terms of run times with these solvers.

Running these two case studies will have created total_data_unrounded.csv and total_data.csv inside the case study folders, which will be used to create the emission reduction profiles in step 2. 

### 2. Create emissions reduction profiles
This step should be done first by a single person in the team, and all others running case studies should pull these changes before running case studies.

Based on the BAU (assumes a more limited technology mix) and Least cost (assumes extensive technology mix including e.g. short term and long term storage) emissions, we need to create the "carbon budget" scenarios. We model 11 scenarios from the baseline to 0 for all case studies. These can be calculated through STEVFNs/Code/Automations/generate_carbon_budget.py script.

To run:
* In the terminal, navigate to STEVFNs/Code/Automations, and run
```
python generate_carbon_budget.py
```
* This will automatically create a budget profile or update existing values for single countries based on the most recent total_data files in BAU and Least_Cost. 
* It will then prompt the user to answer whether collaboration emissions should also be created. If yes, enter "y" and click return
* The user will be prompted to enter a comma-separated list of 2-4 countries with a small example. If the collaborations between Germany, France, Turkey and Morocco are desired to be modelled, the user should enter the two-letter ISO abbreviations as:
```
DE,FR,TR,MA
```
This will create *all the possible* sub-collaborations (two-, three-, and four-country combos) between these countries, which will be printed in the terminal. The CO2_Budget profile should also be saved in STEVFNs/Code/Assets/CO2_Budget/parameters.csv file.

> [!NOTE] 
> To create collaboration emissions reduction profiles, the individual countries' emissions should have been calculated in BAU_No_Action and Least_Cost_Emissions case studies (i.e. there should be a scenario folder for that individual country and the case studies ran). 


### 3. Create collaboration case study folders
> [!IMPORTANT] 
> To create the case study folders for multiple countries, both in autarky and collaboration formats, the CO<sub>2</sub> budget for those collaborations must have already been created. 
> If they have not been created, the script will create the folders with a network struture but will exit without generating the scenario folders. 
> The user must then re-run generate_carbon_budget.py, allow for all single country values to be updated, and say yes when prompted to create for a collaboration.

To follow on the example of modelling the possible sub-combinations of Germany, France, Turkey and Morocco done in step 2 for their emission reduction profile:

* In the terminal, navigate to STEVFNs/Code/Automations, and run
```
python generate_collab_case_studies.py . DE FR TR MA
```
Note that in this case, the list is only separated by spaces. The order does not matter, the script will automatically be created with alphabetical combinations as a convention.

For this command to work as written, user needs to be in local/path/to/STEVFNs/Code/Automations. Otherwise, the script will display the usage instructions in your terminal/console, which show
```
python generate_collab_case_studies.py <root_dir> [DE FR TR ...]
```
If in another folder, the user may type out the path to the Automations folder in place of `<root_dir>` and the list of countries afterwards (no need for brackets).

This step will create ready-to-run case study folders for those combinations, both in Autarky (no trade between them) and collaboration (electricity and ammonia trade between them). 

### 4. As a sense-check, update CO2_Budget Asset type in Asset_Parameters.csv
> [!IMPORTANT]
> June/July 2025:
> When several people are running case studies at the same time AVOID, running this script unless previously agreed upon and everyone in the team is aware to pull any changes to their local branches.
> This will avoid potential merge conflicts

This step is especially important if a new individual country has been added as Autarky_XX and BAU_No_Action and Least_Cost_Emissions case studies have been re-ran to include this new country.
It requires to go through step 2, and then running this helper automation script will only ensure that all values in CO2_Budget/parameters.csv for Type are correctly mapped to theie country/collaboration scenarios in all case studies, not only the new one.

* In the terminal, navigate to STEVFNs/Code/Automations, and run
```
python update_co2_budget_asset_types.py
```
> [!NOTE] 
> July, 2025:
> For Phase II, milestone 2, running this step should not be necessary, as all individual countries for this deliverable have been created, and any collaboration generated through step 3 should already correctly map the values.
> However, should something change in emissions reduction, it could be a good sense check to run and ensure these are mapped correctly.

### 5. Run case studies


#### To run single country case studies
Single country case studies, where the naming convention of the case study folder is Autarky_XX with XX being the two-letter ISO code, can be run with the following command example to run Germany with mosek as the solver
```
python run_cases.py DE --solver mosek
```

#### To run multiple country case studies
Collaborations and their autarky comparison (e.g. WW-XX-YY_Autarky and WW-XX-YY_Collab) can be run with a slightly different command. You will need to enter the four-country list of countries that will be collaborating. In Steps 2 and 4, you should have created all the collaboration emissions profile and case study folders through a different helper script. In the example above, we created them for DE, FR, TR, MA. To run all case studies from this combination (i.e. the two-, three- and four-country combinations in a loop), run the following command

```
python run_cases.py DE FR TR MA
```
This will solve all of them with CLARABEL, if you wish to use MOSEK, specify with the --solver flag.

> [!TIP]
> As the number of assets in a network increases, so does the build and sovle time of the problem. The current version of GMPA samples only 720 hours of a year to allow for quick solves. Increasing the sample size will impact running times. A few estimates of how long it should take for 720 hours:
> Using CLI to run python main.py with few other applications using memory at the same time, 
>       1. Single country case studies should take under 2 minutes to solve all 11 scenarios
>       2. Two countries without collaboration should take under 5 minutes to solve all 11 scenarios
>       3. Four countries collaborating should take around 11 minutes to solve all 11 scenarios

Therefore, to run all comabinations of a set of four countries, it should take about two hours to finish, as it will have to run 16 case studies all together. These may be left running overnight, or in the background.

##### Issues when running - troubleshooting
> [!NOTE]
> This command is thought of to be able to run many case studies in a set of countries that are collaborating in the background or overnight consecutively and review results later. The wrapper is designed to skip any case study that, for any reason, does not run and continue with the rest.
>
> If this happens, an error_log will display at the end of the run in the terminal, see below:

There may be times when one of the case studies in the loop does not run. For example, when running python run_cases.py DE FR TR MA in initial testing displayed this error log once the run ended:

```
SUMMARY OF FAILED CASE STUDIES:
- MA-TR_Autarky: Command '['python', 'main.py']' returned non-zero exit status 1.
- MA-TR_Collab: Command '['python', 'main.py']' returned non-zero exit status 1.
```

Of the 16 case studies between those countries, only these two had a problem. The exepction "returned non-zero exit status 1" does not give enough information to solve the issue in this case. To troubleshoot that separately, we need to run the command `python run_cases.py TR MA`, which will only run the `_Autarky` and `_Collab` versions of MA-TR combination, instead of the whole set again.

In the case of this example, doing this quickly returned internal STEVFNs exceptions as:
```
Asset type 29 for asset number 15 failed due to exception: single positional indexer is out-of-bounds
Asset type 29 for asset number 16 failed due to exception: single positional indexer is out-of-bounds
Asset type 29 for asset number 17 failed due to exception: single positional indexer is out-of-bounds
...
Asset type 0 for asset number 48 failed due to exception: single positional indexer is out-of-bounds
Asset type 0 for asset number 49 failed due to exception: single positional indexer is out-of-bounds

```
Checking directly in the folders for MA-TR_Autarky/BAU and  MA-TR_Collab/BAU, it was found that the Location_Parameters.csv had not been updated to include all locations up to this phase. Once this was updated, running `python run_cases.py TR MA` as successful, now displaying `All case studies completed successfully.`.

> [!TIP]
> If you are unable to track down the specific issue in a situation such as this, please contact Mónica or Aniq for support; when contacting:
>   * Include the problematic case study(ies)
>   * Include the error messages shown

Even when the script does run all case studies, results need to be reviewed (see step 6 for more detail) to ensure the data is sensible. If there is a case study with "weird" results, it may need further detailed review and to be run again with tailored parameters or a different solver.
In these cases, there may be times where a specific three or two country combination needs to be run again with MOSEK instead of CLARABEL, for example. Please see the table below for example commands depending on the situation where you may run some specific case studies individually.

| Command                                       | What it does                                            |
| --------------------------------------------- | ---------------------------------------------           |
| `python run_cases.py DE`                      | Runs only `Autarky_DE`                                  |
| `python run_cases.py bau`                     | Runs BAU\_No\_Action                                    |
| `python run_cases.py DE FR --solver mosek`    | Runs DE-FR\_Autarky and DE-FR\_Collab with MOSEK solver |
| `python run_cases.py DE FR MA TR`             | Runs all 2-, 3-, and 4-country combinations             |
| `python run_cases.py DE FR MA TR --sub`       | Runs only `DE-FR-MA-TR_Autarky` and `_Collab`           |



### 6. Review results 
Running main.py will save a mitigation plot in the case study folder, along with other result files. The mitigation plot should look something like this: 
![Logo](img/mitigation_curve_example.png)

Systems cost decrease with higher emissions values, and they tend to have an "elbow" when approaching zero emissions (going left on the X-axis), as costs increase more rapidly when investment is needed in more expensive technologies to completely decarbonise the system modelled.
If the result plot looks off, e.g. has an unexpected "_dip_" or "_peak_", this is likely due to the solver used. On occasion, CLARABEL will find an optimal solution for one of the emissions reduction scenarios that creates these anomalies. This is likely due to a flatter objective function curve. We have seen this be fixed by changing the solver to MOSEK.

MOSEK requires to be installed and a user license, and can be downloaded at [MOSEK Downloads](https://www.mosek.com/downloads/), a trial or personal academic license may be requested through [License Request](https://www.mosek.com/license/request/).

Please contact Aniq or Mónica with any issues.

If the results are sensible, they should be consolidated and formatted for web upload once all relevant case studies have been run. 

### 7. Preparing results for webtool

Once all the required case studies have been run and have total_data_unrounded.csv result files, all results can be compiled and processed for upload by running the STEVFNs/Code/Automations/prepare_data_for_website.py script. Simply run it through an IDE, or through terminal, once in the Automations folder:
```
python prepare_data_for_website.py
```
This will create files and a folder in the STEVFNs/Code/Results/Results_for_Website folder.
All files in the /To_Upload folder here are needed for the results to display in the webtool. 

