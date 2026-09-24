-- Q6: Where do low-wage workers live far from jobs? (spatial-mismatch screen -> policy targeting)
-- Triangulates three independent signals per tract:
--   (1) concentration of low-wage resident workers        (RAC)
--   (2) few low-wage jobs per low-wage worker within 10 miles  (WAC/RAC + geography; a cumulative-opportunity
--       job-worker ratio, which controls for density so dense job-rich AND worker-rich areas are not flagged)
--   (3) high share of low-wage workers commuting 25+ miles     (OD; share is more robust than the mean)
-- Bands are nominal dollars, so this screen is used cross-sectionally (2023 only), never as a time trend.

-- name: setup_tract_pairs
-- All Houston-MSA tract pairs whose centroids are within 10 miles (bounding-box prefilter, then exact haversine).
DROP TABLE IF EXISTS tract_pairs;
CREATE TABLE tract_pairs AS
SELECT a.tract AS home_tract, b.tract AS job_tract, haversine_mi(a.lat, a.lon, b.lat, b.lon) AS dist_mi
FROM dim_tract a JOIN dim_tract b
  ON a.in_houston_msa = 1 AND b.in_houston_msa = 1 AND ABS(a.lat - b.lat) < 0.15 AND ABS(a.lon - b.lon) < 0.17
WHERE haversine_mi(a.lat, a.lon, b.lat, b.lon) <= 10;
CREATE INDEX ix_tp_h ON tract_pairs(home_tract);
CREATE INDEX ix_tp_j ON tract_pairs(job_tract);

-- name: setup_tract_access
DROP TABLE IF EXISTS tract_access;
CREATE TABLE tract_access AS
WITH jobs_side AS (
  SELECT p.home_tract AS tract, w.year, SUM(w.jobs) AS jobs_10mi, SUM(w.wage_low) AS low_wage_jobs_10mi
  FROM tract_pairs p JOIN fact_wac w ON w.tract = p.job_tract AND w.year IN (2019, 2023) GROUP BY p.home_tract, w.year),
workers_side AS (
  SELECT p.home_tract AS tract, r.year, SUM(r.wage_low) AS low_wage_workers_10mi
  FROM tract_pairs p JOIN fact_rac r ON r.tract = p.job_tract AND r.year IN (2019, 2023) GROUP BY p.home_tract, r.year)
SELECT j.tract, j.year, j.jobs_10mi, j.low_wage_jobs_10mi, s.low_wage_workers_10mi,
       j.low_wage_jobs_10mi * 1.0 / s.low_wage_workers_10mi AS lw_jobs_per_lw_worker_10mi
FROM jobs_side j JOIN workers_side s ON s.tract = j.tract AND s.year = j.year;
CREATE INDEX ix_ta ON tract_access(tract, year);

-- name: setup_tract_metrics_2023
DROP TABLE IF EXISTS tract_metrics_2023;
CREATE TABLE tract_metrics_2023 AS
WITH od_home AS (
  SELECT h_tract AS tract, SUM(jobs) AS od_workers, SUM(dist_x_jobs) / SUM(jobs) AS avg_miles_all,
         SUM(dist_x_low) / NULLIF(SUM(wage_low), 0) AS avg_miles_low_wage,
         1.0 * SUM(wage_low_25plus) / NULLIF(SUM(wage_low), 0) AS share_low_wage_25plus
  FROM fact_od WHERE year = 2023 GROUP BY h_tract),
