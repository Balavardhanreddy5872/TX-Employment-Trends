"""Cleaning + validation of LODES8 Texas files.

Blocks (15-digit GEOIDs) are aggregated to census tracts (11-digit) to (a) cut the row count by
~100x and (b) dampen the synthetic noise LEHD injects at block level for confidentiality.
Every raw file goes through explicit data-quality checks whose results are written to
``outputs/reports/data_quality.md`` so the cleaning is auditable.

Usage: python -m src.clean
"""
from __future__ import annotations

import json
import re

import geopandas as gpd
import numpy as np
import pandas as pd

from src.config import (AGE_BANDS, HOUSTON_MSA_COUNTIES, INTERIM, NAICS_SECTORS, OD_YEARS, RAC_YEARS,
                        RAW, REPORT_DIR, WAC_YEARS, WAGE_BANDS)

SECTOR_COLS = list(NAICS_SECTORS)
WAGE_COLS, AGE_COLS = list(WAGE_BANDS), list(AGE_BANDS)
RENAME = {"C000": "jobs", "CA01": "age_u30", "CA02": "age_30_54", "CA03": "age_55p",
          "CE01": "wage_low", "CE02": "wage_mid", "CE03": "wage_high",
          **{c: c.lower() for c in SECTOR_COLS}}
EARTH_RADIUS_MI = 3958.756


# ----------------------------------------------------------------------------- helpers
def haversine_miles(lat1, lon1, lat2, lon2) -> np.ndarray:
    """Great-circle distance in miles (vectorised)."""
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_MI * np.arcsin(np.sqrt(a))


def tract_of(geocode: pd.Series) -> pd.Series:
    """15-digit block GEOID -> 11-digit tract GEOID."""
    return geocode.str.slice(0, 11)


def clean_county_name(name: str) -> str:
    return re.sub(r"\s+County,\s*TX$", "", name)


