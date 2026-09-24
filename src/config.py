"""Central configuration: paths, study area, years, and LODES code books."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"
PROCESSED = ROOT / "data" / "processed"
DB_PATH = ROOT / "db" / "lodes.db"
SQL_DIR = ROOT / "sql"
FIG_DIR = ROOT / "outputs" / "figures"
REPORT_DIR = ROOT / "outputs" / "reports"
TABLE_DIR = ROOT / "outputs" / "tables"

LODES_BASE = "https://lehd.ces.census.gov/data/lodes/LODES8/tx"
TIGER_BASE = "https://www2.census.gov/geo/tiger/GENZ2023/shp"

WAC_YEARS = list(range(2010, 2024))
RAC_YEARS = list(range(2010, 2024))
OD_YEARS = [2015, 2019, 2023]  # post-oil-bust, pre-COVID, latest
BASE_YEAR, LATEST_YEAR = 2019, 2023

# Houston-The-Woodlands-Sugar Land MSA (CBSA 26420), 9 counties, 5-digit FIPS
HOUSTON_MSA_COUNTIES = {
    "48015": "Austin", "48039": "Brazoria", "48071": "Chambers",
    "48157": "Fort Bend", "48167": "Galveston", "48201": "Harris",
    "48291": "Liberty", "48339": "Montgomery", "48473": "Waller",
}
HARRIS_FIPS = "48201"
CBSA_HOUSTON = "26420"

# WAC/RAC job-count columns -> readable names (NAICS 2-digit supersectors, LODES CNS01-20)
NAICS_SECTORS = {
    "CNS01": "Agriculture, Forestry, Fishing",
    "CNS02": "Mining, Oil & Gas Extraction",
    "CNS03": "Utilities",
    "CNS04": "Construction",
    "CNS05": "Manufacturing",
    "CNS06": "Wholesale Trade",
    "CNS07": "Retail Trade",
    "CNS08": "Transportation & Warehousing",
    "CNS09": "Information",
    "CNS10": "Finance & Insurance",
    "CNS11": "Real Estate & Rental",
    "CNS12": "Professional, Scientific & Technical",
    "CNS13": "Management of Companies",
    "CNS14": "Admin, Support & Waste Mgmt",
    "CNS15": "Educational Services",
    "CNS16": "Health Care & Social Assistance",
    "CNS17": "Arts, Entertainment & Recreation",
    "CNS18": "Accommodation & Food Services",
    "CNS19": "Other Services",
    "CNS20": "Public Administration",
}
WAGE_BANDS = {"CE01": "Low (<= $1,250/mo)", "CE02": "Mid ($1,251-$3,333/mo)", "CE03": "High (> $3,333/mo)"}
AGE_BANDS = {"CA01": "Under 30", "CA02": "30-54", "CA03": "55+"}