base AS (
  SELECT d.tract, d.county_name, d.lat, d.lon, d.land_sqmi, tc.center,
         COALESCE(w.jobs, 0) AS jobs, COALESCE(w.wage_high, 0) AS high_wage_jobs, COALESCE(w.wage_low, 0) AS low_wage_jobs,
         COALESCE(r.jobs, 0) AS resident_workers, COALESCE(r.wage_low, 0) AS low_wage_residents,
         a.jobs_10mi, a.low_wage_jobs_10mi, a.low_wage_workers_10mi, a.lw_jobs_per_lw_worker_10mi,
         o.avg_miles_all, o.avg_miles_low_wage, o.share_low_wage_25plus
  FROM dim_tract d
  JOIN tract_center tc ON tc.tract = d.tract
  LEFT JOIN fact_wac w ON w.tract = d.tract AND w.year = 2023
  LEFT JOIN fact_rac r ON r.tract = d.tract AND r.year = 2023
  LEFT JOIN tract_access a ON a.tract = d.tract AND a.year = 2023
  LEFT JOIN od_home o ON o.tract = d.tract
  WHERE d.in_houston_msa = 1),
q AS (
  SELECT *,
    NTILE(4) OVER (ORDER BY low_wage_residents)       AS q_low_wage_residents,   -- 4 = most low-wage residents
    NTILE(4) OVER (ORDER BY lw_jobs_per_lw_worker_10mi) AS q_low_wage_job_access, -- 1 = fewest jobs per worker nearby
    NTILE(4) OVER (ORDER BY share_low_wage_25plus)    AS q_low_wage_commute      -- 4 = most 25+ mile commuters
  FROM base WHERE resident_workers >= 100 AND lw_jobs_per_lw_worker_10mi IS NOT NULL AND share_low_wage_25plus IS NOT NULL)
SELECT q.*,
       (q_low_wage_residents = 4) + (q_low_wage_job_access = 1) + (q_low_wage_commute = 4) AS priority_score
FROM q;

-- name: tract_metrics_2023
SELECT * FROM tract_metrics_2023 ORDER BY tract;

-- name: priority_summary_by_county
-- priority_score 3 = high on all three signals; >= 2 counts as 'elevated'.
WITH t AS (SELECT * FROM tract_metrics_2023)
SELECT county_name,
       COUNT(*) AS tracts_screened,
       SUM(priority_score = 3)                                                   AS tracts_score3,
       SUM(priority_score >= 2)                                                  AS tracts_score2plus,
       SUM(CASE WHEN priority_score = 3 THEN low_wage_residents ELSE 0 END)     AS low_wage_residents_score3,
       ROUND(100.0 * SUM(CASE WHEN priority_score = 3 THEN low_wage_residents ELSE 0 END)
             / (SELECT SUM(low_wage_residents) FROM t), 2)                       AS pct_of_msa_low_wage_residents,
       ROUND(100.0 * SUM(CASE WHEN priority_score = 3 THEN share_low_wage_25plus * low_wage_residents END)
             / NULLIF(SUM(CASE WHEN priority_score = 3 THEN low_wage_residents END), 0), 1) AS pct_low_wage_25plus_mi_score3
FROM t GROUP BY county_name ORDER BY low_wage_residents_score3 DESC;

-- name: priority_tracts_top25
SELECT tract, county_name, center AS nearest_center, low_wage_residents, low_wage_jobs_10mi,
       ROUND(lw_jobs_per_lw_worker_10mi, 2) AS lw_jobs_per_lw_worker_10mi,
       ROUND(100 * share_low_wage_25plus, 1) AS pct_lw_workers_25plus_mi, priority_score
FROM tract_metrics_2023 WHERE priority_score = 3 ORDER BY low_wage_residents DESC LIMIT 25;

-- name: job_worker_ratio_by_county_2023
-- Resident-weighted low-wage job-to-worker ratio within 10 miles (>1 = more low-wage jobs than low-wage workers nearby).
SELECT county_name, SUM(low_wage_residents) AS low_wage_residents,
       ROUND(SUM(lw_jobs_per_lw_worker_10mi * low_wage_residents) / SUM(low_wage_residents), 2) AS lw_jobs_per_lw_worker_10mi,
       ROUND(100.0 * SUM(share_low_wage_25plus * low_wage_residents) / SUM(low_wage_residents), 1) AS pct_lw_workers_25plus_mi
FROM tract_metrics_2023 GROUP BY county_name ORDER BY low_wage_residents DESC;
