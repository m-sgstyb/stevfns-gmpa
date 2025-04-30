import itertools, re, shutil, sys
from pathlib import Path
import pandas as pd

# ───────────────────────── Config ───────────────────────── #

AUTARKY_RE      = re.compile(r"^Autarky_(?P<cc>[A-Z]{2})$")
MAX_COMBO_SIZE  = 4
NH3_PERIOD      = 96
NH3_TIME        = 108
REDUCTION_STEPS = [f"{i * 10}" for i in range(10)]   # 0 … 100 %

# ─────────────── discover single-country dirs ─────────────── #

def find_country_folders(root: Path) -> dict[str, Path]:
    folder = folder.resolve()
    mapping = {
        m.group("cc"): entry
        for entry in folder.iterdir()
        if (m := AUTARKY_RE.match(entry.name)) and entry.is_dir()
    }
    if not mapping:
        raise RuntimeError(f"No Autarky_<CC> folders in {folder}")
    return mapping


def load_network_csv(folder: Path) -> pd.DataFrame:
    csv = folder / "Network_Structure.csv"
    if not csv.exists():
        raise FileNotFoundError(csv)
    return pd.read_csv(csv)

# ─────────────── Network helpers ─────────────── #

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
    dup = df[df["Asset_Class"] == "CO2_Budget"].index[1:]
    if not dup.empty:
        df = df.drop(dup)
    return df.reset_index(drop=True)


def add_transport_assets(df, countries, loc_map):
    pairs = list(itertools.combinations(sorted(countries), 2))
    tmpl  = df.iloc[0].copy()
    new   = []
    nxt   = df["Asset_Number"].max() + 1
    for c1, c2 in pairs:
        # EL_Transport
        row = tmpl.copy()
        row["Asset_Number"], row["Asset_Class"] = nxt, "EL_Transport"
        row["Location_1"],  row["Location_2"]   = loc_map[c1], loc_map[c2]
        new.append(row); nxt += 1
        # NH3_Transport
        row = tmpl.copy()
        row["Asset_Number"], row["Asset_Class"] = nxt, "NH3_Transport"
        row["Location_1"],  row["Location_2"]   = loc_map[c1], loc_map[c2]
        row["Period"],      row["Transport_Time"] = NH3_PERIOD, NH3_TIME
        new.append(row); nxt += 1
    if new:
        df = pd.concat([df, pd.DataFrame(new)], ignore_index=True)
    return df


def write_network_csv(df, folder: Path):
    folder.mkdir(parents=True, exist_ok=True)
    df = df.copy()
    df["Asset_Number"] = range(len(df))
    df.to_csv(folder / "Network_Structure.csv", index=False)

# ─────────────── BAU static files ─────────────── #

def copy_bau_static(src_country_folder: Path, dst_bau: Path):
    src_bau = src_country_folder / "BAU"
    for fname in ("Location_Parameters.csv", "System_Parameters.csv"):
        shutil.copy(src_bau / fname, dst_bau / fname)

# ─────────────── CO₂-Budget parameter table ─────────────── #

def load_co2_budget_table(root: Path) -> pd.DataFrame:
    csv_path = root / "../Assets/CO2_Budget/parameters.csv"
    df = pd.read_csv(csv_path)
    df.columns = [c.strip() for c in df.columns]
    if "Type" not in df.columns:
        df = df.rename(columns={"git": "Type", "git_": "Type"})
    return df[df["case_study"].str.contains("_", na=False)][["Type", "case_study"]]


def normalise_case_study(txt: str) -> tuple[frozenset[str], str]:
    name, suff = txt.split("_", 1)
    suff = "COLLAB" if suff.upper().startswith("COLLAB") else "AUT"
    return frozenset(sorted(name.split("-"))), suff


def resolve_co2_type(combo_codes, params_df, suffix) -> int:
    want_set, want_suf = frozenset(sorted(combo_codes)), suffix.upper()
    for _, row in params_df.iterrows():
        cs_set, cs_suf = normalise_case_study(str(row["case_study"]))
        if cs_set == want_set and cs_suf == want_suf:
            return int(row["Type"])
    raise ValueError(f"No CO2_Budget Type for {'-'.join(combo_codes)}_{suffix}")

# ─────────────── Asset_Parameters builder ─────────────── #

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


def write_asset_parameters(df, folder: Path):
    df.to_csv(folder / "Asset_Parameters.csv", index=False)

# ─────────────── Reduction helpers ─────────────── #

def clone_folder(src: Path, dst: Path):
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def bump_co2_asset_type(src_csv: Path, dst_csv: Path, offset: int):
    df = pd.read_csv(src_csv)
    mask = df["Asset_Class"] == "CO2_Budget"
    df.loc[mask, "Asset_Type"] += offset
    df.to_csv(dst_csv, index=False)

# ─────────────── main ─────────────── #

def main(root_dir, selected_countries=None):
    root = Path(root_dir).resolve()
    case_study_dir = root / "../../Data/Case_Study"
    output_dir     = case_study_dir

    country_folders = find_country_folders(root)
    if selected_countries:
        selected_countries = [cc.upper() for cc in selected_countries]
        unknown = set(selected_countries) - set(country_folders)
        if unknown:
            raise ValueError(f"Unknown country codes: {', '.join(unknown)}")
        country_folders = {cc: country_folders[cc] for cc in selected_countries}
    single_frames   = {cc: load_network_csv(p) for cc, p in country_folders.items()}
    loc_map         = location_map_from_co2(single_frames)
    co2_params_df   = load_co2_budget_table(root)

    countries = sorted(country_folders)
    print("Detected countries:", ", ".join(countries))

    for r in range(2, min(MAX_COMBO_SIZE, len(countries)) + 1):
        for combo in itertools.combinations(countries, r):
            name   = "-".join(combo)
            f_aut  = output_dir / f"{name}_Autarky"
            f_col  = output_dir / f"{name}_Collab"

            union  = union_networks([single_frames[c] for c in combo])
            coll   = add_transport_assets(union, combo, loc_map)

            write_network_csv(union, f_aut)
            write_network_csv(coll,  f_col)

            for folder, net_df, suf in (
                (f_aut, union, "AUT"),
                (f_col, coll,  "COLLAB"),
            ):
                bau = folder / "BAU"
                bau.mkdir(parents=True, exist_ok=True)
                copy_bau_static(country_folders[combo[0]], bau)
                co2_type = resolve_co2_type(combo, co2_params_df, suf)
                write_asset_parameters(build_asset_parameters(net_df, co2_type), bau)

                for idx, step_name in enumerate(REDUCTION_STEPS, start=1):
                    dst = folder / step_name
                    clone_folder(bau, dst)
                    bump_co2_asset_type(
                        bau / "Asset_Parameters.csv",
                        dst / "Asset_Parameters.csv",
                        offset=idx
                    )

            print(f"✓  {name}: Autarky & Collab (reductions) done")

# ─────────────── script entry ─────────────── #

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate_case_studies.py <root_dir> [CC1 CC2 CC3 ...]")
        sys.exit(1)

    root_dir = sys.argv[1]
    selected_countries = sys.argv[2:] if len(sys.argv) > 2 else None
    main(root_dir, selected_countries)
