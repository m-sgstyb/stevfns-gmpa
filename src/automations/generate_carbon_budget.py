"""
Generate the time-varying CO2e budget profiles in reinvestment period 
cumulative caps for STEVFNs GMPA modelling

TEMPORARY TEST VERSION
----------------------
Each scenario (e.g. 2C or 2.5C pathways) is defined by two values: the 
cumulative emissions allowed in the first and last reinvestment windows.
Windows in between are filled with linear interpolation. Currently, values
hardcoded below.

In Dev: The linear interpolation will be replaced with AR6 derived values
to represent emission reduction pathways in this context; the output format
and pipeline hooks stay the same

How it plugs into CO2_Budget_Asset
----------------------------------
Two files in src/assets/CO2_Budget/ :

  parameters.csv                   (one row per CASE, not per scenario)
      Type, trajectory_filename, case_study
      0,    emissions_budget_profiles,  SG
      1,    emissions_budget_profiles,  ID-AU

  profiles/emissions_budget_profiles.csv (one shared file, all cases/scenarios)
      scenario_name, co2_budget, co2_budget_unit, case_study
      2C,            765000,     MtCO2e,           SG       (one row per period)

  * Network_Structure / Asset_Parameters 'Asset_Type' for CO2_Budget = Type.
  * The asset opens <trajectory_filename>.csv, then filters on
      scenario_name == network.scenario_name  (the 2C / 2.5C folder name)
      case_study    == the case_study in its parameters.csv row
    and needs exactly num_periods rows, in chronological order.

Cases are discovered from data/Case_Study folder names:
    Autarky_ID/2C, Autarky_ID/2.5C      -> case "ID"
    ID-AU_Collab/2C, ID-AU_Collab/2.5C  -> case "ID-AU"
NOTE: This test uses explicit case study name rather than GMPA processing
Collaboration profiles = sum of the member countries' profiles (read from the
shared profile file), per scenario and per period.

Run from src/automations:
    uv run python generate_carbon_budget.py
"""

import csv
import os

# ----------------------------------------------------------------------------
# MANUAL INPUTS (per country, cumulative emissions per reinvestment period)
#   scenario_name (must match the scenario folder name): (first period, last period)
# ----------------------------------------------------------------------------
UNIT = "MtCO2e"
SCENARIOS = {
    "2C": (1000000, 500000),
    "2.5C": (1500000, 750000),
}

# Must equal ceil(project_life / reinvestment_period) in the model, otherwise
# CO2_Budget_Asset._load_budget_trajectory raises a ValueError.
N_PERIODS = 6

# False: only create missing (scenario, case) profiles, keep existing ones so a
#        later credible profile is never overwritten by the pipeline.
# True : regenerate every discovered case/scenario from SCENARIOS above.
OVERWRITE_EXISTING = True

# ----------------------------------------------------------------------------
# Paths (run from Code/Automations)
# ----------------------------------------------------------------------------
CASE_STUDY_DIR = os.path.join("..", "..", "Data", "Case_Study")
ASSET_DIR = os.path.join("..", "Assets", "CO2_Budget")
PROFILE_NAME = "emissions_budget_profiles"
PARAMS_FILE = os.path.join(ASSET_DIR, "parameters.csv")
PROFILE_FILE = os.path.join(ASSET_DIR, "profiles", PROFILE_NAME + ".csv")

