"""
Generate Case Studies Script — v3.2
────────────────────────────────────────────────────────

Creates every 2-, 3-, 4-country *_Autarky / *_Collab* case study and a BAU
sub-folder for each, using parameters in `parameters.csv`.

Folder structure assumptions:
- Script is inside: <root_dir>/automation/
- Single-country folders (Autarky_XX) are inside: <root_dir>/Data/Case_Study/
- parameters.csv is located at: <root_dir>/Code/Assets/CO2_Budget/parameters.csv

Usage:
──────
    cd <root_dir>
    python automation/generate_case_studies.py [country1 country2 ...]

    If no countries are passed, all found in Case_Study folder will be used.

Dependencies:
─────────────
    pip install pandas
"""
import itertools
import re
import shutil
import sys
from pathlib import Path
import pandas as pd

# ────────────────────────── Config ────────────────────────── #
AUTARKY_RE     = re.compile(r"^Autarky_(?P<cc>[A-Z]{2})$")
MAX_COMBO_SIZE = 4
NH3_PERIOD     = 96
NH3_TIME       = 108

# ─────────────── Get root based on script's location ─────────────── #
script_path = Path(__file__).resolve()
root_dir = script_path.parents[1]  # assumes script in root_dir/automation/

case_study_dir = root_dir / "Data" / "Case_Study"
co2_params_path = root_dir / "Code" / "Assets" / "CO2_Budget" / "parameters.csv"

# ─────────────────────── Folder Functions ─────────────────────── #
def find_country_folders(root: Path) -> dict[str, Path]:
    mapping = {}
    for entry in root.iterdir():
        m = AUTARKY_RE.match(entry.name)
        if m and entry.is_dir():
            mapping[m.group("cc")] = entry
    if not mapping:
        raise RuntimeError(f"No Autarky_<CC> folders in {root}")
    return mapping

def load_network_csv(folder: Path) -> pd.DataFrame:
    csv = folder / "Network_Structure.csv"
    if not csv.exists():
        raise FileNotFoundError(csv)
    return pd.read_csv(csv)

def location_map_from_co2(dfs) -> dict[str, int]:
    out = {}
    for cc, df in dfs.items():
        row = df.loc[df["Asset_Class"] == "CO2_Budget"]
        if row.empty:
            raise ValueError(f"{cc}: no CO2_Budget row")
        out[cc] = int(row.iloc[0]["Location_1"])
    return out

def union_networks(frames):
    df = pd.concat(frames, ignore_index=True)
    mask = df["Asset_Class"] == "CO2_Budget"
    if mask.sum() > 1:
        df = df.drop(df[mask].index[1:])
    return df.reset_index(drop=True)

def add_transport_assets(df, countries, loc_map):
    pairs = list(itertools.combinations(sorted(countries), 2))
    tmpl  = df.iloc[0].copy()
    new   = []
    nxt   = df["Asset_Number"].max() + 1
    for c1, c2 in pairs:
        for cls in ("EL_Transport", "NH3_Transport"):
            row = tmpl.copy()
            row["Asset_Number"] = nxt; nxt += 1
            row["Asset_Class"] = cls
            row["Location_1"] = loc_map[c1]
            row["Location_2"] = loc_map[c2]
            if cls == "NH3_Transport":
                row["Period"] = NH3_PERIOD
                row["Transport_Time"] = NH3_TIME
            new.append(row)
    return pd.concat([df, pd.DataFrame(new)], ignore_index=True)

def write_network_csv(df, folder: Path):
    folder.mkdir(parents=True, exist_ok=True)
    df = df.copy()
    df["Asset_Number"] = range(len(df))
    df.to_csv(folder / "Network_Structure.csv", index=False)

def copy_bau_static(src_country_folder: Path, dst_bau: Path):
    src_bau = src_country_folder / "BAU"
    for fname in ("Location_Parameters.csv", "System_Parameters.csv"):
        shutil.copy(src_bau / fname, dst_bau / fname)

def load_co2_budget_table(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]
    if "Type" not in df.columns:
        df = df.rename(columns={"git": "Type", "git_": "Type"})
    df = df[df["case_study"].str.contains("_", na=False)]
    return df[["Type", "case_study"]]

def normalise_case_study(txt: str) -> tuple[frozenset[str], str]:
    name, suff = txt.split("_", 1)
    suff = "COLLAB" if suff.upper().startswith("COLLAB") else "COLLAB"
    return frozenset(name.split("-")), suff

def resolve_co2_type(combo_codes, params_df, suffix) -> int:
    want_set = frozenset(combo_codes)
    want_suf = suffix.upper()
    for _, row in params_df.iterrows():
        cs_set, cs_suf = normalise_case_study(str(row["case_study"]))
        if cs_suf == want_suf and cs_set == want_set:
            return int(row["Type"])
    raise ValueError(f"No CO2_Budget Type for {'-'.join(combo_codes)}_{suffix}")

def build_asset_parameters(net_df, co2_type):
    df = net_df[["Asset_Number", "Asset_Class", "Location_1", "Location_2"]].copy()
    def aset(row):
        if row["Asset_Class"] in ("EL_Transport", "NH3_Transport"):
            return 0
        if row["Asset_Class"] == "CO2_Budget":
            return co2_type
        return row["Location_1"] if pd.notna(row["Location_1"]) else row["Location_2"]
    df["Asset_Type"] = df.apply(aset, axis=1)
    return df

def write_asset_parameters(df, bau_folder):
    df.to_csv(bau_folder / "Asset_Parameters.csv", index=False)

# ─────────────────────── Main Function ─────────────────────── #
def main(selected=None):
    country_folders = find_country_folders(case_study_dir)

    if selected:
        selected = [cc.upper() for cc in selected]
        country_folders = {k: v for k, v in country_folders.items() if k in selected}

    if not country_folders:
        raise RuntimeError("No matching country folders found.")

    single_frames = {cc: load_network_csv(p) for cc, p in country_folders.items()}
    loc_map = location_map_from_co2(single_frames)
    co2_params_df = load_co2_budget_table(co2_params_path)

    countries = sorted(country_folders)
    print("Selected countries:", ", ".join(countries))

    for r in range(2, min(MAX_COMBO_SIZE, len(countries)) + 1):
        for combo in itertools.combinations(countries, r):
            name = "-".join(combo)
            f_aut = case_study_dir / f"{name}_Autarky"
            f_col = case_study_dir / f"{name}_Collab"

            union = union_networks([single_frames[c] for c in combo])
            collab = add_transport_assets(union, combo, loc_map)

            write_network_csv(union, f_aut)
            write_network_csv(collab, f_col)

            for folder, net_df, suffix in (
                (f_aut, union, "AUT"),
                (f_col, collab, "COLLAB")
            ):
                bau = folder / "BAU"
                bau.mkdir(parents=True, exist_ok=True)
                copy_bau_static(country_folders[combo[0]], bau)
                co2_type = resolve_co2_type(combo, co2_params_df, suffix)
                write_asset_parameters(build_asset_parameters(net_df, co2_type), bau)

            print(f"✓ {name}: Autarky & Collab written")

# ─────────────────────── Entry Point ─────────────────────── #
if __name__ == "__main__":
    # Get country codes from CLI if given, otherwise use all found
    main(sys.argv[1:] if len(sys.argv) > 1 else None)
