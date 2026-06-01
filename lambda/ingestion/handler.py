"""
Lambda ingestion handler.

Pulls records from a source (e.g., S3 drop, REST API, Kinesis) and writes
raw Iceberg tables into the Bronze (raw) S3 bucket.

Glue Catalog is the Iceberg REST catalog. Tables are v3 format (time travel,
hidden partitioning, row-level deletes).
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List

import boto3
import pyarrow as pa
from pyiceberg.catalog import load_catalog
from pyiceberg.schema import Schema
from pyiceberg.types import (
    DoubleType,
    LongType,
    NestedField,
    StringType,
    TimestampType,
)

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
logging.basicConfig(level=LOG_LEVEL)
log = logging.getLogger("ingestion")

ENVIRONMENT = os.environ["ENVIRONMENT"]
RAW_BUCKET = os.environ["RAW_BUCKET"]
TABLE_PREFIX = os.environ.get("TABLE_PREFIX", "raw")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")


# --- Catalog (Glue Iceberg REST) ---

def get_catalog():
    """Load Glue as the Iceberg catalog. Local dev can override with PYICEBERG_CATALOG_URI."""
    return load_catalog(
        "glue",
        **{
            "type": "glue",
            "region": AWS_REGION,
            "warehouse": f"s3://{RAW_BUCKET}/",
        },
    )


# --- Source adapters (drop-in for any backend) ---

def fetch_from_s3_drop(s3_key: str) -> List[Dict[str, Any]]:
    """Read a JSON/CSV drop from S3. Replace with your own source."""
    s3 = boto3.client("s3", region_name=AWS_REGION)
    obj = s3.get_object(Bucket=RAW_BUCKET, Key=s3_key)
    body = obj["Body"].read().decode("utf-8")
    return json.loads(body) if s3_key.endswith(".json") else []


def fetch_from_api(endpoint: str, params: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    """Stub: pull from an HTTP source. Plug requests/aiohttp here."""
    return []


def fetch_from_kinesis(stream: str, shard_id: str) -> List[Dict[str, Any]]:
    """Stub: pull records from Kinesis."""
    return []


# --- Arrow + Iceberg writers ---

EVENT_SCHEMA = Schema(
    NestedField(1, "event_id", StringType(), required=True),
    NestedField(2, "user_id", StringType(), required=False),
    NestedField(3, "event_type", StringType(), required=False),
    NestedField(4, "amount", DoubleType(), required=False),
    NestedField(5, "ingested_at", TimestampType(), required=True),
    NestedField(6, "source", StringType(), required=False),
    NestedField(7, "raw_payload", StringType(), required=False),
)


def to_arrow_table(records: Iterable[Dict[str, Any]]) -> pa.Table:
    rows = []
    now = datetime.now(timezone.utc)
    for r in records:
        rows.append(
            {
                "event_id": r.get("event_id") or str(uuid.uuid4()),
                "user_id": r.get("user_id"),
                "event_type": r.get("event_type"),
                "amount": float(r.get("amount", 0.0)) if r.get("amount") is not None else None,
                "ingested_at": r.get("ingested_at") or now,
                "source": r.get("source") or "unknown",
                "raw_payload": json.dumps(r, default=str),
            }
        )

    if not rows:
        rows = [{
            "event_id": "0",
            "user_id": None,
            "event_type": None,
            "amount": None,
            "ingested_at": now,
            "source": "noop",
            "raw_payload": "{}",
        }]

    return pa.Table.from_pylist(rows, schema=EVENT_SCHEMA.as_arrow())


def ensure_table(catalog, namespace: str, table_name: str) -> Any:
    identifier = f"{namespace}.{table_name}"
    if not catalog.table_exists(identifier):
        log.info("Creating Iceberg table %s", identifier)
        return catalog.create_table(
            identifier=identifier,
            schema=EVENT_SCHEMA,
            properties={
                "format-version": "3",
                "write.format.default": "parquet",
                "write.metadata.compression-codec": "zstd",
            },
        )
    return catalog.load_table(identifier)


def write_to_iceberg(records: List[Dict[str, Any]], table_name: str) -> Dict[str, Any]:
    catalog = get_catalog()
    namespace = f"{TABLE_PREFIX}_{ENVIRONMENT}"
    if not catalog.namespace_exists(namespace):
        catalog.create_namespace(namespace)

    table = ensure_table(catalog, namespace, table_name)
    arrow_table = to_arrow_table(records)
    table.append(arrow_table)
    return {
        "table": f"{namespace}.{table_name}",
        "rows_written": len(records),
        "iceberg_format_version": "3",
    }


# --- Lambda entrypoint ---

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Routes based on the event source.

    Trigger variants:
      - Scheduled: event["source"] = "schedule", no body → use poll config
      - S3 drop: event["Records"] = S3 notification list
      - API: event["source"] = "api", event["endpoint"] = "..."
    """
    log.info("Ingestion start: env=%s source=%s", ENVIRONMENT, json.dumps({k: v for k, v in event.items() if k != "Records"}))

    # S3-triggered
    if "Records" in event:
        out = []
        for record in event["Records"]:
            if record.get("eventSource") == "aws:s3":
                key = record["s3"]["object"]["key"]
                records = fetch_from_s3_drop(key)
                if records:
                    out.append(write_to_iceberg(records, table_name=key.split("/")[0].replace(".json", "").replace(".", "_")))
        return {"statusCode": 200, "body": json.dumps(out, default=str)}

    # Scheduled
    if event.get("source") == "schedule":
        out = []
        for table in event.get("tables", []):
            records = fetch_from_api(table["endpoint"], table.get("params", {}))
            if records:
                out.append(write_to_iceberg(records, table_name=table["name"]))
        return {"statusCode": 200, "body": json.dumps(out, default=str)}

    # Manual / test
    table_name = event.get("table", "demo_events")
    records = event.get("records", [])
    if not records:
        records = [
            {"event_id": "demo-1", "user_id": "u1", "event_type": "click", "amount": 0.0, "source": "test"},
        ]
    out = write_to_iceberg(records, table_name=table_name)
    return {"statusCode": 200, "body": json.dumps(out, default=str)}
