"""Generate and execute the three walkthrough notebooks (outputs embedded so GitHub renders them).

Usage: python -m src.make_notebooks
"""
import nbformat as nbf
from nbconvert.preprocessors import ExecutePreprocessor

from src.config import ROOT

NB_DIR = ROOT / "notebooks"
md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell

SETUP = """import sys, sqlite3
from pathlib import Path
ROOT = Path.cwd() if (Path.cwd() / 'src').exists() else Path.cwd().parent
sys.path.insert(0, str(ROOT))
import pandas as pd, numpy as np
pd.set_option('display.width', 200); pd.set_option('display.max_columns', 30); pd.set_option('display.float_format', '{:,.2f}'.format)
from src.config import *
"""


def nb01():
    return [
        md("# 01 - Data acquisition, cleaning and quality checks\n\n"
           "**Goal:** turn ~450 MB of raw Census LODES8 block-level files into clean, validated tract-level tables.\n\n"
           "**Why tracts?** Raw files are keyed by 15-digit census *blocks* (~170k workplace blocks / 430k residence blocks in Texas). "
           "LEHD adds synthetic noise at block level to protect confidentiality, and blocks are too granular to interpret. "
           "Aggregating to 11-digit *tracts* (6,896 in Texas) removes ~96% of rows and damps the noise."),
        code(SETUP),
        md("## 1. What a raw WAC file looks like"),
        code("raw = pd.read_csv(RAW / 'wac' / 'tx_wac_S000_JT00_2023.csv.gz', dtype={'w_geocode': str})\n"
             "print(raw.shape)\nraw.iloc[:3, :12]"),
        md("`w_geocode` must be read as a **string** - blocks start with `48` (Texas) and identifiers lose meaning as integers. "
           "`C000` = total jobs; `CNS01-20` = NAICS supersectors; `CE01-03` = monthly-earnings bands; `CA01-03` = age bands."),
        md("## 2. Data-quality checks (run on every file)\n\n"
           "`src/clean.py` asserts that identifiers are unique and well-formed, counts are non-negative and non-null, and that the sector, "
           "wage and age breakdowns each add back to the job total. Results for all 31 raw files:"),
        code("qa = pd.read_json(INTERIM / 'qa.json')\n"
             "checks = [c for c in qa.columns if c.endswith('mismatch') or c in ('dup_geocodes','dup_pairs','bad_geocode_len','negative_values','null_values','blocks_not_in_xwalk_tract','pairs_missing_coords')]\n"
             "print('files checked:', len(qa), '| failed checks:', int(qa[checks].fillna(0).sum().sum()))\n"
             "qa[['kind','year','rows_raw','total_jobs_raw','total_jobs_clean']].query('year in [2010, 2019, 2023]')"),
        md("Zero failures. As a plausibility check, the 2019 Texas WAC total (12.4M) is in the range expected for jobs covered by "
           "unemployment insurance (roughly 12-13M)."),
        md("## 3. Cleaning steps, demonstrated on one year"),
        code("from src.clean import clean_lodes_area, build_dim_tract\n"
             "dim, blocks = build_dim_tract()\n"
             "wac23, qa23 = clean_lodes_area('wac', 2023, set(dim['tract']))\n"
             "print(f\"{qa23['rows_raw']:,} blocks -> {len(wac23):,} tracts | jobs preserved: {qa23['total_jobs_raw'] == wac23['jobs'].sum()}\")\n"
             "wac23.head()"),
        md("Total jobs are **exactly preserved** through aggregation (the check above prints `True`). "
           "Column names are standardised (`CE01` -> `wage_low`, `CNS16` -> `cns16`)."),
        md("## 4. The tract dimension\n\n"
           "Built from the LEHD geography crosswalk (names, county, CBSA) joined to TIGER polygons for true tract centroids and land area. "
           "The Houston MSA is flagged from its nine county FIPS codes."),
        code("dim[dim.in_houston_msa == 1].groupby('county_name').agg(tracts=('tract','count'), land_sqmi=('land_sqmi','sum')).sort_values('tracts', ascending=False)"),
        md("## 5. Sanity check: does the cleaned data tell a coherent story?"),
        code("wac = pd.read_parquet(INTERIM / 'wac_tract.parquet').merge(dim[['tract','cbsa']], on='tract')\n"
             "tx = wac.groupby('year')['jobs'].sum()\n"
             "hou = wac[wac.cbsa == '26420'].groupby('year')['jobs'].sum()\n"
             "pd.DataFrame({'texas': tx, 'houston_msa': hou, 'houston_share_%': 100 * hou / tx})"),
        md("Texas jobs dip in 2020 (COVID). Houston's share of the state rises from 24.9% to a 25.8% peak in 2015, then slides to 24.7% by 2023 - the oil-bust-then-lag pattern the SQL analysis quantifies. "
           "Next: model the tables in SQLite (`src/build_db.py`) and analyse them in SQL."),
    ]


