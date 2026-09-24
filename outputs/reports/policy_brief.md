# Houston's job base: where it is growing, where it is stalling, and where workers are stranded

**Audience:** regional workforce board / transportation planners / economic-development leaders
**Question:** *Where should the Houston region target workforce-access investment, given how its jobs and commutes have changed since 2010?*
**Data:** Census LEHD LODES8, Texas, 2010-2023 (workplace, residence and origin-destination files), 9-county Houston-The Woodlands-Sugar Land MSA (1,606 census tracts).

## Bottom line

1. **Houston stopped keeping pace with Texas' other big metros after the 2015 oil bust.** Jobs grew 2.4%/yr in 2010-19 (Texas: 2.3%) but only 1.7%/yr in 2019-23, against 2.9% for Dallas-Fort Worth and 4.2% for Austin. Houston added 215k jobs since 2019 (+6.9%); DFW added 456k (+12.3%).
2. **The economy is diversifying away from energy, and the mix is healthy.** Oil, gas and mining jobs fell 35% from their 2014 peak (116k to 75k) and lost 18% since 2019, yet the region's industry concentration index (HHI 760) is essentially unchanged and on par with Dallas-Fort Worth (749). Growth since 2019 came from professional/scientific/technical services (+42k), health care (+37k) and transportation & warehousing (+27k).
3. **Jobs are moving out, and Harris County is losing share.** Harris still holds 76% of MSA jobs but grew 4.5% since 2019 versus 20.5% in Montgomery, 16.1% in Fort Bend and 24.6% in Chambers. The share of MSA jobs 20-35 miles from Downtown rose from 15.4% to 22.1% (2010-23); downtown/inner-loop rings fell from 39.8% to 33.0%. The Woodlands (+71%), Sugar Land (+56%), Energy Corridor (+27%) and the Texas Medical Center (+26%) grew far faster than Downtown (+7%) and Uptown/Galleria (+1%).
4. **Commutes are getting longer and more regional.** Among Houston-MSA residents the share of jobs 25+ miles from home rose from 22.5% to 26.9% (2015-23). 37% of Harris jobs are now held by non-Harris residents (32.5% in 2015), and 23% of Harris residents work outside the county (18.3%).
5. **About 50,000 low-wage workers live in 93 tracts that are short on nearby low-wage jobs and long on 25+ mile commutes.** They are concentrated in Harris (16.7k workers, 32 tracts), Montgomery (8.1k, 16), Fort Bend (6.4k, 12), Galveston (5.0k, 9), Brazoria (4.9k, 10) and Liberty (3.9k, 7).

## Evidence

| Finding | Number | Where in repo |
|---|---|---|
| Houston MSA jobs 2010 / 2019 / 2023 | 2.53M / 3.13M / 3.35M | `outputs/tables/metro_growth_summary.csv` |
| 2019-23 growth: Houston vs DFW / Austin / San Antonio / Texas | 6.9% vs 12.3% / 18.0% / 9.8% / 8.9% | same |
| Oil bust: Houston job growth in 2016, 2017 | +0.02%, +0.11% (mining -13%, -15%) | `houston_shock_years.csv` |
| Location quotient (vs Texas): mining / construction / finance / information | 1.45 / 1.18 / 0.74 / 0.62 | `sector_change_houston_msa.csv` |
| Harris jobs per resident worker vs Fort Bend / Montgomery | 1.22 vs 0.60 / 0.75 | `msa_county_summary.csv` |
| Low-wage jobs per low-wage worker within 10 mi: Harris vs Brazoria vs Liberty | 1.15 vs 0.70 vs 0.48 | `job_worker_ratio_by_county_2023.csv` |
| Residents commuting 25+ mi: Harris vs Montgomery vs Liberty | 20% vs 47% vs 70% | `home_county_commute_profile.csv` |
| Priority tracts / low-wage workers in them | 93 / 49,704 (9.8% of 505k) | `priority_summary_by_county.csv` |

Figures: `outputs/figures/01` to `11`; interactive tract map: `outputs/maps/houston_jobs_interactive.html`.

## Recommendations

1. **Pilot commuter access where the gap is widest, not where transit already runs.** Start with candidate corridors that link priority-tract clusters in Montgomery, Liberty/Chambers and Brazoria to their nearest large job centers (The Woodlands/Greenspoint, Baytown/Ship Channel, Clear Lake/Texas Medical Center). Use vanpool and microtransit first: with 25+ mile trips and dispersed origins, fixed-route service will not pencil out. *Success metric: share of low-wage residents in pilot tracts able to reach 25k+ jobs within 45 minutes.*
2. **Anchor suburban job growth in the sectors that already scale outside the core.** Health care, logistics and professional services drove 2019-23 growth and are present in Fort Bend, Montgomery and Galveston. Where low-wage jobs-per-worker within 10 miles is below ~0.8 (Brazoria 0.70, Liberty 0.48), incentives and hiring partnerships for these sectors bring jobs to workers rather than the reverse.
3. **Treat energy as a cycle, not a trend.** Mining is still 1.45x over-represented and swings ~3x harder than total jobs. Keep the region's diversification trajectory (tech/professional services, health, logistics) funded and track the mining location quotient and the 20-35 mile job ring annually as early-warning indicators.
4. **Validate before spending.** This is a screening tool. Overlay vehicle access (ACS), METRO/Harris County transit routes (GTFS) and employer locations for the 93 priority tracts before committing budget.

## Caveats (read before quoting numbers)

* **Wage bands are nominal.** LODES "low / mid / high" earnings bands ($1,250 / $3,333 per month) are fixed in nominal dollars, so inflation moves jobs into higher bands over time. Wage comparisons here are across places within 2023, never a real-wage trend.
* **Commute distance is straight-line to the employer-assigned work address.** LODES places remote workers at their employer's address and some multi-site firms at headquarters, so long-distance shares (and the 2015-23 rise) overstate physical commuting after 2020. Directional conclusions (more regional) hold; exact miles do not.
* **OD "main" files include only workers who live and work in Texas**; out-of-state flows and federal/military/self-employed jobs outside UI coverage are not in LODES.
* **LODES injects noise at block level** (differential privacy). All analysis is at tract level or higher; tract-level ratios for small tracts are volatile.
* **Center boundaries are approximate** (tract centroids within 3 mi of hand-placed anchor points).
* The screen ranks tracts on three correlated signals; it identifies *where to look*, not *causal* effects of transit or job placement.
