# Quick Start

Once the repository has been installed locally via the instructions at [Installation](installation.md), and running `uv sync` to set up the virtual environment, create your own local branch for testing.
Follow the next steps for initial setup and testing.

### Create your local branch

To avoid editing directly in the main branch, create your own local branch to test the model and run your own case studies.
You may choose a branch name, such as "my-test" or "custom-runs": from your command line replace `<branch-name>` in the following prompt with your chosen name and, run

```
git checkout -b <branch-name>
```

If named "my-test", the command is therefore
```
git checkout -b my-test
```
This will create a new branch where you can start testing the model and creating your own case studies


### Quick run pre-defined test-collab case study

The repository natively includes some input data and a case study defined for a two-country collaboration. This is located in Case_Study/test-collab. 

To run this case, from the repository root in your terminal, run

```
uv run python run_cases.py --name test-collab
```

Your terminal should quickly solve and display something like this: 

```console
--- Running: test-collab with clarabel solver ---

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

!!! note
    A plot window will open after the run completes. Close it to view other result plots and return control to your terminal.

Once you have been able to run the pre-defined minimal case study, you can create your own and run the model.
Guidance on requirements and workflow for this can be found in [Case Study Setup](../setup/case-study-setup.md).