def nb02():
    helper = ("from src.run_sql import connect, parse_blocks\n"
              "con = connect()\n"
              "Q = {}\n"
              "for f in sorted(SQL_DIR.glob('*.sql')):\n"
              "    for name, sql in parse_blocks(f.read_text()):\n"
              "        Q[name] = sql\n"
              "def run(name, show_sql=True):\n"
              "    if show_sql: print(Q[name], '\\n')\n"
              "    return pd.read_sql_query(Q[name], con)\n")
    return [
        md("# 02 - SQL analysis: Houston's economy in six questions\n\n"
           "All queries live in `sql/*.sql` (SQLite dialect) and are re-run here against `db/lodes.db`. "
           "Each answers a question a workforce board or planning agency would ask.\n\n"
           "| # | Question | SQL techniques |\n|---|---|---|\n"
           "| 1 | Is Houston growing as fast as Texas' other metros? | CTE, `LAG`, `FIRST_VALUE`, conditional-aggregation pivot, CAGR |\n"
           "| 2 | What is the industry mix and how is it changing? | location quotient, `SUM() OVER`, HHI |\n"
           "| 3 | Which counties are job hubs vs bedroom communities? | multi-CTE joins of WAC and RAC |\n"
           "| 4 | Where are the job centers, and are jobs decentralising? | window `ROW_NUMBER` nearest-center assignment, CASE bands |\n"
           "| 5 | How are commutes changing? | large OD fact table, weighted averages, denormalised keys |\n"
           "| 6 | Where are low-wage workers stranded from jobs? | spatial self-join (bounding box + haversine UDF), `NTILE` quartiles |"),
        code(SETUP + helper),
        md("## Q1. Growth vs. peer metros"),
        code("run('metro_growth_summary')"),
        md("**Read:** Houston out-grew Texas before 2019 (2.40% vs 2.28%/yr) but lagged badly after (1.67% vs 2.16%). "
           "Dallas-Fort Worth (+12.3%) and Austin (+18.0%) pulled away in 2019-23 while Houston added +6.9%."),
        code("run('houston_shock_years', show_sql=False)"),
        md("**Read:** the oil bust is visible - total job growth collapses to ~0% in 2016-17 as mining jobs fall 13-15% a year (Harvey hit in 2017 too). "
           "Mining employment then fell another 21% in 2021. Energy jobs move ~3x as violently as the whole economy."),
        md("## Q2. Industry mix"),
        code("run('sector_change_houston_msa')"),
        md("**Read:** since 2019 Houston added most in Professional/Scientific/Technical (+42k), Health Care (+37k) and Transportation & Warehousing (+27k); "
           "Mining lost 17k. Mining is still the most over-represented sector (LQ 1.45); Finance (0.74) and Information (0.62) are under-represented."),
        code("run('sector_diversification_hhi', show_sql=False).query('year in [2010, 2015, 2019, 2023]').pivot(index='metro_name', columns='year', values='hhi')"),
        md("**Read:** the industry-concentration index for Houston (755 -> 760) is flat and equal to Dallas-Fort Worth (749) - "
           "so the energy decline has not left the region *more* concentrated. Austin and San Antonio are more concentrated (public sector and education)."),
        md("## Q3. Hubs vs. bedroom communities"),
        code("run('msa_county_summary', show_sql=False)"),
        md("**Read:** Harris County (76% of MSA jobs) has 1.22 jobs per resident worker - a net importer. "
           "Fort Bend (0.60) and Montgomery (0.75) are net exporters, and they are also growing 3-4x faster than Harris (16% and 20% vs 4.5% since 2019)."),
        md("## Q4. Employment centers and decentralisation"),
        code("run('center_summary', show_sql=False)"),
        code("r = run('decentralization_by_ring', show_sql=False)\nr[r.year.isin([2010, 2019, 2023])].pivot(index='ring', columns='year', values='share_pct')"),
        md("**Read:** the 0-10 mile share of MSA jobs fell from 39.8% to 33.0% while the 20-35 mile ring rose from 15.4% to 22.1%. "
           "Downtown (+7% since 2010) and Uptown/Galleria (+1%) are nearly flat; The Woodlands (+71%), Sugar Land (+56%), Energy Corridor (+27%) and the Texas Medical Center (+26%) are growing. "
           "Baytown's industrial base shrank 15%."),
        md("## Q5. Commutes"),
        code("run('commute_distance_trend')"),
        code("run('harris_inbound_outbound', show_sql=False)"),
        md("**Read:** the share of Houston-area workers with 25+ mile straight-line distances rose from 22.5% (2015) to 26.9% (2023). "
           "37% of Harris jobs are now held by non-Harris residents (32.5% in 2015). "
           "*Caveat:* LODES puts remote workers at their employer's address, so some of the rise is not physical commuting; the direction, not the magnitude, is the finding."),
        code("run('home_county_commute_profile', show_sql=False).query('year == 2023')"),
        md("## Q6. Spatial mismatch: who is far from low-wage jobs?\n\n"
           "Three signals per tract (all 2023): (1) many low-wage resident workers, (2) few low-wage jobs per low-wage worker within 10 miles, "
           "(3) a high share of low-wage residents commuting 25+ miles. A tract scores 1 point per signal."),
        code("print(Q['setup_tract_pairs']); print(Q['setup_tract_access'])"),
        md("The `tract_pairs` table is a spatial self-join: every tract pair within 10 miles, found with a bounding-box prefilter (cheap, in C) then an exact haversine "
           "(a Python UDF registered on the SQLite connection) - ~1,600 x 1,600 candidate pairs in about 3 seconds, no GIS extension needed."),
        code("run('priority_summary_by_county', show_sql=False)"),
        code("run('job_worker_ratio_by_county_2023', show_sql=False)"),
        md("**Read:** 93 tracts hit all three signals and hold ~49.7k low-wage workers (9.8% of the MSA's 505k). "
           "Brazoria (0.70) and Liberty (0.48) have far fewer low-wage jobs per low-wage worker within 10 miles than Harris (1.15); "
           "70% of Liberty's low-wage residents commute 25+ miles versus 22% in Harris."),
        code("run('priority_tracts_top25', show_sql=False).head(10)"),
    ]


