-- Q2/Q3: What does the Houston economy look like, by county and by industry, and how did it change?

-- name: msa_county_summary
WITH w AS (
  SELECT d.county_name, d.county_fips,
         SUM(CASE WHEN f.year = 2010 THEN f.jobs END) AS jobs_2010,
         SUM(CASE WHEN f.year = 2019 THEN f.jobs END) AS jobs_2019,
         SUM(CASE WHEN f.year = 2023 THEN f.jobs END) AS jobs_2023,
         SUM(CASE WHEN f.year = 2023 THEN f.wage_high END) AS high_wage_2023,
         SUM(CASE WHEN f.year = 2023 THEN f.wage_low END)  AS low_wage_2023
  FROM fact_wac f JOIN dim_tract d ON d.tract = f.tract WHERE d.in_houston_msa = 1 GROUP BY d.county_name, d.county_fips),
r AS (
  SELECT d.county_fips, SUM(f.jobs) AS resident_workers_2023
  FROM fact_rac f JOIN dim_tract d ON d.tract = f.tract WHERE d.in_houston_msa = 1 AND f.year = 2023 GROUP BY d.county_fips)
SELECT w.county_name, jobs_2010, jobs_2019, jobs_2023,
       ROUND(100.0 * (jobs_2023 - jobs_2010) / jobs_2010, 1)              AS growth_2010_23_pct,
       ROUND(100.0 * (jobs_2023 - jobs_2019) / jobs_2019, 1)              AS growth_2019_23_pct,
       ROUND(100.0 * jobs_2023 / SUM(jobs_2023) OVER (), 1)               AS share_of_msa_jobs_pct,
       resident_workers_2023,
       ROUND(jobs_2023 * 1.0 / resident_workers_2023, 2)                   AS jobs_per_resident_worker,
       ROUND(100.0 * high_wage_2023 / jobs_2023, 1)                        AS high_wage_share_pct,
       ROUND(100.0 * low_wage_2023 / jobs_2023, 1)                         AS low_wage_share_pct
FROM w JOIN r ON r.county_fips = w.county_fips ORDER BY jobs_2023 DESC;

-- name: sector_change_houston_msa
-- Job counts by industry in the Houston MSA; LQ = location quotient vs. Texas (>1 = specialised).
WITH msa AS (
  SELECT s.sector_code, s.year, SUM(s.jobs) AS jobs
  FROM fact_wac_sector s JOIN dim_tract d ON d.tract = s.tract WHERE d.in_houston_msa = 1 GROUP BY s.sector_code, s.year),
tx AS (SELECT sector_code, year, SUM(jobs) AS jobs FROM fact_wac_sector GROUP BY sector_code, year),
p AS (
  SELECT m.sector_code,
         MAX(CASE WHEN m.year = 2010 THEN m.jobs END) AS jobs_2010,
         MAX(CASE WHEN m.year = 2019 THEN m.jobs END) AS jobs_2019,
         MAX(CASE WHEN m.year = 2023 THEN m.jobs END) AS jobs_2023
  FROM msa m GROUP BY m.sector_code),
tot AS (
  SELECT (SELECT SUM(jobs) FROM msa WHERE year = 2023) AS msa_2023, (SELECT SUM(jobs) FROM tx WHERE year = 2023) AS tx_2023)
SELECT ds.sector_name, p.jobs_2010, p.jobs_2019, p.jobs_2023,
       p.jobs_2023 - p.jobs_2019                                                     AS abs_chg_2019_23,
       ROUND(100.0 * (p.jobs_2023 - p.jobs_2019) / p.jobs_2019, 1)                   AS pct_chg_2019_23,
       ROUND(100.0 * (p.jobs_2023 - p.jobs_2010) / p.jobs_2010, 1)                   AS pct_chg_2010_23,
       ROUND(100.0 * p.jobs_2023 / tot.msa_2023, 1)                                  AS share_of_msa_pct,
       ROUND((p.jobs_2023 * 1.0 / tot.msa_2023) / (t.jobs * 1.0 / tot.tx_2023), 2)   AS location_quotient
FROM p JOIN dim_sector ds ON ds.sector_code = p.sector_code
       JOIN tx t ON t.sector_code = p.sector_code AND t.year = 2023, tot
ORDER BY abs_chg_2019_23 DESC;

-- name: sector_diversification_hhi
-- Herfindahl-Hirschman index of industry concentration (0-10,000; lower = more diversified).
WITH m AS (
  SELECT dm.metro_name, s.year, s.sector_code, SUM(s.jobs) AS jobs
  FROM fact_wac_sector s JOIN dim_tract d ON d.tract = s.tract JOIN dim_metro dm ON dm.cbsa = d.cbsa
  GROUP BY dm.metro_name, s.year, s.sector_code),
sh AS (SELECT *, 100.0 * jobs / SUM(jobs) OVER (PARTITION BY metro_name, year) AS share FROM m)
SELECT metro_name, year, ROUND(SUM(share * share), 0) AS hhi
FROM sh GROUP BY metro_name, year ORDER BY metro_name, year;

-- name: houston_sector_share_trend
-- Energy vs. health care vs. the rest: sector shares of Houston MSA jobs over time.
WITH m AS (
  SELECT s.year, s.sector_code, SUM(s.jobs) AS jobs
  FROM fact_wac_sector s JOIN dim_tract d ON d.tract = s.tract WHERE d.cbsa = '26420' GROUP BY s.year, s.sector_code)
SELECT year, ds.sector_name, jobs, ROUND(100.0 * jobs / SUM(jobs) OVER (PARTITION BY year), 2) AS share_pct
FROM m JOIN dim_sector ds ON ds.sector_code = m.sector_code ORDER BY year, jobs DESC;

-- name: wage_mix_by_year_houston
-- Share of Houston MSA jobs by monthly-earnings band (LODES: low <= $1,250; mid $1,251-3,333; high > $3,333).
-- CAVEAT: the bands are fixed NOMINAL dollars, so inflation alone pushes jobs into higher bands over time.
-- Use this table for cross-sectional comparisons (place vs place, same year), not as a real-wage trend.
SELECT f.year, SUM(f.jobs) AS jobs,
       ROUND(100.0 * SUM(f.wage_low)  / SUM(f.jobs), 2) AS low_pct,
       ROUND(100.0 * SUM(f.wage_mid)  / SUM(f.jobs), 2) AS mid_pct,
       ROUND(100.0 * SUM(f.wage_high) / SUM(f.jobs), 2) AS high_pct
FROM fact_wac f JOIN dim_tract d ON d.tract = f.tract WHERE d.cbsa = '26420' GROUP BY f.year ORDER BY f.year;
