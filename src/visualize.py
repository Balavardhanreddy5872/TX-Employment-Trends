"""Charts, choropleth maps and an interactive map built from the SQL outputs (outputs/tables/*.csv).

Palette: validated categorical order (blue, orange, aqua, yellow), one-hue blue sequential ramp for magnitude,
blue<->red diverging with a gray midpoint for polarity. Series are direct-labelled (yellow/aqua sit below 3:1
contrast on white, so labels carry identity).
Usage: python -m src.visualize
"""
from __future__ import annotations

import sqlite3

import folium
import geopandas as gpd
import matplotlib as mpl
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, Normalize, TwoSlopeNorm

from src.config import DB_PATH, FIG_DIR, HOUSTON_MSA_COUNTIES, RAW, ROOT, TABLE_DIR

MAP_DIR = ROOT / "outputs" / "maps"
BLUE, ORANGE, AQUA, YELLOW, RED, GRAY = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e34948", "#8a8985"
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e6e5e1", "#fcfcfb"
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
seq_cmap = LinearSegmentedColormap.from_list("seq_blue", SEQ)
div_cmap = LinearSegmentedColormap.from_list("div", [RED, "#f1a9a8", "#f0efec", "#9ec5f4", BLUE])
METRO_COLOR = {"Houston": BLUE, "Dallas-Fort Worth": ORANGE, "Austin": AQUA, "San Antonio": YELLOW, "Texas": GRAY}

mpl.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE, "figure.dpi": 110,
    "font.family": "sans-serif", "font.size": 10, "text.color": INK, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK2, "axes.edgecolor": GRID, "axes.spines.top": False,
    "axes.spines.right": False, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.axisbelow": True, "axes.titlesize": 13, "axes.titleweight": "bold", "axes.titlelocation": "left",
})


def T(name: str) -> pd.DataFrame:
    return pd.read_csv(TABLE_DIR / f"{name}.csv", dtype={"tract": str})


def save(fig, name: str, note: str | None = None) -> None:
    if note:
        fig.text(0.01, 0.005, note, fontsize=7.5, color=INK2, ha="left", va="bottom")
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_DIR / f"{name}.png", dpi=170, bbox_inches="tight")
    plt.close(fig)
    print("  wrote", f"{name}.png")


SRC = "Source: Census LEHD LODES8 (WAC, all jobs, JT00). Analysis: this repo."


# ----------------------------------------------------------------------------- charts
def fig_metro_growth() -> None:
    d = T("metro_jobs_index")
    fig, ax = plt.subplots(figsize=(9, 5.2))
    for m, g in d.groupby("metro_name"):
        c = METRO_COLOR[m]
        ax.plot(g["year"], g["index_2010_100"], color=c, lw=3 if m == "Houston" else 2,
                ls="--" if m == "Texas" else "-", zorder=3 if m == "Houston" else 2)
        last = g.iloc[-1]
        dy = {"Texas": 2.2, "Houston": -2.2}.get(m, 0)
        ax.text(2023.15, last["index_2010_100"] + dy, f"{m}  {last['index_2010_100']:.0f}", color=INK, va="center", fontsize=9.5,
                fontweight="bold" if m == "Houston" else "normal")
        ax.scatter([2023], [last["index_2010_100"]], color=c, s=28, zorder=4, edgecolor=SURFACE, linewidth=1.5)
    for x, label, ha in [(2016, "Oil bust", "right"), (2017, "Harvey", "left"), (2020, "COVID-19", "center")]:
        ax.axvline(x, color=GRID, lw=1.2, zorder=1)
        ax.text(x + (-0.12 if ha == "right" else 0.12 if ha == "left" else 0), 165, label, ha=ha, va="bottom", fontsize=8.5, color=INK2)
    ax.set_xlim(2010, 2026); ax.set_ylim(95, 168)
    ax.set_xticks(range(2010, 2024, 2)); ax.set_ylabel("Jobs, index (2010 = 100)")
    ax.set_title("Houston kept pace until the 2015 oil bust, then lagged Texas' other big metros", pad=24)
    save(fig, "01_metro_job_growth_index", SRC)


