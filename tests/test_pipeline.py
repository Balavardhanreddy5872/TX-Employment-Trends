import sqlite3

import pandas as pd
import pytest

from src.clean import clean_county_name, haversine_miles, tract_of
from src.config import DB_PATH, HOUSTON_MSA_COUNTIES, NAICS_SECTORS
from src.run_sql import parse_blocks


def test_haversine_houston_to_dallas():
    d = float(haversine_miles(29.7604, -95.3698, 32.7767, -96.7970))
    assert 220 < d < 230  # ~224 straight-line miles


def test_haversine_zero_and_symmetry():
    assert float(haversine_miles(29.7, -95.3, 29.7, -95.3)) == pytest.approx(0)
    a, b = haversine_miles(29.7, -95.3, 30.1, -95.5), haversine_miles(30.1, -95.5, 29.7, -95.3)
    assert float(a) == pytest.approx(float(b))


def test_tract_of_and_county_name():
    assert tract_of(pd.Series(["482013101001000"])).iloc[0] == "48201310100"
    assert clean_county_name("Harris County, TX") == "Harris"


def test_config_shape():
    assert len(HOUSTON_MSA_COUNTIES) == 9 and "48201" in HOUSTON_MSA_COUNTIES
    assert len(NAICS_SECTORS) == 20


def test_parse_blocks():
    blocks = parse_blocks("-- name: a\nSELECT 1;\n\n-- name: setup_b\nCREATE TABLE x(i);")
    assert [b[0] for b in blocks] == ["a", "setup_b"]


needs_db = pytest.mark.skipif(not DB_PATH.exists(), reason="run `make db` first")


@pytest.fixture(scope="module")
def con():
    c = sqlite3.connect(DB_PATH)
    yield c
    c.close()


@needs_db
def test_sector_columns_sum_to_total(con):
    bad = con.execute("""SELECT COUNT(*) FROM fact_wac WHERE cns01+cns02+cns03+cns04+cns05+cns06+cns07+cns08+cns09+cns10
        +cns11+cns12+cns13+cns14+cns15+cns16+cns17+cns18+cns19+cns20 <> jobs""").fetchone()[0]
    assert bad == 0


@needs_db
def test_long_sector_table_matches_wide(con):
    wide = con.execute("SELECT SUM(jobs) FROM fact_wac WHERE year = 2023").fetchone()[0]
    long = con.execute("SELECT SUM(jobs) FROM fact_wac_sector WHERE year = 2023").fetchone()[0]
    assert wide == long


@needs_db
def test_no_duplicate_tract_years(con):
    for t in ("fact_wac", "fact_rac"):
        assert con.execute(f"SELECT COUNT(*) - COUNT(DISTINCT tract || year) FROM {t}").fetchone()[0] == 0


@needs_db
def test_all_fact_tracts_in_dimension(con):
    orphans = con.execute("SELECT COUNT(*) FROM fact_wac w LEFT JOIN dim_tract d ON d.tract = w.tract WHERE d.tract IS NULL").fetchone()[0]
    assert orphans == 0


@needs_db
def test_od_jobs_are_bounded_by_wac(con):
    # OD-main workers employed in the MSA cannot exceed WAC jobs in the MSA
    od = con.execute("SELECT SUM(o.jobs) FROM fact_od o JOIN dim_tract d ON d.tract = o.w_tract WHERE o.year = 2023 AND d.in_houston_msa = 1").fetchone()[0]
    wac = con.execute("SELECT SUM(w.jobs) FROM fact_wac w JOIN dim_tract d ON d.tract = w.tract WHERE w.year = 2023 AND d.in_houston_msa = 1").fetchone()[0]
    assert 0.85 * wac < od <= wac


@needs_db
def test_houston_msa_has_nine_counties(con):
    assert con.execute("SELECT COUNT(DISTINCT county_fips) FROM dim_tract WHERE in_houston_msa = 1").fetchone()[0] == 9
