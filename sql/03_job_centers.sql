-- Q4: Where are the jobs? Employment centers, densest tracts, and how the geography is shifting.

-- name: center_summary
WITH j AS (
  SELECT tc.center,
         SUM(CASE WHEN w.year = 2010 THEN w.jobs END) AS jobs_2010,
         SUM(CASE WHEN w.year = 2019 THEN w.jobs END) AS jobs_2019,
         SUM(CASE WHEN w.year = 2023 THEN w.jobs END) AS jobs_2023,
         SUM(CASE WHEN w.year = 2023 THEN w.wage_high END) AS high_2023,
         SUM(CASE WHEN w.year = 2023 THEN w.wage_low END)  AS low_2023,
         SUM(CASE WHEN w.year = 2023 THEN w.cns16 END)     AS health_2023,
         SUM(CASE WHEN w.year = 2023 THEN w.cns02 + w.cns05 END) AS energy_mfg_2023,
         COUNT(DISTINCT w.tract) AS tracts
  FROM fact_wac w JOIN tract_center tc ON tc.tract = w.tract GROUP BY tc.center)
SELECT center, tracts, jobs_2010, jobs_2019, jobs_2023,
       ROUND(100.0 * jobs_2023 / SUM(jobs_2023) OVER (), 1)                  AS share_of_msa_jobs_pct,
       ROUND(100.0 * (jobs_2023 - jobs_2019) / jobs_2019, 1)                 AS growth_2019_23_pct,
       ROUND(100.0 * (jobs_2023 - jobs_2010) / jobs_2010, 1)                 AS growth_2010_23_pct,
       ROUND(100.0 * high_2023 / jobs_2023, 1)                               AS high_wage_share_pct,
       ROUND(100.0 * low_2023 / jobs_2023, 1)                                AS low_wage_share_pct,
       ROUND(100.0 * health_2023 / jobs_2023, 1)                             AS health_care_share_pct,
       ROUND(100.0 * energy_mfg_2023 / jobs_2023, 1)                         AS energy_mfg_share_pct
FROM j ORDER BY jobs_2023 DESC;

-- name: top_job_tracts_2023
-- 25 densest employment tracts in the MSA (tracts > 0.05 sq mi land to avoid tiny-polygon artefacts).
SELECT d.tract, d.county_name, tc.center, w.jobs, ROUND(d.land_sqmi, 2) AS land_sqmi,
       ROUND(w.jobs / d.land_sqmi, 0) AS jobs_per_sqmi,
       ROUND(100.0 * w.wage_high / w.jobs, 1) AS high_wage_pct, ROUND(100.0 * w.wage_low / w.jobs, 1) AS low_wage_pct
FROM fact_wac w JOIN dim_tract d ON d.tract = w.tract JOIN tract_center tc ON tc.tract = w.tract
WHERE w.year = 2023 AND d.land_sqmi > 0.05 AND w.jobs > 1000
ORDER BY jobs_per_sqmi DESC LIMIT 25;

-- name: decentralization_by_ring
-- Are jobs moving outward? Share of MSA jobs by distance from Downtown Houston.
WITH t AS (
  SELECT d.tract, haversine_mi(d.lat, d.lon, c.lat, c.lon) AS mi_from_downtown
  FROM dim_tract d, dim_center c WHERE d.in_houston_msa = 1 AND c.center = 'Downtown'),
b AS (
  SELECT w.year,
         CASE WHEN t.mi_from_downtown < 5 THEN '1. 0-5 mi' WHEN t.mi_from_downtown < 10 THEN '2. 5-10 mi'
              WHEN t.mi_from_downtown < 20 THEN '3. 10-20 mi' WHEN t.mi_from_downtown < 35 THEN '4. 20-35 mi'
              ELSE '5. 35+ mi' END AS ring, SUM(w.jobs) AS jobs
  FROM fact_wac w JOIN t ON t.tract = w.tract GROUP BY w.year, ring)
SELECT year, ring, jobs, ROUND(100.0 * jobs / SUM(jobs) OVER (PARTITION BY year), 2) AS share_pct
FROM b ORDER BY year, ring;

-- name: fastest_growing_tracts_2019_23
-- Tracts adding the most jobs since 2019 (min. 500 jobs in 2019 so growth is not a tiny-base artefact).
SELECT d.tract, d.county_name, tc.center, a.jobs AS jobs_2019, b.jobs AS jobs_2023, b.jobs - a.jobs AS added_jobs,
       ROUND(100.0 * (b.jobs - a.jobs) / a.jobs, 1) AS growth_pct
FROM fact_wac a JOIN fact_wac b ON b.tract = a.tract AND b.year = 2023
     JOIN dim_tract d ON d.tract = a.tract JOIN tract_center tc ON tc.tract = a.tract
WHERE a.year = 2019 AND a.jobs >= 500 ORDER BY added_jobs DESC LIMIT 20;