def nb03():
    return [
        md("# 03 - Geo-visualisation and recommendation\n\n"
           "Maps and charts are produced by `src/visualize.py` from the SQL outputs. This notebook walks through them and ends with the recommendation."),
        code(SETUP + "from IPython.display import Image, display, HTML\n"
             "show = lambda n: display(Image(filename=str(FIG_DIR / n), width=760))"),
        md("## 1. Houston vs. the other big Texas metros"),
        code("show('01_metro_job_growth_index.png')"),
        md("Houston tracked or beat Texas through the mid-2010s, stalled with the 2015-17 oil bust and Harvey, and has grown more slowly than DFW, Austin and San Antonio since."),
        code("show('02_houston_energy_vs_total_yoy.png')"),
        md("## 2. What is driving growth"),
        code("show('03_houston_sector_job_change.png')"),
        md("## 3. Growth has moved to the suburbs"),
        code("show('04_county_growth_and_balance.png')"),
        code("show('05_employment_center_growth.png')"),
        code("show('10_map_job_change_2019_23.png')"),
        md("## 4. Where jobs are concentrated, and where people live relative to them"),
        code("show('08_map_job_density.png')"),
        code("show('09_map_jobs_housing_balance.png')"),
        md("Blue = job hubs (Downtown, Uptown/Galleria, Texas Medical Center, Westchase, Energy Corridor, Greenspoint, Ship Channel); red = bedroom tracts. "
           "The red ring around the core is where commutes start."),
        md("## 5. Commutes are becoming more regional"),
        code("show('06_commute_distance_and_harris_flows.png')"),
        md("## 6. Access-gap screen and recommendation"),
        code("show('11_map_access_gap_priority_tracts.png')"),
        code("show('07_priority_tracts_by_county.png')"),
        code("t = pd.read_csv(TABLE_DIR / 'tract_metrics_2023.csv', dtype={'tract': str})\n"
             "p = t[t.priority_score == 3]\n"
             "print(f\"{len(p)} priority tracts hold {p.low_wage_residents.sum():,.0f} of {t.low_wage_residents.sum():,.0f} low-wage resident workers ({100*p.low_wage_residents.sum()/t.low_wage_residents.sum():.1f}%)\")\n"
             "p.groupby('county_name').agg(tracts=('tract','count'), low_wage_residents=('low_wage_residents','sum'),\n"
             "    lw_jobs_per_worker_10mi=('lw_jobs_per_lw_worker_10mi','median'), pct_25plus_mi=('share_low_wage_25plus', lambda s: 100*s.median())).sort_values('low_wage_residents', ascending=False)"),
        md("### Recommendation\n\n"
           "1. **Pilot commuter access (vanpool / microtransit) on corridors linking the priority-tract clusters to their nearest job centers** - Montgomery to The Woodlands/Greenspoint, "
           "Liberty and Chambers to Baytown/Ship Channel, Brazoria to Clear Lake/Texas Medical Center, Fort Bend and NW Harris to Sugar Land/Energy Corridor.\n"
           "2. **Bring jobs to workers** in Brazoria (0.70) and Liberty (0.48), where low-wage jobs per low-wage worker within 10 miles is lowest, by anchoring growth sectors (health care, logistics) there.\n"
           "3. **Keep diversifying away from energy** and monitor the mining location quotient and the 20-35 mile job ring as leading indicators.\n"
           "4. **Validate with vehicle-access (ACS) and transit (GTFS) data** before committing budget.\n\n"
           "Full brief with caveats: `outputs/reports/policy_brief.md`. Interactive map: `outputs/maps/houston_jobs_interactive.html`."),
    ]


def run() -> None:
    NB_DIR.mkdir(exist_ok=True)
    specs = [("01_data_cleaning_and_qa.ipynb", nb01()), ("02_sql_analysis.ipynb", nb02()),
             ("03_geo_visualization_and_recommendation.ipynb", nb03())]
    for name, cells in specs:
        nb = nbf.v4.new_notebook(cells=cells)
        nb.metadata["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
        print("executing", name)
        ExecutePreprocessor(timeout=900, kernel_name="python3").preprocess(nb, {"metadata": {"path": str(ROOT)}})
        nbf.write(nb, NB_DIR / name)


if __name__ == "__main__":
    run()