# ----------------------------------------------------------------------------- dimensions
def build_dim_tract() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Tract dimension (names, county, CBSA, centroid) + block coordinate lookup for OD distances."""
    xw = pd.read_csv(RAW / "tx_xwalk.csv.gz", dtype=str,
                     usecols=["tabblk2020", "cty", "ctyname", "trct", "cbsa", "cbsaname", "blklatdd", "blklondd"])
    xw["blklatdd"], xw["blklondd"] = xw["blklatdd"].astype(float), xw["blklondd"].astype(float)
    blocks = xw[["tabblk2020", "blklatdd", "blklondd"]].rename(
        columns={"tabblk2020": "geocode", "blklatdd": "lat", "blklondd": "lon"})

    dim = (xw.groupby("trct")
             .agg(county_fips=("cty", "first"), county_name=("ctyname", "first"),
                  cbsa=("cbsa", "first"), cbsa_name=("cbsaname", "first"),
                  block_lat=("blklatdd", "mean"), block_lon=("blklondd", "mean"))
             .reset_index().rename(columns={"trct": "tract"}))
    dim["county_name"] = dim["county_name"].map(clean_county_name)
    dim["in_houston_msa"] = dim["county_fips"].isin(HOUSTON_MSA_COUNTIES).astype(int)
    dim["is_harris"] = (dim["county_fips"] == "48201").astype(int)

    # Prefer true polygon centroids (projected to Texas Centric Albers) over the block-point mean.
    tracts = gpd.read_file(f"zip://{RAW / 'geo' / 'cb_2023_48_tract_500k.zip'}")
    cent = tracts.to_crs(3083).geometry.centroid.to_crs(4326)
    cent_df = pd.DataFrame({"tract": tracts["GEOID"], "lat": cent.y, "lon": cent.x,
                            "land_sqmi": tracts["ALAND"] / 2_589_988.11})
    dim = dim.merge(cent_df, on="tract", how="left")
    dim["lat"], dim["lon"] = dim["lat"].fillna(dim["block_lat"]), dim["lon"].fillna(dim["block_lon"])
    dim = dim.drop(columns=["block_lat", "block_lon"])
    return dim, blocks


# ----------------------------------------------------------------------------- WAC / RAC
def clean_lodes_area(kind: str, year: int, valid_tracts: set[str]) -> tuple[pd.DataFrame, dict]:
    """Clean one WAC (workplace) or RAC (residence) year and aggregate to tract."""
    key = "w_geocode" if kind == "wac" else "h_geocode"
    path = RAW / kind / f"tx_{kind}_S000_JT00_{year}.csv.gz"
    df = pd.read_csv(path, dtype={key: str}, usecols=[key, "C000", *AGE_COLS, *WAGE_COLS, *SECTOR_COLS])
    n_raw = len(df)

    qa = {"kind": kind, "year": year, "rows_raw": n_raw,
          "dup_geocodes": int(df[key].duplicated().sum()),
          "bad_geocode_len": int((df[key].str.len() != 15).sum()),
          "negative_values": int((df.drop(columns=key) < 0).any(axis=1).sum()),
          "null_values": int(df.isna().any(axis=1).sum()),
          "sector_sum_mismatch": int((df[SECTOR_COLS].sum(axis=1) != df["C000"]).sum()),
          "wage_sum_mismatch": int((df[WAGE_COLS].sum(axis=1) != df["C000"]).sum()),
          "age_sum_mismatch": int((df[AGE_COLS].sum(axis=1) != df["C000"]).sum()),
          "total_jobs_raw": int(df["C000"].sum())}

    df = df.drop_duplicates(key)
    df = df[(df[key].str.len() == 15) & ~df.isna().any(axis=1)]
    df["tract"] = tract_of(df[key])
    qa["blocks_not_in_xwalk_tract"] = int((~df["tract"].isin(valid_tracts)).sum())
    df = df[df["tract"].isin(valid_tracts)]

    out = df.drop(columns=key).groupby("tract", as_index=False).sum().rename(columns=RENAME)
    out.insert(0, "year", year)
    qa.update(rows_clean=len(df), tracts=len(out), total_jobs_clean=int(out["jobs"].sum()))
    return out, qa


# ----------------------------------------------------------------------------- OD
DIST_BINS = [0, 10, 25, 50, np.inf]
DIST_LABELS = ["lt10", "10_25", "25_50", "50plus"]


def clean_od(year: int, blocks: pd.DataFrame, valid_tracts: set[str]) -> tuple[pd.DataFrame, dict]:
    """Clean one OD (main, JT00) year: keep flows touching the Houston MSA, compute straight-line
    commute distance at block level, then aggregate to tract-pair."""
    path = RAW / "od" / f"tx_od_main_JT00_{year}.csv.gz"
    cols = ["w_geocode", "h_geocode", "S000", "SE01", "SE02", "SE03", "SI01", "SI02", "SI03"]
    od = pd.read_csv(path, dtype={"w_geocode": str, "h_geocode": str}, usecols=cols)
    qa = {"kind": "od", "year": year, "rows_raw": len(od), "total_jobs_raw": int(od["S000"].sum()),
          "dup_pairs": int(od.duplicated(["w_geocode", "h_geocode"]).sum()),
          "negative_values": int((od[cols[2:]] < 0).any(axis=1).sum()),
          "wage_sum_mismatch": int((od[["SE01", "SE02", "SE03"]].sum(axis=1) != od["S000"]).sum())}

    msa = tuple(HOUSTON_MSA_COUNTIES)
    touches = od["w_geocode"].str.slice(0, 5).isin(msa) | od["h_geocode"].str.slice(0, 5).isin(msa)
    od = od[touches].drop_duplicates(["w_geocode", "h_geocode"]).copy()

    b = blocks.set_index("geocode")
    w, h = b.reindex(od["w_geocode"]), b.reindex(od["h_geocode"])
    od["dist_mi"] = haversine_miles(h["lat"].to_numpy(), h["lon"].to_numpy(), w["lat"].to_numpy(), w["lon"].to_numpy())
    qa["pairs_missing_coords"] = int(od["dist_mi"].isna().sum())
    od = od.dropna(subset=["dist_mi"])

    od["w_tract"], od["h_tract"] = tract_of(od["w_geocode"]), tract_of(od["h_geocode"])
    od = od[od["w_tract"].isin(valid_tracts) & od["h_tract"].isin(valid_tracts)]
    od["dist_bin"] = pd.cut(od["dist_mi"], DIST_BINS, labels=DIST_LABELS, right=False)
    for lab in DIST_LABELS:
        od[f"jobs_{lab}"] = np.where(od["dist_bin"] == lab, od["S000"], 0)
    od["dist_x_jobs"] = od["dist_mi"] * od["S000"]
    od["dist_x_low"] = od["dist_mi"] * od["SE01"]
    od["dist_x_high"] = od["dist_mi"] * od["SE03"]
    od["low_25plus"] = np.where(od["dist_mi"] >= 25, od["SE01"], 0)

    sums = ["S000", "SE01", "SE02", "SE03", "SI01", "SI02", "SI03", *[f"jobs_{lab}" for lab in DIST_LABELS],
            "dist_x_jobs", "dist_x_low", "dist_x_high", "low_25plus"]
    out = od.groupby(["w_tract", "h_tract"], as_index=False)[sums].sum()
    out = out.rename(columns={"S000": "jobs", "SE01": "wage_low", "SE02": "wage_mid", "SE03": "wage_high",
                              "SI01": "goods_prod", "SI02": "trade_transp_util", "SI03": "other_services",
                              "low_25plus": "wage_low_25plus"})
    out.insert(0, "year", year)
    qa.update(rows_clean=len(od), tract_pairs=len(out), total_jobs_clean=int(out["jobs"].sum()))
    return out, qa


# ----------------------------------------------------------------------------- report
def write_quality_report(qa_rows: list[dict]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(qa_rows).fillna("")
    checks = [c for c in df.columns if c not in ("kind", "year")]
    lines = ["# Data quality report", "",
             "Generated by `src/clean.py`. Each LODES file is checked before it is aggregated to tracts.", "",
             "| check | what it verifies |", "|---|---|",
             "| dup_geocodes / dup_pairs | no duplicated block (or block-pair) keys |",
             "| bad_geocode_len | every GEOID is 15 characters |",
             "| negative_values / null_values | no impossible or missing counts |",
             "| sector/wage/age_sum_mismatch | sector, wage and age breakdowns each add up to the total job count |",
             "| blocks_not_in_xwalk_tract | every block maps to a known tract |",
             "| pairs_missing_coords | every OD block has coordinates for distance calculation |", "",
             "## Results", "", df[["kind", "year", *checks]].to_markdown(index=False)]
    (REPORT_DIR / "data_quality.md").write_text("\n".join(lines) + "\n")
    hard = ["dup_geocodes", "bad_geocode_len", "negative_values", "null_values", "sector_sum_mismatch",
            "wage_sum_mismatch", "age_sum_mismatch", "blocks_not_in_xwalk_tract", "dup_pairs", "pairs_missing_coords"]
    bad = df[[c for c in hard if c in df.columns]].replace("", 0).astype(int).sum()
    print("QA totals of failed checks:", {k: int(v) for k, v in bad.items() if v})


def run() -> None:
    INTERIM.mkdir(parents=True, exist_ok=True)
    dim, blocks = build_dim_tract()
    dim.to_parquet(INTERIM / "dim_tract.parquet", index=False)
    valid = set(dim["tract"])
    print(f"dim_tract: {len(dim):,} tracts ({dim['in_houston_msa'].sum()} in Houston MSA)")

    qa_rows = []
    for kind, years in (("wac", WAC_YEARS), ("rac", RAC_YEARS)):
        frames = []
        for y in years:
            f, qa = clean_lodes_area(kind, y, valid)
            frames.append(f), qa_rows.append(qa)
            print(f"  {kind} {y}: {qa['rows_raw']:,} blocks -> {qa['tracts']:,} tracts, {qa['total_jobs_clean']:,} jobs")
        pd.concat(frames, ignore_index=True).to_parquet(INTERIM / f"{kind}_tract.parquet", index=False)

    frames = []
    for y in OD_YEARS:
        f, qa = clean_od(y, blocks, valid)
        frames.append(f), qa_rows.append(qa)
        print(f"  od {y}: {qa['rows_raw']:,} raw block pairs -> {qa['tract_pairs']:,} MSA-touching tract pairs")
    pd.concat(frames, ignore_index=True).to_parquet(INTERIM / "od_tract.parquet", index=False)

    write_quality_report(qa_rows)
    (INTERIM / "qa.json").write_text(json.dumps(qa_rows, indent=1))


if __name__ == "__main__":
    run()