def fig_houston_shocks() -> None:
    d = T("houston_shock_years").dropna(subset=["jobs_yoy_pct"])
    fig, ax = plt.subplots(figsize=(9, 4.6))
    w = 0.38
    ax.bar(d["year"] - w / 2, d["jobs_yoy_pct"], w, color=BLUE, label="All jobs", zorder=3)
    ax.bar(d["year"] + w / 2, d["mining_yoy_pct"], w, color=ORANGE, label="Oil, gas & mining jobs", zorder=3)
    ax.axhline(0, color=INK2, lw=1)
    ax.set_xticks(d["year"]); ax.set_xticklabels(d["year"], fontsize=9)
    ax.set_ylabel("Year-over-year change (%)"); ax.legend(frameon=False, loc="upper left", ncol=2)
    ax.set_title("Energy jobs swing ~3x harder than the whole Houston economy")
    save(fig, "02_houston_energy_vs_total_yoy", SRC + " Houston-The Woodlands-Sugar Land MSA.")


def fig_sector_change() -> None:
    d = T("sector_change_houston_msa").sort_values("abs_chg_2019_23")
    fig, ax = plt.subplots(figsize=(9.5, 6.4))
    colors = [BLUE if v >= 0 else RED for v in d["abs_chg_2019_23"]]
    ax.barh(d["sector_name"], d["abs_chg_2019_23"], color=colors, height=0.68, zorder=3)
    for y, (v, lq) in enumerate(zip(d["abs_chg_2019_23"], d["location_quotient"])):
        ax.text(v + (900 if v >= 0 else -900), y, f"{v:+,.0f}", va="center", ha="left" if v >= 0 else "right", fontsize=8.5, color=INK)
    ax.axvline(0, color=INK2, lw=1)
    ax.set_xlim(-24000, 50000); ax.set_xlabel("Change in jobs, 2019 to 2023"); ax.grid(axis="y", visible=False)
    ax.set_title("Where Houston added (and lost) jobs since 2019", pad=10)
    save(fig, "03_houston_sector_job_change", SRC + " Houston MSA. Oil & gas extraction fell 18% but is still 1.45x more concentrated than Texas overall.")


def fig_county() -> None:
    d = T("msa_county_summary")
    d = d[d["jobs_2023"] > 15000].sort_values("growth_2019_23_pct")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), gridspec_kw={"wspace": 0.45})
    ax = axes[0]
    ax.barh(d["county_name"], d["growth_2019_23_pct"], color=[BLUE if c != "Harris" else ORANGE for c in d["county_name"]], height=0.65, zorder=3)
    for y, v in enumerate(d["growth_2019_23_pct"]):
        ax.text(v + 0.4, y, f"{v:.1f}%", va="center", fontsize=9)
    ax.set_title("Job growth 2019-23 (%)"); ax.grid(axis="y", visible=False); ax.set_xlim(0, 30)
    ax = axes[1]
    d2 = d.sort_values("jobs_per_resident_worker")
    ax.barh(d2["county_name"], d2["jobs_per_resident_worker"], color=[BLUE if c != "Harris" else ORANGE for c in d2["county_name"]], height=0.65, zorder=3)
    ax.axvline(1, color=INK2, lw=1, ls="--"); ax.text(1.02, len(d2) - 0.45, "balanced", fontsize=8, color=INK2, va="bottom")
    for y, v in enumerate(d2["jobs_per_resident_worker"]):
        ax.text(v + 0.02, y, f"{v:.2f}", va="center", fontsize=9)
    ax.set_title("Jobs per resident worker, 2023"); ax.grid(axis="y", visible=False); ax.set_xlim(0, 1.5); ax.set_ylim(-0.6, len(d2))
    fig.suptitle("Growth is moving to the suburbs; Harris County still imports workers", x=0.01, ha="left", fontsize=13, fontweight="bold", y=1.02)
    save(fig, "04_county_growth_and_balance", SRC + " RAC = workers by residence. Counties with >15k jobs shown; Harris highlighted.")


