"""
Local DuckDB seeder - reads the sample events JSON, ingests it via DuckDB,
then runs the dbt project against DuckDB so you can see the full pipeline work
without any AWS credentials.

Usage:
    python scripts/local_seed.py
    cd dbt && DBT_PROFILES_DIR=. dbt build --profile data_pipeline --target local
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).parent.parent
SAMPLE_PATH = ROOT / "sample" / "events.json"
DUCKDB_PATH = ROOT / "dbt" / "dbt.duckdb"


def seed_events() -> None:
    if not SAMPLE_PATH.exists():
        print(f"No sample data at {SAMPLE_PATH}. Run: python scripts/generate_sample_data.py --rows 10000")
        sys.exit(1)

    con = duckdb.connect(str(DUCKDB_PATH))
    df = pd.read_json(SAMPLE_PATH)
    df["ingested_at"] = pd.to_datetime(df["ingested_at"])

    con.execute("CREATE SCHEMA IF NOT EXISTS raw_dev")
    con.execute("DROP TABLE IF EXISTS raw_dev.raw_events")
    # Write all columns + raw_payload as JSON
    con.register("df_view", df)
    con.execute(
        "CREATE TABLE raw_dev.raw_events AS "
        "SELECT event_id, user_id, event_type, amount, ingested_at, source, "
        "       CAST(to_json(df_view) AS VARCHAR) AS raw_payload "
        "FROM df_view"
    )
    con.unregister("df_view")
    print(f"Seeded {len(df)} rows → {DUCKDB_PATH}")


def main() -> None:
    seed_events()
    print("Now run: cd dbt && DBT_PROFILES_DIR=. dbt build --profile data_pipeline --target local")


if __name__ == "__main__":
    main()
