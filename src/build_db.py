"""Load cleaned parquet files into a SQLite star-schema (db/lodes.db) for the SQL analysis stage.

Tables
  dim_tract          tract, county, CBSA, centroid lat/lon, land area, Houston-MSA flag
  dim_sector         NAICS supersector code -> name
  fact_wac           jobs by WORKPLACE tract x year (+ wage/age bands and 20 sector columns)
  fact_rac           workers by RESIDENCE tract x year
  fact_wac_sector    long (unpivoted) version of the WAC sector columns
  fact_od            home->work tract-pair flows touching the Houston MSA (2015/2019/2023)
Usage: python -m src.build_db
"""
import sqlite3

import pandas as pd

from src.config import DB_PATH, INTERIM, NAICS_SECTORS, PROCESSED

INDEXES = [
    "CREATE INDEX ix_wac_ty ON fact_wac(tract, year)",
    "CREATE INDEX ix_wac_y ON fact_wac(year)",
    "CREATE INDEX ix_rac_ty ON fact_rac(tract, year)",
    "CREATE INDEX ix_rac_y ON fact_rac(year)",
    "CREATE INDEX ix_ws_ys ON fact_wac_sector(year, sector_code)",
    "CREATE INDEX ix_ws_t ON fact_wac_sector(tract)",
    "CREATE INDEX ix_od_wy ON fact_od(year, w_tract)",
    "CREATE INDEX ix_od_hy ON fact_od(year, h_tract)",
    "CREATE INDEX ix_od_wc ON fact_od(year, w_county)",
    "CREATE INDEX ix_od_hc ON fact_od(year, h_county)",
    "CREATE INDEX ix_dim_county ON dim_tract(county_fips)",
    "CREATE INDEX ix_dim_cbsa ON dim_tract(cbsa)",
]


def run() -> None:
    DB_PATH.parent.mkdir(exist_ok=True)
    DB_PATH.unlink(missing_ok=True)
    con = sqlite3.connect(DB_PATH)

    dim = pd.read_parquet(INTERIM / "dim_tract.parquet")
    wac = pd.read_parquet(INTERIM / "wac_tract.parquet")
    rac = pd.read_parquet(INTERIM / "rac_tract.parquet")
    od = pd.read_parquet(INTERIM / "od_tract.parquet")
    od["w_county"], od["h_county"] = od["w_tract"].str[:5], od["h_tract"].str[:5]  # tract GEOID starts with county FIPS

    dim.to_sql("dim_tract", con, index=False)
    pd.DataFrame({"sector_code": [c.lower() for c in NAICS_SECTORS], "sector_name": list(NAICS_SECTORS.values())}
                 ).to_sql("dim_sector", con, index=False)
    wac.to_sql("fact_wac", con, index=False)
    rac.to_sql("fact_rac", con, index=False)
    od.to_sql("fact_od", con, index=False)

    sector_cols = [c.lower() for c in NAICS_SECTORS]
    long = wac[["year", "tract", *sector_cols]].melt(id_vars=["year", "tract"], var_name="sector_code", value_name="jobs")
    long[long["jobs"] > 0].to_sql("fact_wac_sector", con, index=False)

    # Small, shareable panel of the Houston MSA (workplace jobs) so the repo is useful without re-downloading raw data.
    panel = wac.merge(dim[["tract", "county_fips", "county_name", "in_houston_msa"]], on="tract")
    panel = panel[panel["in_houston_msa"] == 1].drop(columns="in_houston_msa")
    PROCESSED.mkdir(parents=True, exist_ok=True)
    panel.to_csv(PROCESSED / "houston_msa_wac_tract_panel.csv.gz", index=False)

    for stmt in INDEXES:
        con.execute(stmt)
    con.commit()
    for t in ("dim_tract", "dim_sector", "fact_wac", "fact_rac", "fact_wac_sector", "fact_od"):
        n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t:<16}{n:>10,} rows")
    con.close()
    print(f"database written to {DB_PATH} ({DB_PATH.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    run()