def fig_centers() -> None:
    d = T("center_summary")
    d = d[d["center"] != "Rest of MSA"].sort_values("growth_2010_23_pct")
    fig, ax = plt.subplots(figsize=(9.5, 5.4))
    ax.barh(d["center"], d["growth_2010_23_pct"], color=BLUE, height=0.65, zorder=3)
    for y, (g, j) in enumerate(zip(d["growth_2010_23_pct"], d["jobs_2023"])):
        ax.text(g + 1.2, y, f"{g:+.0f}%   ({j/1000:,.0f}k jobs)", va="center", fontsize=8.8)
    rest = T("center_summary").query("center == 'Rest of MSA'").iloc[0]
    ax.axvline(rest["growth_2010_23_pct"], color=ORANGE, lw=1.6, ls="--")
    ax.text(rest["growth_2010_23_pct"] + 1, -0.85, f"rest of MSA +{rest['growth_2010_23_pct']:.0f}%", color=INK, fontsize=8.5)
    ax.set_xlim(-25, 105); ax.set_xlabel("Job growth 2010 to 2023 (%)"); ax.grid(axis="y", visible=False)
    ax.set_title("Legacy cores barely grew; new suburban cores and medicine did", pad=8)
    save(fig, "05_employment_center_growth", SRC + " Centers = census tracts whose centroid is within 3 mi of the district core.")


def fig_commute() -> None:
    c = T("commute_distance_trend"); io = T("harris_inbound_outbound")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), gridspec_kw={"wspace": 0.3, "width_ratios": [1.1, 1]})
    ax = axes[0]
    bands = [("pct_lt10mi", "< 10 mi", SEQ[1]), ("pct_10_25mi", "10-25 mi", SEQ[3]), ("pct_25_50mi", "25-50 mi", SEQ[5]), ("pct_50plus_mi", "50+ mi", INK)]
    bottom = np.zeros(len(c))
    for col, lab, color in bands:
        ax.bar(c["year"].astype(str), c[col], bottom=bottom, color=color, width=0.55, label=lab, edgecolor=SURFACE, linewidth=2, zorder=3)
        for i, (b, v) in enumerate(zip(bottom, c[col])):
            ax.text(i, b + v / 2, f"{v:.0f}%", ha="center", va="center", fontsize=8.5, color="white" if color != SEQ[1] else INK)
        bottom += c[col].to_numpy()
    ax.legend(frameon=False, bbox_to_anchor=(0.5, -0.07), loc="upper center", ncol=4, fontsize=8.5)
    ax.set_ylim(0, 100); ax.set_title("Distance from home to work site\n(Houston-MSA residents)", fontsize=11); ax.grid(axis="x", visible=False)
    ax = axes[1]
    ax.plot(io["year"], io["inbound_share_pct"], color=BLUE, lw=2.4, marker="o", ms=8, mec=SURFACE, mew=2)
    ax.plot(io["year"], io["outbound_share_pct"], color=ORANGE, lw=2.4, marker="o", ms=8, mec=SURFACE, mew=2)
    for col, color, lab in [("inbound_share_pct", BLUE, "Harris jobs held by\nnon-Harris residents"), ("outbound_share_pct", ORANGE, "Harris residents working\noutside Harris")]:
        ax.text(2023.4, io[col].iloc[-1], f"{io[col].iloc[-1]:.0f}%  {lab}", fontsize=8.5, va="center")
    ax.set_xlim(2014.5, 2028.5); ax.set_xticks([2015, 2019, 2023]); ax.set_ylim(10, 45); ax.set_ylabel("%")
    ax.set_title("Harris County commuting is\nbecoming more regional", fontsize=11)
    fig.suptitle("Longer, more regional commutes", x=0.01, ha="left", fontsize=13, fontweight="bold", y=1.08)
    save(fig, "06_commute_distance_and_harris_flows", "Source: LEHD LODES8 OD (main, JT00; both ends in Texas). Straight-line miles to employer-assigned work location; remote workers are counted at their employer's address.")


def fig_priority_bars() -> None:
    d = T("priority_summary_by_county").sort_values("low_wage_residents_score3")
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    ax.barh(d["county_name"], d["low_wage_residents_score3"], color=BLUE, height=0.65, zorder=3)
    for y, (v, n) in enumerate(zip(d["low_wage_residents_score3"], d["tracts_score3"])):
        ax.text(v + 200, y, f"{v:,.0f} workers in {n} tracts", va="center", fontsize=8.8)
    ax.set_xlim(0, 24500); ax.set_xlabel("Low-wage resident workers in highest-priority tracts"); ax.grid(axis="y", visible=False)
    ax.set_title("Where workforce-access investment would reach the most people", pad=8)
    save(fig, "07_priority_tracts_by_county", "Priority = top quartile of low-wage residents AND bottom quartile of nearby low-wage jobs per worker AND top quartile of 25+ mile low-wage commuters.")


