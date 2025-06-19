# GMPA - STEVFNs modelling
![Logo](gmpa_logo.png)

This is the STEVFNs model generator branch containing modelling details for the GMPA. For the general details of the model generator and how to install, see main. To run case studies in this branch, you need to clone the STEVFNs repository as instructed and fetch all remote branches. You will then be able to pull GMPA branch and have a local version of it to work with. 


## Workflow
---

> [!NOTE]
> The workflow detailed below relates to case study creation and running the model; it assumes that all data inputs for assets (costs, renewable energy profiles, etc.) have been already been created. It also assumes that the countries we are modelling for are already in the Location Parameters, and that the scenarios for said countries in baseline case studies have been created. Comprehensive documentation of how this is done will be prepared for upcoming phases of the project.


### 1. Run baseline case studies
The assumptions for GMPA at its latest stage use a BAU and Least Cost baseline to generate a specific country's emissions reduction profile. In STEVFNs/Data/Case_Study there will be two folders named BAU_No_Action and Least_Cost_Emissions. In these, scenario folders for the countries currently covered in GMPA can be found. By running BAU and LC, we obtain the emissions data to create 11 scenarios of emissions reduction towards 0 MtCO2e

To run:
    1. Open main.py in an editor
    2. Change case_study_name to "BAU_No_Action" 
    3. If in an IDE, run directly. If you want to run through CLI, open a terminal and navigate to STEVFNs in your local repo, activate the conda environment and run:
    ```
    python main.py
    ```

