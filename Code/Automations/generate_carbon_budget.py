import sys
import csv
import itertools
import os

def process_combination(combo, country_emissions):
    factors = [round(x / 10, 1) for x in range(0, 11)]

    sum_bau = sum(country_emissions[c][0] for c in combo)
    sum_lc  = sum(country_emissions[c][1] for c in combo)

    sum_bau_30 = sum_bau * 30
    sum_lc_30  = sum_lc * 30

    bau_factors = [sum_bau_30 * f for f in factors]

    less_equal_list = [bf for bf in bau_factors if bf <= sum_lc_30]
    greater_list    = [bf for bf in bau_factors if bf > sum_lc_30]

    final_values = []
    final_values.extend(less_equal_list)

    num_greater = len(greater_list)
    for i in range(1, num_greater + 1):
        new_val = (i * sum_lc_30) / num_greater
        final_values.append(new_val)

    final_values.sort()

    return final_values

def read_country_emissions():

    bau_path = os.path.join("..", "..", "Data", "Case_Study", "BAU_No_Action", "total_data_unrounded.csv")
    lc_path = os.path.join("..", "..", "Data", "Case_Study", "Least_Cost_Emissions", "total_data_unrounded.csv")

    def extract_first_emissions_per_country(file_path):
        emissions = {}
        seen = set()
        with open(file_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                country = row["country_1"].strip()
                if country and country not in seen:
                    try:
                        emissions[country] = float(row["collaboration_emissions"])
                        seen.add(country)
                    except ValueError:
                        print(f"⚠️ Could not parse emissions for {country} in {file_path}")
        return emissions

    bau_emissions = extract_first_emissions_per_country(bau_path)
    lc_emissions = extract_first_emissions_per_country(lc_path)

    all_countries = set(bau_emissions.keys()).union(lc_emissions.keys())

    country_emissions = {}
    for country in all_countries:
        bau = bau_emissions.get(country)
        lc = lc_emissions.get(country)

        if bau is None:
            print(f"⚠️ Country '{country}' not found in BAU emissions data.")
        if lc is None:
            print(f"⚠️ Country '{country}' not found in Least Cost emissions data.")

        if bau is not None and lc is not None:
            country_emissions[country] = (bau, lc)

    return country_emissions

def load_existing_cases(output_file):
    existing_cases = {}
    if os.path.exists(output_file):
        with open(output_file, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                case = row['case_study']
                if case not in existing_cases:
                    existing_cases[case] = []
                existing_cases[case].append(row['maximum_budget'])
    return existing_cases

def ensure_file_ends_with_newline(file_path):
    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
        with open(file_path, mode='rb+') as f:
            f.seek(-1, os.SEEK_END)
            last_char = f.read(1)
            if last_char != b'\n':
                f.write(b'\n')

def write_parameters(output_file, case_study, values, starting_type):
    ensure_file_ends_with_newline(output_file)  # 🛡 Ensure newline before appending

    with open(output_file, mode='a', newline='', encoding='utf-8') as out_f:
        writer = csv.writer(out_f)
        for val in values:
            formatted_val = f"{val:.2E}" if abs(val) >= 1000 else f"{val:.6f}"
            writer.writerow([starting_type, formatted_val, "MtCO2e", case_study])
            starting_type += 1
    return starting_type

def initialize_output_file(output_file):
    if not os.path.exists(output_file):
        with open(output_file, mode='w', newline='', encoding='utf-8') as out_f:
            writer = csv.writer(out_f)
            writer.writerow(["Type", "maximum_budget", "maximum_budget_unit", "case_study"])

def update_existing_case_values(output_file, case_study, new_values):
    if not os.path.exists(output_file):
        return

    with open(output_file, mode='r', encoding='utf-8') as f:
        rows = list(csv.reader(f))

    header = rows[0]
    updated_rows = []
    value_idx = 0

    for row in rows[1:]:
        if row[3] == case_study and value_idx < len(new_values):
            val = new_values[value_idx]
            formatted_val = f"{val:.2E}" if abs(val) >= 1000 else f"{val:.6f}"
            row[1] = formatted_val  # Replace only the maximum_budget
            value_idx += 1
        updated_rows.append(row)

    # If the case doesn't exist, append new rows
    if value_idx == 0:
        return False  # Signal that it was not updated (new case)

    with open(output_file, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(updated_rows)
    return True


def prompt_for_collaboration():
    resp = input("Do you want to generate parameters for a collaboration? (y/n): ").strip().lower()
    if resp.startswith("y"):
        combo = input("Enter comma-separated list of maximum 4 countries (e.g., ID,SG): ")
        return [c.strip().upper() for c in combo.split(",") if c.strip()]
    return None

def main():
    input_file = os.path.join("..", "..", "Data", "Case_Study", "input.csv")
    output_file = os.path.join("..", "Assets", "CO2_Budget", "parameters.csv")

    initialize_output_file(output_file)
    country_emissions = read_country_emissions()
    existing_cases = load_existing_cases(output_file)

    type_index = sum(len(v) for v in existing_cases.values())

    # Process all single-country cases
    for country in country_emissions:
        case_study = country
        #updated = update_existing_case_values(output_file, case_study, values)
        if case_study not in existing_cases or len(existing_cases[case_study]) < 11:
            print(f"Generating parameters for: {country}")
            values = process_combination([country], country_emissions)
            type_index = write_parameters(output_file, case_study, values, type_index)
        elif case_study in existing_cases:
             print(f"Updating parameters for: {country}")
             values = process_combination([country], country_emissions)
             updated = update_existing_case_values(output_file, case_study, values)
    # Ask if the user wants to add collaborations
    while True:
        combo = prompt_for_collaboration()
        if not combo:
            break
    #if combo:
        if len(combo) > 4:
            print("⚠️ Please enter no more than 4 countries for collaboration.")
        else:
            # Generate all unique combinations of size 2 to len(combo)
            for r in range(2, len(combo) + 1):
                for sub_combo in itertools.combinations(combo, r):
                    combo_sorted = sorted(sub_combo)
                    case_study = "-".join(combo_sorted)

                    if case_study in existing_cases:
                        print(f"Updating collaboration: {case_study}")
                        try:
                            values = process_combination(combo_sorted, country_emissions)
                            updated = update_existing_case_values(output_file, case_study, values)
                        except KeyError as e:
                            print(f"⚠️ Country not found in emissions data: {e}")
                    else:
                        try:
                            print(f"Generating collaboration: {case_study}")
                            type_index = write_parameters(output_file, case_study, values, type_index)
                        except KeyError as e:
                            print(f"⚠️ Country not found in emissions data: {e}")

    print("✅ Done! Parameters written to parameters.csv")

if __name__ == "__main__":
    main()