# ----------------------------------------------------------------------------- maps
def load_geo() -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    tr = gpd.read_file(f"zip://{RAW / 'geo' / 'cb_2023_48_tract_500k.zip'}")
    tr = tr[tr["GEOID"].str[:5].isin(HOUSTON_MSA_COUNTIES)].to_crs(3083)
    co = gpd.read_file(f"zip://{RAW / 'geo' / 'cb_2023_us_county_500k.zip'}")
    co = co[(co["STATEFP"] == "48") & (co["GEOID"].isin(HOUSTON_MSA_COUNTIES))].to_crs(3083)
    return tr[["GEOID", "geometry"]].rename(columns={"GEOID": "tract"}), co


def map_data() -> pd.DataFrame:
    con = sqlite3.connect(DB_PATH)
    q = """
    SELECT d.tract, d.county_name, d.land_sqmi,
           COALESCE(w23.jobs,0) AS jobs_2023, COALESCE(w19.jobs,0) AS jobs_2019,
           COALESCE(r23.jobs,0) AS workers_2023
    FROM dim_tract d
    LEFT JOIN fact_wac w23 ON w23.tract=d.tract AND w23.year=2023
    LEFT JOIN fact_wac w19 ON w19.tract=d.tract AND w19.year=2019
    LEFT JOIN fact_rac r23 ON r23.tract=d.tract AND r23.year=2023
    WHERE d.in_houston_msa=1"""
    df = pd.read_sql_query(q, con, dtype={"tract": str})
    centers = pd.read_sql_query("SELECT * FROM dim_center", con)
    con.close()
    df["jobs_per_sqmi"] = df["jobs_2023"] / df["land_sqmi"].where(df["land_sqmi"] > 0)
    df["job_chg"] = df["jobs_2023"] - df["jobs_2019"]
    df["jobs_per_worker"] = (df["jobs_2023"] / df["workers_2023"].where(df["workers_2023"] > 0))
    df.attrs["centers"] = centers
    return df


LABEL_OFFSETS = {"Downtown": (10, 8, "left"), "Texas Medical Center": (10, -13, "left"), "Uptown / Galleria": (-9, -12, "right"),
                 "Energy Corridor": (-9, 4, "right"), "The Woodlands": (8, 4, "left"), "Sugar Land": (-8, -12, "right"),
                 "Greenspoint / IAH": (8, 4, "left"), "Baytown Industrial": (8, 6, "left"), "Clear Lake / NASA": (8, -12, "left")}


def new_map_fig(co):
    minx, miny, maxx, maxy = co.total_bounds
    return plt.subplots(figsize=(8.2, 8.2 * (maxy - miny) / (maxx - minx) + 0.6))


def _frame(ax, co, centers=None, label=True):
    co.boundary.plot(ax=ax, color="#3a3a38", lw=0.6, zorder=5)
    minx, miny, maxx, maxy = co.total_bounds
    ax.set_xlim(minx - 5000, maxx + 5000); ax.set_ylim(miny - 5000, maxy + 5000)
    ax.set_axis_off(); ax.grid(False)
    if centers is not None and label:
        pts = gpd.GeoSeries(gpd.points_from_xy(centers["lon"], centers["lat"]), crs=4326).to_crs(3083)
        for (x, y), name in zip(zip(pts.x, pts.y), centers["center"]):
            if name in LABEL_OFFSETS:
                dx, dy, ha = LABEL_OFFSETS[name]
                ax.scatter([x], [y], s=16, color=INK, zorder=7, edgecolor="white", linewidth=1)
                ax.annotate(name.split(" / ")[0], (x, y), xytext=(dx, dy), textcoords="offset points", fontsize=7.5, zorder=8, ha=ha,
                            path_effects=[pe.withStroke(linewidth=2.5, foreground="white")])


