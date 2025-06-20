#!/usr/bin/env python3
import os
import sys
import subprocess
import shutil

# Path definitions
base_dir = os.path.dirname(os.path.realpath(__file__)) 
root_dir = os.path.dirname(os.path.dirname(base_dir)) # STEVFNs repo root dir
results_root = os.path.join(root_dir, "Code", "Results")

# --- Step 1: Run Consolidate.py ---
case_study_dir = os.path.join(root_dir, "Data", "Case_Study")
consolidate_script = os.path.join(case_study_dir, "Consolidate.py")
if not os.path.isfile(consolidate_script):
    print(f"❌Error: {consolidate_script} not found", file=sys.stderr)
    sys.exit(1)
subprocess.run([sys.executable, consolidate_script], cwd=case_study_dir, check=True)
print("✅ Consolidate.py completed") # Base files saved in case_study_dir

# --- Step 2: Run Mitigation_Potential_Diagram_Data_script.py ---
mitigation_script = os.path.join(base_dir, "Mitigation_Potential_Diagram_Data_script.py")
if not os.path.isfile(mitigation_script):
    print(f"❌Error: {mitigation_script} not found", file=sys.stderr)
    sys.exit(1)
subprocess.run([sys.executable, mitigation_script], cwd=case_study_dir, check=True)
print("✅ Mitigation_Potential_Diagram_Data_script.py completed")

# --- Step 3: Copy the six CSVs to Results_for_Website/website ---
results_dir = os.path.join(results_root, "Results_for_Website")
website_dir = os.path.join(results_dir, "To_Upload")
os.makedirs(website_dir, exist_ok=True)

files_to_copy = [
    "total_data_autarky.csv",
    "total_data_collaboration.csv",
    "combined_data_autarky.csv",
    "combined_data_collaboration.csv",
    # "heatmap_autarky.csv",
    "heatmap_collaboration.csv",
]

for fname in files_to_copy:
    src = os.path.join(results_dir, fname)
    dst = os.path.join(website_dir, fname)
    if os.path.isfile(src):
        shutil.copy(src, dst)
        print(f"Copied {fname} → Results_for_Website/To_Upload")
    else:
        print(f"⚠️WARNING: {src} not found", file=sys.stderr)

# --- Step 4: Run readable_names_total_data_script.py in the website directory ---
readable_script = os.path.join(base_dir, "readable_names_total_data_script.py")
if not os.path.isfile(readable_script):
    print(f"❌Error: {readable_script} not found", file=sys.stderr)
    sys.exit(1)
subprocess.run([sys.executable, readable_script], cwd=website_dir, check=True)
print("✅ readable_names_total_data_script.py completed")

# --- Step 5: Collect files for upload ---
# to_upload_dir = os.path.join(results_dir, "To_Upload")
# os.makedirs(to_upload_dir, exist_ok=True)

# upload_files = [
#     # from website root
#     os.path.join(website_dir, "combined_data_autarky.csv"),
#     os.path.join(website_dir, "combined_data_collaboration.csv"),
#     os.path.join(website_dir, "heatmap_collaboration.csv"),
#     # Copy the replaced total_data files with readable names
#     os.path.join(website_dir, "total_data_autarky.csv"),
#     os.path.join(website_dir, "total_data_collaboration.csv"),
# ]

# for src in upload_files:
#     if os.path.isfile(src):
#         dst = os.path.join(to_upload_dir, os.path.basename(src))
#         shutil.copy(src, dst)
#         print(f"Copied {os.path.basename(src)} → Results_for_Website/To_Upload")
#     else:
#         print(f" ⚠️ WARNING: {src} not found; skipping", file=sys.stderr)

print("✅ All files collected in To_Upload/")
