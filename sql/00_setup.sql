-- Reusable dimensions and views. Blocks named `setup_*` run silently; every other block is exported to
-- outputs/tables/<name>.csv by src/run_sql.py.  Dialect: SQLite (UDFs power/sqrt/ln/exp/haversine_mi are
-- registered by the runner).

-- name: setup_metros
DROP TABLE IF EXISTS dim_metro;
CREATE TABLE dim_metro (cbsa TEXT PRIMARY KEY, metro_name TEXT);
INSERT INTO dim_metro VALUES ('26420','Houston'), ('19100','Dallas-Fort Worth'), ('12420','Austin'), ('41700','San Antonio');

DROP VIEW IF EXISTS v_metro_jobs;
CREATE VIEW v_metro_jobs AS
SELECT m.metro_name, w.year, SUM(w.jobs) AS jobs, SUM(w.wage_high) AS high_wage_jobs, SUM(w.wage_low) AS low_wage_jobs
FROM fact_wac w JOIN dim_tract d ON d.tract = w.tract JOIN dim_metro m ON m.cbsa = d.cbsa
GROUP BY m.metro_name, w.year
UNION ALL
SELECT 'Texas', year, SUM(jobs), SUM(wage_high), SUM(wage_low) FROM fact_wac GROUP BY year;

-- name: setup_centers
-- Approximate anchor points of the region's major employment centers (lat/lon of the district core).
DROP TABLE IF EXISTS dim_center;
CREATE TABLE dim_center (center TEXT PRIMARY KEY, lat REAL, lon REAL);
INSERT INTO dim_center VALUES
 ('Downtown',                29.7590, -95.3670),
 ('Texas Medical Center',    29.7100, -95.4000),
 ('Uptown / Galleria',       29.7390, -95.4610),
 ('Westchase',               29.7250, -95.5650),
 ('Energy Corridor',         29.7830, -95.6260),
 ('Greenspoint / IAH',       29.9430, -95.4150),
 ('The Woodlands',           30.1650, -95.4610),
 ('Sugar Land',              29.5900, -95.6150),
 ('Clear Lake / NASA',       29.5500, -95.0960),
 ('Ship Channel / Pasadena', 29.7150, -95.2000),
 ('Baytown Industrial',      29.7400, -94.9800);

-- name: setup_tract_center
-- Assign each Houston-MSA tract to its nearest employment center if its centroid lies within 3 miles.
DROP TABLE IF EXISTS tract_center;
CREATE TABLE tract_center AS
WITH d AS (
  SELECT t.tract, c.center, haversine_mi(t.lat, t.lon, c.lat, c.lon) AS dist_mi,
         ROW_NUMBER() OVER (PARTITION BY t.tract ORDER BY haversine_mi(t.lat, t.lon, c.lat, c.lon)) AS rk
  FROM dim_tract t CROSS JOIN dim_center c WHERE t.in_houston_msa = 1)
SELECT tract, CASE WHEN dist_mi <= 3.0 THEN center ELSE 'Rest of MSA' END AS center, dist_mi
FROM d WHERE rk = 1;
CREATE INDEX ix_tc ON tract_center(tract);
