# Methodology

## Data
| File | Content | Years used | Grain after cleaning |
|---|---|---|---|
| LODES8 WAC `tx_wac_S000_JT00` | jobs by **workplace** block: total, 3 age bands, 3 earnings bands, 20 NAICS supersectors | 2010-2023 | tract x year |
| LODES8 RAC `tx_rac_S000_JT00` | workers by **residence** block, same breakdowns | 2010-2023 | tract x year |
| LODES8 OD `tx_od_main_JT00` | home block -> work block job counts (both in TX) | 2015, 2019, 2023 | tract-pair x year (flows touching the Houston MSA) |
| LODES8 crosswalk `tx_xwalk` | block -> tract/county/CBSA names, block centroids | 2020 blocks | tract dimension |
| Census cartographic boundaries 2023 (tracts, counties) | polygons | - | mapping, tract centroids, land area |

LODES8 uses 2020 census blocks for **all** years, so tract geography is consistent over time (no crosswalking).
Job type JT00 = all jobs; segment S000 = all workers.

**Study area:** Houston-The Woodlands-Sugar Land MSA (CBSA 26420): Austin, Brazoria, Chambers, Fort Bend, Galveston, Harris, Liberty, Montgomery, Waller counties. Benchmarks: Dallas-Fort Worth-Arlington (19100), Austin-Round Rock (12420), San Antonio-New Braunfels (41700).

## Pipeline
```
download_data.py -> clean.py -> build_db.py -> run_sql.py (sql/*.sql) -> visualize.py -> reports / notebooks
   raw .csv.gz      parquet       SQLite         outputs/tables/*.csv       PNG + HTML
```
1. **Clean (Python)** - typed reads (GEOIDs as strings to keep leading zeros), explicit QA (duplicates, GEOID length, negatives, nulls, sector/wage/age sums equal the job total, orphan blocks), block -> tract aggregation, OD distances via haversine on block centroids, aggregation to tract pairs with distance-band counts. All QA results are written to `outputs/reports/data_quality.md` (0 failures across 31 files).
2. **Model (SQLite star schema)** - `dim_tract`, `dim_sector`, `dim_metro`, `dim_center`; `fact_wac`, `fact_rac`, `fact_wac_sector` (unpivoted), `fact_od` (with denormalised county keys). Indexes on the join/filter keys.
3. **Analyse (SQL)** - 6 numbered files, 28 named queries; CTEs, window functions (`LAG`, `FIRST_VALUE`, `NTILE`, `ROW_NUMBER`, `SUM() OVER`), conditional aggregation pivots, self-joins, spatial joins with bounding-box prefilters, python UDFs for `haversine_mi` / `power`. Each query is exported to `outputs/tables/`.
4. **Visualise (Python)** - matplotlib/geopandas static charts and choropleths; folium interactive map.

## Key definitions
* **Location quotient** = (sector share of Houston MSA jobs) / (sector share of Texas jobs). >1 = specialised.
* **HHI** = sum of squared sector shares (in %); lower = more diversified.
* **Employment centers** = tracts whose centroid lies within 3 miles of a hand-placed district anchor (Downtown, TMC, Uptown/Galleria, Westchase, Energy Corridor, Greenspoint/IAH, The Woodlands, Sugar Land, Clear Lake/NASA, Ship Channel/Pasadena, Baytown). Anchors are approximate; nearest center wins.
* **Jobs per resident worker** = WAC jobs / RAC workers for the same geography (>1 = net importer of workers).
* **Job-worker ratio within 10 mi** = low-wage jobs in tracts whose centroids are within 10 miles / low-wage workers living in those tracts (a cumulative-opportunity accessibility measure that controls for density).
* **Access-gap screen** - tract scores 1 point for each of: (a) top quartile of low-wage resident workers, (b) bottom quartile of the 10-mile low-wage job-worker ratio, (c) top quartile of low-wage workers with 25+ mile commutes. Score 3 = "priority". Tracts with < 100 resident workers are not screened.

## Limitations & how they are handled
| Issue | Handling |
|---|---|
| Nominal earnings bands drift with inflation | wage analysis is cross-sectional only; documented in SQL comments and report |
| Remote workers / multi-site firms placed at employer address | distance reported in bands, trend flagged as an upper bound, 25+ mi share used instead of the mean |
| Differential-privacy noise in blocks | aggregate to tracts; QA identities still hold |
| OD covers only in-state, UI-covered private + state/local government jobs | stated in captions; flows to other states excluded |
| Straight-line vs network distance | no routing engine used; distances are relative measures |
| Screen signals are spatially correlated | used for prioritisation only; recommend validating with ACS vehicle access and GTFS |
| LODES 2023 is the latest release at time of writing | numbers will shift slightly if LEHD revises |

## Reproducing
```bash
make setup && make all        # ~10 min; downloads ~450 MB, builds a ~750 MB local SQLite (git-ignored)
make notebooks                # re-executes the three notebooks
```
