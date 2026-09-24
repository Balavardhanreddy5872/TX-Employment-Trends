# Interview guide - Houston Employment & Commute Analysis

## Resume bullets (pick 3-4)

* Built an **end-to-end analytics pipeline** (Python → SQLite → SQL → geospatial visualisation) on 450 MB of Census LODES data (12M+ Texas jobs, 2010-23, 31 files); automated a data-quality audit with **0 failed checks** and a one-command rebuild (`make all`).
* Wrote **22 analytical SQL queries** (CTEs, window functions, pivots, spatial self-joins with UDFs) to benchmark Houston against Dallas-Fort Worth, Austin and San Antonio; showed Houston's 2019-23 job growth trailed peers (**+6.9% vs +12.3% / +18.0%**) after the oil bust despite stable industry diversification (HHI 760 vs 749).
* Quantified **suburban decentralisation** (jobs 20-35 mi from Downtown: 15.4% → 22.1%; Harris County +4.5% vs Montgomery +20.5% since 2019) and longer commutes (25+ mi share 22.5% → 26.9%).
* Designed a **three-signal spatial-mismatch screen** across 1,600 tracts identifying 93 priority tracts / ~50k low-wage workers with poor job access; delivered a policy brief with targeted commuter-access and suburban job-anchoring recommendations.
* Cut a key query from **294 s to 0.5 s** by denormalising county keys and indexing; produced 11 colour-blind-safe charts/maps and an interactive tract-level map.

## 30-second pitch
"I analysed where jobs and commutes have shifted in the Houston region using 14 years of Census payroll-linked data. Houston lagged Texas' other big metros after the oil bust, growth moved to the suburbs, and commutes got longer. I built the pipeline in Python and SQL, then developed a screening model that pinpoints about 93 neighbourhoods where roughly 50,000 low-wage workers live far from low-wage jobs - that's where I recommend the region pilot commuter access and suburban job anchoring."

## 2-minute walk-through (STAR)
* **Situation** - A regional workforce board wants to know where to spend limited access dollars; the raw data (LODES) is huge, block-level and noisy.
* **Task** - Turn it into a defensible, reproducible answer: where are jobs, who commutes where, who is left out?
* **Action** - (1) Downloaded/cleaned 31 files with automated QA and aggregated blocks → tracts. (2) Modelled a star schema in SQLite. (3) Answered six business questions in SQL. (4) Mapped results and built a tract screen from three independent signals (RAC residents, WAC/RAC 10-mile accessibility, OD commute distance). (5) Wrote a brief with recommendations and explicit caveats.
* **Result** - Houston lagging peers, suburban shift, 93 priority tracts covering ~9.8% of the region's low-wage workers, and a validation plan before spending.

## Numbers to have memorised
Houston MSA jobs 2.53M → 3.13M → 3.35M (2010/19/23) · 2019-23 growth Houston 6.9%, DFW 12.3%, Austin 18.0% · mining jobs 116k (2014) → 75k (2023), LQ 1.45 · Harris 76% of MSA jobs, +4.5% vs Montgomery +20.5% · Harris jobs per resident worker 1.22 (Fort Bend 0.60) · 25+ mi commutes 22.5% → 26.9% · 93 priority tracts / 49.7k workers (9.8% of 505k) · Liberty low-wage jobs per worker within 10 mi 0.48 vs Harris 1.15.

## Likely questions and strong answers

**Why did you aggregate to tracts?** Blocks carry LEHD's synthetic noise (differential-privacy-style protection) and are too granular; 430k residence blocks became 6.9k tracts (>98% fewer rows) while total jobs are preserved exactly (asserted). Tract is also the level at which I can join Census boundaries and, later, ACS.

**How do you know the data is right?** Automated checks on every file: unique 15-char GEOIDs, no nulls/negatives, sector/wage/age breakdowns each sum to total jobs, every block maps to a tract. All 31 pass; I also sanity-checked the story (Texas dips in 2020, Houston's share of Texas jobs peaks in 2015 and declines after).

**What is a location quotient / HHI, and why use them?** LQ = local sector share ÷ state sector share; shows specialisation (mining 1.45). HHI = Σ share² measures concentration; I used it to show energy's decline did not make Houston more concentrated.

**Walk me through the spatial-mismatch screen.** Three signals per tract: (1) top quartile of low-wage resident workers (RAC), (2) bottom quartile of low-wage jobs per low-wage worker within 10 miles (cumulative-opportunity accessibility, controls for density), (3) top quartile of low-wage workers commuting 25+ miles (OD). Score = number of signals; 3 = priority. Triangulating three independent data sources makes it robust to any one being noisy.

**How did you compute "within 10 miles" in SQL?** A self-join of the tract dimension with a cheap bounding-box predicate on lat/lon, then an exact haversine (Python UDF registered on the SQLite connection) - ~1,600² candidate pairs in ~3 s, no PostGIS needed. In production I'd use PostGIS/DuckDB-spatial with a spatial index.

**What are the biggest limitations?** (1) LODES wage bands are *nominal*, so I only compare places within a year - never a real-wage trend. (2) Remote workers are placed at the employer address, inflating long-distance commutes after 2020 - I use distance bands and the 25+ mile share, and I state that direction, not magnitude, is the finding. (3) OD only covers in-state UI-covered jobs. (4) Straight-line distance. (5) The screen is descriptive, not causal.

**Did you find anything that made you change the analysis?** Yes - I first computed "low-wage jobs within 10 miles" change 2019→23 and it fell ~15%. I realised that was an artefact of nominal wage bands (inflation pushes jobs up a band) and dropped that query. I also replaced mean commute distance (skewed by long tail/remote-work artefacts) with the 25+ mile share, and replaced raw job counts with a job-to-worker ratio so dense areas weren't flagged simply for being dense.

**Performance?** One query took 294 s (double join through the tract dimension over 3.9M OD rows). Denormalising county FIPS onto the OD table (tract GEOID prefix) plus a composite index brought it to 0.5 s.

**How would you scale it?** SQLite handles this comfortably (740 MB). For all states I'd use DuckDB/Parquet or a warehouse (partition by state-year), and move the spatial join to PostGIS/DuckDB spatial.

**What would you do next?** Add ACS vehicle access and poverty, METRO GTFS transit reach, network (not straight-line) travel times, a shift-share decomposition of the growth gap vs DFW, and a forecast/scenario for the 20-35 mile ring.

**How would you present to non-technical stakeholders?** The one-page policy brief: five bottom-line findings, three recommendations with a success metric, and a caveats box; interactive map for exploring their own neighbourhoods.

**Causality?** I don't claim it. The screen prioritises where to look; a pilot with a comparison group is how you'd measure impact.

## Live-coding style prompts you can answer from this repo
* *Year-over-year growth by metro* - `sql/01_growth_benchmarks.sql` (`LAG`, `FIRST_VALUE`).
* *Pivot years to columns* - conditional aggregation in `metro_growth_summary`.
* *Nearest center per tract* - `ROW_NUMBER() OVER (PARTITION BY tract ORDER BY dist)` in `00_setup.sql`.
* *Quartiles* - `NTILE(4)` in `05_spatial_mismatch.sql`.
* *Share of total* - `SUM(x) OVER ()` in `msa_county_summary`.
