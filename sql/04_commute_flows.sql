-- Q5: How do people commute? (LODES OD "main" = both home and work in Texas; distances are straight-line.)

-- name: commute_distance_trend
-- Houston-MSA RESIDENTS: average one-way straight-line distance to the employer-assigned work location, and the
-- distance-band mix. CAVEAT: LODES places remote workers at their employer's address, so long-distance shares
-- overstate physical commuting after 2020; the mean is also pulled up by a long tail (bands are more robust).
SELECT o.year, SUM(o.jobs) AS workers,
       ROUND(SUM(o.dist_x_jobs) / SUM(o.jobs), 2)                    AS avg_miles_all,
       ROUND(SUM(o.dist_x_low)  / SUM(o.wage_low), 2)                AS avg_miles_low_wage,
       ROUND(SUM(o.dist_x_high) / SUM(o.wage_high), 2)               AS avg_miles_high_wage,
       ROUND(100.0 * SUM(o.jobs_lt10)   / SUM(o.jobs), 1)            AS pct_lt10mi,
       ROUND(100.0 * SUM(o.jobs_10_25)  / SUM(o.jobs), 1)            AS pct_10_25mi,
       ROUND(100.0 * SUM(o.jobs_25_50)  / SUM(o.jobs), 1)            AS pct_25_50mi,
       ROUND(100.0 * SUM(o.jobs_50plus) / SUM(o.jobs), 1)            AS pct_50plus_mi
FROM fact_od o JOIN dim_tract h ON h.tract = o.h_tract WHERE h.in_houston_msa = 1 GROUP BY o.year ORDER BY o.year;

-- name: county_flow_matrix_2023
-- Home county (rows) x work county (columns) worker flows for the 9-county MSA; everything else lumped as 'Other TX'.
SELECT CASE WHEN h.in_houston_msa = 1 THEN h.county_name ELSE 'Other TX' END AS home_county,
       CASE WHEN w.in_houston_msa = 1 THEN w.county_name ELSE 'Other TX' END AS work_county,
       SUM(o.jobs) AS workers
FROM fact_od o JOIN dim_tract h ON h.tract = o.h_tract JOIN dim_tract w ON w.tract = o.w_tract
WHERE o.year = 2023 GROUP BY home_county, work_county ORDER BY home_county, workers DESC;

-- name: harris_inbound_outbound
-- Harris County: share of its jobs filled by residents of OTHER counties (inbound), and share of its resident
-- workers who work OUTSIDE Harris (outbound). Uses the denormalised county columns on fact_od.
WITH inb AS (
  SELECT year, SUM(jobs) AS jobs_in_harris, SUM(CASE WHEN h_county <> '48201' THEN jobs ELSE 0 END) AS filled_by_outside_residents
  FROM fact_od WHERE w_county = '48201' GROUP BY year),
outb AS (
  SELECT year, SUM(jobs) AS harris_resident_workers, SUM(CASE WHEN w_county <> '48201' THEN jobs ELSE 0 END) AS work_outside_harris
  FROM fact_od WHERE h_county = '48201' GROUP BY year)
SELECT inb.year, jobs_in_harris, filled_by_outside_residents,
       ROUND(100.0 * filled_by_outside_residents / jobs_in_harris, 1) AS inbound_share_pct,
       harris_resident_workers, work_outside_harris,
       ROUND(100.0 * work_outside_harris / harris_resident_workers, 1) AS outbound_share_pct
FROM inb JOIN outb ON outb.year = inb.year ORDER BY inb.year;

-- name: home_county_commute_profile
-- Which home counties send workers furthest? (Houston MSA residents, by year)
SELECT h.county_name AS home_county, o.year, SUM(o.jobs) AS workers,
       ROUND(SUM(o.dist_x_jobs) / SUM(o.jobs), 1) AS avg_miles,
       ROUND(100.0 * (SUM(o.jobs_25_50) + SUM(o.jobs_50plus)) / SUM(o.jobs), 1) AS pct_over_25mi,
       ROUND(100.0 * SUM(CASE WHEN w.county_fips = '48201' THEN o.jobs ELSE 0 END) / SUM(o.jobs), 1) AS pct_work_in_harris
FROM fact_od o JOIN dim_tract h ON h.tract = o.h_tract JOIN dim_tract w ON w.tract = o.w_tract
WHERE h.in_houston_msa = 1 GROUP BY h.county_name, o.year ORDER BY o.year, workers DESC;

-- name: top_center_commute_sheds_2023
-- For each employment center: jobs held by workers who live 25+ miles away, and where the typical worker lives.
SELECT tc.center, SUM(o.jobs) AS jobs_held_by_od_workers,
       ROUND(SUM(o.dist_x_jobs) / SUM(o.jobs), 1) AS avg_miles_workers_travel,
       ROUND(100.0 * (SUM(o.jobs_25_50) + SUM(o.jobs_50plus)) / SUM(o.jobs), 1) AS pct_from_25plus_mi,
       ROUND(100.0 * SUM(CASE WHEN h.county_fips = '48201' THEN o.jobs ELSE 0 END) / SUM(o.jobs), 1) AS pct_live_in_harris
FROM fact_od o JOIN tract_center tc ON tc.tract = o.w_tract JOIN dim_tract h ON h.tract = o.h_tract
WHERE o.year = 2023 AND tc.center <> 'Rest of MSA' GROUP BY tc.center ORDER BY jobs_held_by_od_workers DESC;

-- name: top_tract_pair_flows_2023
SELECT h.county_name AS home_county, o.h_tract, w.county_name AS work_county, o.w_tract, tc.center AS work_center,
       o.jobs AS workers, ROUND(o.dist_x_jobs / o.jobs, 1) AS miles
FROM fact_od o JOIN dim_tract h ON h.tract = o.h_tract JOIN dim_tract w ON w.tract = o.w_tract
     LEFT JOIN tract_center tc ON tc.tract = o.w_tract
WHERE o.year = 2023 AND o.h_tract <> o.w_tract ORDER BY o.jobs DESC LIMIT 20;
