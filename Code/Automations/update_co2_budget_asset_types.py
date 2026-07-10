"""
Created on Wed Apr 30 16:20:54 2025

@author: Mónica Sagastuy-Breña
"""
import re
from pathlib import Path
import pandas as pd

# Single country
AUTARKY_RE = re.compile(r"^Autarky_(?P<cc>[A-Z]{2})$")
# Multpile country
COLLAB_RE = re.compile(r"^(?P<ccs>(?:[A-Z]{2}-){1,3}[A-Z]{2})_(?:Autarky|Collaboration)$")
REDUCTION_STEPS = [f"{i * 10}" for i in range(10)]  # "0", "10", ..., "90"

def find_autarky_folders(root: Path) -> dict[str, Path]:
    case_study_dir = root / "Data" / "Case_Study"
    mapping = {
        m.group("cc"): entry
        for entry in case_study_dir.iterdir()
        if entry.is_dir() and (m := AUTARKY_RE.match(entry.name))
    }
    if not mapping:
        raise RuntimeError("No Autarky_<CC> folders found.")
    return mapping

def find_collaboration_folders(root: Path) -> dict[str, Path]:
    case_study_dir = root / "Data" / "Case_Study"
    mapping = {
        m.group("ccs"): entry
        for entry in case_study_dir.iterdir()
        if entry.is_dir() and (m := COLLAB_RE.match(entry.name))
    }
    if not mapping:
        raise RuntimeError("No XX-YY(_Autarky|_Collaboration) folders found.")
    return mapping

def load_co2_budget_table(root: Path) -> pd.DataFrame:
    csv_path = root / "Code" / "Assets" / "CO2_Budget" / "parameters.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing CO2_Budget parameters file: {csv_path}")
    df = pd.read_csv(csv_path)
    df.columns = [c.strip() for c in df.columns]
    return df[["Type", "case_study"]].dropna()

def get_cc_type_group(df: pd.DataFrame, cc: str) -> list[int]:
    matches = df[df["case_study"] == cc]
    if matches.empty:
        raise ValueError(f"No CO2_Budget entries for {cc}")
    return list(matches["Type"].astype(int).sort_values())

def set_co2_asset_type(csv_path: Path, new_type: int):
    if not csv_path.exists():
        print(f"  ⚠ Missing: {csv_path}")
        return
    df = pd.read_csv(csv_path)
    mask = df["Asset_Class"] == "CO2_Budget"
    if not mask.any():
        print(f"  ⚠ No CO2_Budget asset in {csv_path}")
        return
    df.loc[mask, "Asset_Type"] = new_type
    df.to_csv(csv_path, index=False)
    print(f"  ✓ Updated {csv_path.name} to type {new_type}")

def update_folder(name: str, folder: Path, co2_df: pd.DataFrame, skipped: list):
    print(f"\n→ Updating {folder.name}")
    try:
        types = get_cc_type_group(co2_df, name)
    except ValueError as e:
        print(f"  ⚠ {e}")
        skipped.append(name)
        return

    expected_count = 1 + len(REDUCTION_STEPS)
    if len(types) < expected_count:
        print(f"  ⚠ Not enough types ({len(types)}) for {expected_count} folders. Skipping.")
        skipped.append(name)
        return

    # Update BAU
    bau_csv = folder / "BAU" / "Asset_Parameters.csv"
    set_co2_asset_type(bau_csv, types[0])

    # Update 0–90
    for idx, step in enumerate(REDUCTION_STEPS, start=1):
        csv_path = folder / step / "Asset_Parameters.csv"
        set_co2_asset_type(csv_path, types[idx])

def main():
    root = Path(__file__).resolve().parents[2]

    autarky_folders = find_autarky_folders(root)
    collab_folders = find_collaboration_folders(root)
    co2_df = load_co2_budget_table(root)

    skipped = []

    for cc, folder in autarky_folders.items():
        update_folder(cc, folder, co2_df, skipped)

    for cc_combo, folder in collab_folders.items():
        update_folder(cc_combo, folder, co2_df, skipped)

    print("\n✅ Done.")
    if skipped:
        print("\n⚠ Skipped due to missing CO2_Budget parameters:")
        print(", ".join(skipped))

if __name__ == "__main__":
    main()
