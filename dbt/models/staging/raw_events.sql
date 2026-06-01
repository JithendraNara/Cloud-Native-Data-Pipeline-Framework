{{ config(
    materialized='view',
    schema='raw_dev',
    tags=['bronze', 'source']
) }}

-- Bronze: pull from the externally-seeded raw_events table.
-- In production this is the Iceberg table written by the ingestion Lambda (PyIceberg).
-- In local dev, scripts/local_seed.py populates raw_dev.raw_events from sample/events.json.
select * from raw_dev.raw_events
