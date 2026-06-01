{{ config(
    materialized='table',
    schema='silver',
    tags=['silver', 'events']
) }}

-- Silver: business-cleaned events, partitioned by event_date (Iceberg prod)
with stg as (
    select * from {{ ref('stg_events') }}
)

select
    event_id,
    user_id,
    event_type,
    amount,
    ingested_at,
    source,
    raw_payload,
    cast(ingested_at as date) as event_date
from stg
where event_id is not null
  and user_id is not null
