"""Step 1: read from SQL Server and write CSV files to data/. Runs only on the local machine.

Time columns are cut to 6 decimals with CONVERT(varchar(26), ..., 121): the string is truncated,
not rounded. PostgreSQL keeps 6 decimals and would round '9999-12-31 23:59:59.9999999' up to
the year 10000 (finding F3 in docs/reverse-engineering.md).
Run from the repository root: python scripts/extract_from_sqlserver.py
"""
import csv
from pathlib import Path

import pyodbc

from tables import DW, OLTP, TABLES, columns, snake

DATA = Path(__file__).resolve().parent.parent / "extracts"
NULL = r"\N"  # NULL marker, so that NULL and an empty string stay different
PHOTO_TABLES = [(OLTP, "Warehouse.StockItems"), (OLTP, "Warehouse.StockItems_Archive"), (DW, "Dimension.[Stock Item]")]


def connect(db):
    return pyodbc.connect(
        "DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;"
        f"DATABASE={db};Trusted_Connection=yes;TrustServerCertificate=yes"
    )


def select_expr(col, kind):
    q = f"[{col}]"
    if kind == "ts":
        return f"CONVERT(varchar(26), {q}, 121)"
    if kind == "date":
        return f"CONVERT(varchar(10), {q}, 23)"
    if kind == "bool":
        return f"CAST({q} AS int)"
    return q


def main():
    conns = {db: connect(db) for db in (OLTP, DW)}

    # Photo is not copied: stop if it is not empty, so nothing is lost silently.
    for db, table in PHOTO_TABLES:
        n = conns[db].cursor().execute(f"SELECT COUNT(*) FROM {table} WHERE Photo IS NOT NULL").fetchval()
        if n:
            raise SystemExit(f"{table}: {n} rows with a Photo. The script skips Photo and must be extended.")

    counts = []
    for db, table, schema, name, spec in TABLES:
        cols = columns(spec)
        select = ", ".join(select_expr(c, k) for c, k in cols)
        order = ", ".join(str(i) for i in range(1, len(cols) + 1))  # stable file, clean diffs
        cur = conns[db].cursor()
        cur.execute(f"SELECT {select} FROM {table} ORDER BY {order}")

        path = DATA / schema / f"{name}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = 0
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow([snake(c) for c, _ in cols])
            while batch := cur.fetchmany(10000):  # in blocks, never the whole table in memory
                w.writerows([NULL if v is None else v for v in r] for r in batch)
                rows += len(batch)
        counts.append((f"{schema}.{name}", rows))
        print(f"{schema}.{name}: {rows} rows")

    with open(DATA / "row_counts.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["table", "rows"])
        w.writerows(counts)


if __name__ == "__main__":
    main()