def choropleth(gdf, col, cmap, norm, title, subtitle, name, co, centers, cbar_label, missing="#e6e5e1", ticks=None, fmt=None):
    fig, ax = new_map_fig(co)
    gdf.plot(ax=ax, color=missing, linewidth=0, zorder=1)
    ok = gdf[gdf[col].notna()]
    ok.plot(ax=ax, column=col, cmap=cmap, norm=norm, linewidth=0.05, edgecolor="white", zorder=2)
    _frame(ax, co, centers)
    sm = mpl.cm.ScalarMappable(norm=norm, cmap=cmap)
    cb = fig.colorbar(sm, ax=ax, shrink=0.5, pad=0.01, aspect=22)
    cb.set_label(cbar_label, fontsize=8.5); cb.outline.set_visible(False)
    if ticks is not None:
        cb.set_ticks(ticks)
        if fmt:
            cb.set_ticklabels([fmt(t) for t in ticks])
    fig.suptitle(title, x=0.06, ha="left", fontsize=14, fontweight="bold", y=0.96)
    ax.set_title(subtitle, fontsize=9.5, color=INK2, fontweight="normal", pad=4)
    save(fig, name, "Source: Census LEHD LODES8 2023; Census cartographic tract boundaries. Gray = no jobs / too few workers.")


def make_maps() -> pd.DataFrame:
    tr, co = load_geo()
    df = map_data()
    centers = df.attrs["centers"]
    g = tr.merge(df, on="tract", how="left")
    tm = T("tract_metrics_2023")[["tract", "priority_score", "low_wage_residents"]]
    g = g.merge(tm, on="tract", how="left")

    dens = g.copy(); dens.loc[dens["jobs_2023"] < 25, "jobs_per_sqmi"] = np.nan
    choropleth(dens, "jobs_per_sqmi", seq_cmap, mpl.colors.LogNorm(vmin=100, vmax=50000),
               "Houston's jobs are concentrated in a handful of cores", "Jobs per square mile of land, 2023 (log scale)",
               "08_map_job_density", co, centers, "jobs / sq mi", ticks=[100, 1000, 10000, 50000], fmt=lambda t: f"{t:,.0f}")

    bal = g.copy(); bal["log2_ratio"] = np.log2(bal["jobs_per_worker"].clip(0.25, 4))
    bal.loc[(bal["jobs_2023"] < 50) | (bal["workers_2023"] < 100), "log2_ratio"] = np.nan
    choropleth(bal, "log2_ratio", div_cmap, TwoSlopeNorm(vmin=-2, vcenter=0, vmax=2),
               "Jobs-housing balance: job hubs vs. bedroom communities", "Jobs per resident worker, 2023 (blue: job hub; red: bedroom community)",
               "09_map_jobs_housing_balance", co, centers, "jobs per resident worker", ticks=[-2, -1, 0, 1, 2], fmt=lambda t: f"{2 ** t:g}x")

    chg = g.copy(); chg.loc[(chg["jobs_2023"] + chg["jobs_2019"]) < 50, "job_chg"] = np.nan
    choropleth(chg, "job_chg", div_cmap, TwoSlopeNorm(vmin=-3000, vcenter=0, vmax=3000),
               "Job growth is happening at the edges", "Change in jobs by tract, 2019 to 2023 (blue = gained; red = lost)",
               "10_map_job_change_2019_23", co, centers, "jobs added", ticks=[-3000, 0, 3000], fmt=lambda t: f"{t:+,.0f}")

    pr = g.copy()
    fig, ax = new_map_fig(co)
    pr.plot(ax=ax, color="#e6e5e1", linewidth=0, zorder=1)
    cols = {0: "#f1f6fd", 1: "#dbe9fa", 2: "#b3d1f5", 3: ORANGE}
    for s, c in cols.items():
        pr[pr["priority_score"] == s].plot(ax=ax, color=c, linewidth=0.05, edgecolor="white", zorder=2)
    _frame(ax, co, centers)
    handles = [mpl.patches.Patch(color=cols[s], label=lab) for s, lab in
               [(3, "3 of 3 signals (priority)"), (2, "2 signals"), (1, "1 signal"), (0, "none")]]
    ax.legend(handles=handles, loc="lower left", frameon=False, fontsize=8.5, title="Access-gap signals", title_fontsize=9)
    fig.suptitle("Where low-wage workers live far from low-wage jobs", x=0.06, ha="left", fontsize=14, fontweight="bold", y=0.96)
    ax.set_title("Many low-wage residents + few nearby low-wage jobs + many 25+ mile commuters", fontsize=9, color=INK2, fontweight="normal", pad=4)
    save(fig, "11_map_access_gap_priority_tracts", "Source: LEHD LODES8 2023 (RAC, WAC, OD). Screen for prioritisation, not a causal estimate. Gray = tract not screened (<100 resident workers).")
    return g


