{{ config(
    materialized='view',
    schema='staging',
    tags=['staging', 'events']
) }}

-- Staging: typed, deduplicated events
with source as (
    select * from {{ ref('raw_events') }}
),

deduped as (
    select
        *,
        row_number() over (partition by event_id order by ingested_at desc) as rn
    from source
    where event_id is not null
)

select
    cast(event_id as varchar)        as event_id,
    cast(user_id as varchar)         as user_id,
    cast(event_type as varchar)      as event_type,
    cast(amount as double)           as amount,
    cast(ingested_at as timestamp)   as ingested_at,
    cast(source as varchar)          as source,
    raw_payload
from deduped
where rn = 1
