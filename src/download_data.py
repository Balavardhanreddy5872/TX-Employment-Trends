"""Download LODES8 (TX) WAC/RAC/OD files, the geography crosswalk, and TIGER cartographic boundaries.

Idempotent: files already on disk with the expected size are skipped.
Usage: python -m src.download_data [--skip-od]
"""
import argparse
import sys
from pathlib import Path

import requests

from src.config import LODES_BASE, OD_YEARS, RAC_YEARS, RAW, TIGER_BASE, WAC_YEARS


def fetch(url: str, dest: Path, retries: int = 3) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, retries + 1):
        try:
            with requests.get(url, stream=True, timeout=60) as r:
                r.raise_for_status()
                expected = int(r.headers.get("content-length", 0))
                if dest.exists() and expected and dest.stat().st_size == expected:
                    print(f"  skip  {dest.name} (already downloaded)")
                    return
                tmp = dest.with_suffix(dest.suffix + ".part")
                with open(tmp, "wb") as fh:
                    for chunk in r.iter_content(chunk_size=1 << 20):
                        fh.write(chunk)
                tmp.rename(dest)
                print(f"  saved {dest.name} ({dest.stat().st_size / 1e6:.1f} MB)")
                return
        except requests.RequestException as exc:
            print(f"  retry {attempt}/{retries} {url}: {exc}", file=sys.stderr)
    raise RuntimeError(f"failed to download {url}")


def main(skip_od: bool = False) -> None:
    print("Geography crosswalk + TIGER boundaries")
    fetch(f"{LODES_BASE}/tx_xwalk.csv.gz", RAW / "tx_xwalk.csv.gz")
    fetch(f"{TIGER_BASE}/cb_2023_48_tract_500k.zip", RAW / "geo" / "cb_2023_48_tract_500k.zip")
    fetch(f"{TIGER_BASE}/cb_2023_us_county_500k.zip", RAW / "geo" / "cb_2023_us_county_500k.zip")
    print("WAC (jobs by workplace)")
    for y in WAC_YEARS:
        fetch(f"{LODES_BASE}/wac/tx_wac_S000_JT00_{y}.csv.gz", RAW / "wac" / f"tx_wac_S000_JT00_{y}.csv.gz")
    print("RAC (workers by residence)")
    for y in RAC_YEARS:
        fetch(f"{LODES_BASE}/rac/tx_rac_S000_JT00_{y}.csv.gz", RAW / "rac" / f"tx_rac_S000_JT00_{y}.csv.gz")
    if not skip_od:
        print("OD (home-work commute flows)")
        for y in OD_YEARS:
            fetch(f"{LODES_BASE}/od/tx_od_main_JT00_{y}.csv.gz", RAW / "od" / f"tx_od_main_JT00_{y}.csv.gz")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-od", action="store_true")
    main(ap.parse_args().skip_od)
