-- Q1: How has Houston's job base grown relative to Texas' other big metros?

-- name: metro_jobs_index
SELECT metro_name, year, jobs,
       ROUND(100.0 * jobs / FIRST_VALUE(jobs) OVER (PARTITION BY metro_name ORDER BY year), 1) AS index_2010_100,
       ROUND(100.0 * (jobs * 1.0 / LAG(jobs) OVER (PARTITION BY metro_name ORDER BY year) - 1), 2) AS yoy_pct
FROM v_metro_jobs
ORDER BY metro_name, year;

-- name: metro_growth_summary
WITH p AS (
  SELECT metro_name,
         MAX(CASE WHEN year = 2010 THEN jobs END) AS jobs_2010,
         MAX(CASE WHEN year = 2014 THEN jobs END) AS jobs_2014,
         MAX(CASE WHEN year = 2016 THEN jobs END) AS jobs_2016,
         MAX(CASE WHEN year = 2019 THEN jobs END) AS jobs_2019,
         MAX(CASE WHEN year = 2020 THEN jobs END) AS jobs_2020,
         MAX(CASE WHEN year = 2023 THEN jobs END) AS jobs_2023
  FROM v_metro_jobs GROUP BY metro_name)
SELECT metro_name, jobs_2010, jobs_2019, jobs_2023,
       ROUND(100 * (power(jobs_2019 * 1.0 / jobs_2010, 1.0 / 9) - 1), 2)  AS cagr_2010_19_pct,
       ROUND(100 * (power(jobs_2023 * 1.0 / jobs_2019, 1.0 / 4) - 1), 2)  AS cagr_2019_23_pct,
       ROUND(100.0 * (jobs_2016 - jobs_2014) / jobs_2014, 2)              AS chg_2014_16_pct,
       ROUND(100.0 * (jobs_2020 - jobs_2019) / jobs_2019, 2)              AS covid_chg_2019_20_pct,
       ROUND(100.0 * (jobs_2023 - jobs_2020) / jobs_2020, 2)              AS recovery_2020_23_pct,
       ROUND(100.0 * (jobs_2023 - jobs_2019) / jobs_2019, 2)              AS chg_2019_23_pct
FROM p ORDER BY jobs_2023 DESC;

-- name: houston_shock_years
-- Houston MSA: year-over-year change in total jobs vs. oil & gas / mining jobs (2014-16 oil bust, 2020 COVID).
WITH h AS (
  SELECT w.year, SUM(w.jobs) AS jobs, SUM(w.cns02) AS mining_jobs
  FROM fact_wac w JOIN dim_tract d ON d.tract = w.tract WHERE d.cbsa = '26420' GROUP BY w.year)
SELECT year, jobs, mining_jobs,
       ROUND(100.0 * (jobs * 1.0 / LAG(jobs) OVER (ORDER BY year) - 1), 2)                  AS jobs_yoy_pct,
       ROUND(100.0 * (mining_jobs * 1.0 / LAG(mining_jobs) OVER (ORDER BY year) - 1), 2)    AS mining_yoy_pct,
       ROUND(100.0 * mining_jobs / jobs, 2)                                                 AS mining_share_pct
FROM h ORDER BY year;
