"""
Great Expectations data quality suite for the Gold layer.

Run after dbt build:
    python -m data_quality.gx_suite

Validates:
  - daily_user_revenue: gross_revenue not null, not negative
  - event_type_funnel: total_events >= 0
  - Iceberg metadata freshness (snapshot age < 24h)
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

import pyarrow as pa
import pyarrow.compute as pc

log = logging.getLogger("gx")
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

ICEBERG_NAMESPACE = os.environ.get("ICEBERG_GOLD_NAMESPACE", "gold_dev")
ATHENA_WG = os.environ.get("ATHENA_WORKGROUP", "data-pipeline-dev")
ATHENA_OUTPUT = os.environ.get("ATHENA_OUTPUT", "s3://data-pipeline-warehouse/results/")


def query_athena(sql: str) -> pa.Table:
    """Run an Athena query and return an Arrow table."""
    import awswrangler as wr

    return wr.athena.read_sql_query(
        sql,
        database=ICEBERG_NAMESPACE,
        workgroup=ATHENA_WG,
        s3_output=ATHENA_OUTPUT,
        ctas_approach=False,
    )


def validate_daily_user_revenue() -> int:
    table = query_athena(
        "SELECT event_date, user_id, gross_revenue, event_count "
        f"FROM {ICEBERG_NAMESPACE}.daily_user_revenue "
        "WHERE event_date >= current_date - interval '7' day"
    )

    failures = 0

    # 1. nullness
    null_rows = pc.sum(pc.is_null(table["gross_revenue"])).as_py()
    if null_rows > 0:
        failures += 1
        log.error("daily_user_revenue: %d null gross_revenue rows", null_rows)

    # 2. non-negative
    neg_rows = pc.sum(pc.less(table["gross_revenue"], 0)).as_py()
    if neg_rows > 0:
        failures += 1
        log.error("daily_user_revenue: %d negative gross_revenue rows", neg_rows)

    log.info("daily_user_revenue: %d rows scanned, %d failures", table.num_rows, failures)
    return failures


def validate_event_type_funnel() -> int:
    table = query_athena(
        "SELECT event_date, event_type, total_events, unique_users "
        f"FROM {ICEBERG_NAMESPACE}.event_type_funnel "
        "WHERE event_date >= current_date - interval '7' day"
    )

    failures = 0
    neg_events = pc.sum(pc.less(table["total_events"], 0)).as_py()
    if neg_events > 0:
        failures += 1
        log.error("event_type_funnel: %d negative total_events rows", neg_events)

    log.info("event_type_funnel: %d rows scanned, %d failures", table.num_rows, failures)
    return failures


def validate_freshness() -> int:
    """Check that Gold tables have been updated in the last 24h."""
    table = query_athena(
        f"SELECT * FROM {ICEBERG_NAMESPACE}.daily_user_revenue.$snapshots ORDER BY committed_at DESC LIMIT 1"
    )
    if table.num_rows == 0:
        log.error("freshness: no snapshots found")
        return 1
    last = table["committed_at"][0].as_py()
    age = datetime.now(timezone.utc) - last
    if age > timedelta(hours=24):
        log.error("freshness: latest snapshot is %s old (threshold 24h)", age)
        return 1
    log.info("freshness: latest snapshot is %s old (OK)", age)
    return 0


def main() -> int:
    log.info("=== Running Great Expectations suite ===")
    failures = 0
    failures += validate_daily_user_revenue()
    failures += validate_event_type_funnel()
    failures += validate_freshness()

    if failures:
        log.error("Suite FAILED with %d failure(s)", failures)
        return 1
    log.info("Suite PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
