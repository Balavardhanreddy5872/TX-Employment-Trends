"""Execute the numbered SQL files against db/lodes.db and export each named query to outputs/tables/*.csv.

File format: blocks introduced by ``-- name: <query_name>``. Blocks whose name starts with ``setup_`` are
executed silently (DDL / table builds); all others must be a single SELECT and are exported as CSV.
Usage: python -m src.run_sql
"""
import math
import re
import sqlite3
import time

import pandas as pd

from src.clean import haversine_miles
from src.config import DB_PATH, SQL_DIR, TABLE_DIR

NAME_RE = re.compile(r"^--\s*name:\s*(\w+)\s*$", re.M)


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.create_function("power", 2, lambda x, y: None if x is None else math.pow(x, y), deterministic=True)
    con.create_function("sqrt", 1, lambda x: None if x is None else math.sqrt(x), deterministic=True)
    con.create_function("ln", 1, lambda x: None if x is None else math.log(x), deterministic=True)
    con.create_function("exp", 1, lambda x: None if x is None else math.exp(x), deterministic=True)
    con.create_function("haversine_mi", 4, lambda a, b, c, d: float(haversine_miles(a, b, c, d)), deterministic=True)
    return con


def parse_blocks(text: str) -> list[tuple[str, str]]:
    matches = list(NAME_RE.finditer(text))
    return [(m.group(1), text[m.end(): matches[i + 1].start() if i + 1 < len(matches) else len(text)].strip())
            for i, m in enumerate(matches)]


def run() -> dict[str, pd.DataFrame]:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    con, results = connect(), {}
    for f in sorted(SQL_DIR.glob("*.sql")):
        print(f.name)
        for name, sql in parse_blocks(f.read_text()):
            t0 = time.time()
            if name.startswith("setup_"):
                con.executescript(sql)
                print(f"  {name:<34} ok ({time.time() - t0:.1f}s)")
            else:
                df = pd.read_sql_query(sql, con)
                df.to_csv(TABLE_DIR / f"{name}.csv", index=False)
                results[name] = df
                print(f"  {name:<34} {len(df):>6} rows ({time.time() - t0:.1f}s)")
    con.commit()
    con.close()
    return results


if __name__ == "__main__":
    run()