def interactive_map(g: gpd.GeoDataFrame) -> None:
    MAP_DIR.mkdir(parents=True, exist_ok=True)
    centers = pd.read_csv(TABLE_DIR / "center_summary.csv")
    ll = g.to_crs(4326).copy()
    ll["geometry"] = ll.geometry.simplify(0.0008)
    ll = ll.rename(columns={"jobs_2023": "Jobs 2023", "job_chg": "Job change 2019-23", "jobs_per_sqmi": "Jobs per sq mi",
                            "jobs_per_worker": "Jobs per resident worker", "priority_score": "Access-gap score (0-3)",
                            "low_wage_residents": "Low-wage residents"})
    keep = ["tract", "county_name", "Jobs 2023", "Job change 2019-23", "Jobs per sq mi", "Jobs per resident worker",
            "Access-gap score (0-3)", "Low-wage residents", "geometry"]
    ll = ll[keep].copy()
    for c in keep[2:-1]:
        ll[c] = ll[c].round(2)
    m = folium.Map(location=[29.85, -95.4], zoom_start=9, tiles="OpenStreetMap")
    layers = [("Jobs per sq mi", "Blues", "Job density (jobs / sq mi)", [0, 250, 1000, 3000, 10000, 60000]),
              ("Job change 2019-23", "RdBu", "Job change 2019-23", [-4000, -1000, -200, 0, 200, 1000, 4000]),
              ("Access-gap score (0-3)", "YlOrRd", "Access-gap score (0-3)", [0, 1, 2, 3, 3.01])]
    import branca.colormap as bcm
    palettes = {"Blues": ["#cde2fb", "#9ec5f4", "#5598e7", "#256abf", "#0d366b"],
                "RdBu": ["#e34948", "#f1a9a8", "#f0efec", "#9ec5f4", "#2a78d6", "#0d366b"],
                "YlOrRd": ["#f1f6fd", "#b3d1f5", "#3987e5", "#eb6834"]}
    for i, (col, cmap, name, bins) in enumerate(layers):
        d = ll[["tract", col, "geometry"]].copy()
        d[col] = d[col].fillna(0 if bins[0] <= 0 <= bins[-1] else bins[0]).clip(bins[0], bins[-1] - 0.005)
        colors = palettes[cmap][: len(bins) - 1]
        cm = bcm.StepColormap(colors, index=bins, vmin=bins[0], vmax=bins[-1], caption=name)
        fg = folium.FeatureGroup(name=name, show=(i == 0))
        folium.GeoJson(d.to_json(), style_function=lambda f, cm=cm, col=col: {"fillColor": cm(f["properties"][col]), "fillOpacity": 0.78,
                                                                              "color": "white", "weight": 0.3}).add_to(fg)
        fg.add_to(m)
        if i == 0:
            cm.add_to(m)
    tip = folium.GeoJson(ll.to_json(), style_function=lambda f: {"fillOpacity": 0, "weight": 0},
                         tooltip=folium.GeoJsonTooltip(fields=["county_name", "Jobs 2023", "Job change 2019-23", "Jobs per sq mi",
                                                               "Jobs per resident worker", "Low-wage residents", "Access-gap score (0-3)"],
                                                       aliases=["County", "Jobs 2023", "Change 2019-23", "Jobs/sq mi", "Jobs per resident worker", "Low-wage residents", "Access-gap score"]))
    tip.add_to(m)
    con = sqlite3.connect(DB_PATH)
    for _, r in pd.read_sql_query("SELECT * FROM dim_center", con).merge(centers, on="center").iterrows():
        folium.CircleMarker([r["lat"], r["lon"]], radius=5, color="#0b0b0b", fill=True, fill_color="white", fill_opacity=1,
                            tooltip=f"{r['center']}: {r['jobs_2023']:,.0f} jobs ({r['growth_2019_23_pct']:+.1f}% since 2019)").add_to(m)
    con.close()
    folium.LayerControl(collapsed=False).add_to(m)
    m.save(MAP_DIR / "houston_jobs_interactive.html")
    print("  wrote houston_jobs_interactive.html")


def run() -> None:
    print("charts")
    for f in (fig_metro_growth, fig_houston_shocks, fig_sector_change, fig_county, fig_centers, fig_commute, fig_priority_bars):
        f()
    print("maps")
    g = make_maps()
    interactive_map(g)


if __name__ == "__main__":
    run()
