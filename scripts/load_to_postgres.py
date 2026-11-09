"""Step 2: load the CSV files from data/ into PostgreSQL (schemas raw and legacy).

Runs anywhere, CI included. Safe to rerun: every table is dropped and recreated, in one transaction.
The password is read from the PGPASSWORD environment variable, never from the repository.
Run from the repository root: python scripts/load_to_postgres.py
"""
import csv
from pathlib import Path

import psycopg2

from tables import PG_TYPES, TABLES, columns, snake

DATA = Path(__file__).resolve().parent.parent / "extracts"
END_OF_TIME = "9999-12-31 23:59:59.999999"


def main():
    with open(DATA / "row_counts.csv", encoding="utf-8") as f:
        expected = {r["table"]: int(r["rows"]) for r in csv.DictReader(f)}

    conn = psycopg2.connect(host="localhost", port=5433, dbname="legacylift", user="legacylift")
    with conn, conn.cursor() as cur:
        for schema in sorted({t[2] for t in TABLES}):
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")

        for _, _, schema, name, spec in TABLES:
            ddl = ", ".join(f"{snake(c)} {PG_TYPES[k]}" for c, k in columns(spec))
            cur.execute(f"DROP TABLE IF EXISTS {schema}.{name}")
            cur.execute(f"CREATE TABLE {schema}.{name} ({ddl})")
            with open(DATA / schema / f"{name}.csv", encoding="utf-8") as f:
                cur.copy_expert(f"COPY {schema}.{name} FROM STDIN WITH (FORMAT csv, HEADER true, NULL '\\N')", f)

            cur.execute(f"SELECT count(*) FROM {schema}.{name}")
            n = cur.fetchone()[0]
            want = expected[f"{schema}.{name}"]
            assert n == want, f"{schema}.{name}: {n} rows loaded, {want} extracted"
            print(f"{schema}.{name}: {n} rows")

        # The end-of-time value must have survived the trip unchanged (finding F3).
        cur.execute(f"SELECT count(*) FROM legacy.dim_supplier WHERE valid_to = '{END_OF_TIME}'")
        assert cur.fetchone()[0] > 0, f"no row with valid_to = {END_OF_TIME} in legacy.dim_supplier"
    conn.close()


if __name__ == "__main__":
    main()