PARAM_HEADER = ["Type", "trajectory_filename", "case_study"]
PROFILE_HEADER = ["scenario_name", "co2_budget", "co2_budget_unit", "case_study"]


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def read_rows(path):
    """Read a CSV as a list of dicts (all strings; avoids 'NA' -> NaN issues)."""
    if not os.path.exists(path):
        return []
    with open(path, mode="r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_rows(path, header, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def fmt(val):
    return f"{val:.6f}".rstrip("0").rstrip(".")


def linear_profile(first, last, n):
    if n == 1:
        return [first]
    return [first + (last - first) * k / (n - 1) for k in range(n)]


def discover_cases():
    """Return (countries, collabs) from folder names in the case study dir."""
    countries, collabs = [], []
    for name in sorted(os.listdir(CASE_STUDY_DIR)):
        if not os.path.isdir(os.path.join(CASE_STUDY_DIR, name)):
            continue
        if name.endswith("_Collab"):
            collabs.append(name[: -len("_Collab")])  # e.g. "ID-AU"
        elif name.startswith("Autarky_"):
            countries.append(name[len("Autarky_"):]) # e.g. "ID"
        else:
            countries.append(name)
    return countries, collabs


def get_profile(profile_rows, scenario, case):
    """Values for (scenario, case) in file order; empty list if absent."""
    return [float(r["co2_budget"]) for r in profile_rows
            if r["scenario_name"] == scenario and r["case_study"] == case]


def set_profile(profile_rows, scenario, case, values):
    """Replace (scenario, case) rows with new values. Returns the new row list."""
    rows = [r for r in profile_rows
            if not (r["scenario_name"] == scenario and r["case_study"] == case)]
    rows += [{"scenario_name": scenario, "co2_budget": fmt(v),
              "co2_budget_unit": UNIT, "case_study": case} for v in values]
    return rows


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def main():
    # countries, collabs = discover_cases() # to automate later generation
    countries = ["diy-kit-test"]
    collabs = [""]
    print(f"Count)ries: {countries}")
    print(f"Collaborations: {collabs}")

    profile_rows = read_rows(PROFILE_FILE)
    param_rows = read_rows(PARAMS_FILE)

    for scen, (first, last) in SCENARIOS.items():
        if first < 0 or last < 0:
            raise SystemExit(f"Scenario {scen}: negative emissions not supported.")
        if last > first:
            print(f"⚠️ Scenario {scen}: last > first (emissions increase).")

        # 1) single countries
        for c in countries:
            if get_profile(profile_rows, scen, c) and not OVERWRITE_EXISTING:
                print(f"Kept existing profile: {c} / {scen}")
                continue
            values = linear_profile(first, last, N_PERIODS)
            profile_rows = set_profile(profile_rows, scen, c, values)
            print(f"Generated profile: {c} / {scen}")

        # 2) collaborations = sum of member profiles (already in the file)
        for collab in collabs:
            if get_profile(profile_rows, scen, collab) and not OVERWRITE_EXISTING:
                print(f"Kept existing profile: {collab} / {scen}")
                continue
            member_profiles = [get_profile(profile_rows, scen, m)
                               for m in collab.split("-")]
            if any(len(p) != N_PERIODS for p in member_profiles):
                print(f"⚠️ Skipping {collab} / {scen}: a member has no "
                      f"{N_PERIODS}-period profile for this scenario.")
                continue
            values = [sum(v) for v in zip(*member_profiles)]
            profile_rows = set_profile(profile_rows, scen, collab, values)
            print(f"Generated collaboration profile: {collab} / {scen}")

    # 3) parameters.csv: one row per case that has a profile
    existing = {r["case_study"]: int(r["Type"]) for r in param_rows}
    next_type = max(existing.values()) + 1 if existing else 0
    profile_cases = {r["case_study"] for r in profile_rows}
    for case in countries + collabs:
        if case in profile_cases and case not in existing:
            param_rows.append({"Type": next_type,
                               "trajectory_filename": PROFILE_NAME,
                               "case_study": case})
            existing[case] = next_type
            next_type += 1

    write_rows(PROFILE_FILE, PROFILE_HEADER, profile_rows)
    write_rows(PARAMS_FILE, PARAM_HEADER, param_rows)

    print("\nCO2_Budget Type for each case (use as Asset_Type in Asset_Parameters):")
    for case in countries + collabs:
        if case in existing:
            print(f"  {case}: {existing[case]}")
    print(f"✅ Done. Wrote {PARAMS_FILE} and {PROFILE_FILE}")


if __name__ == "__main__":
    main()