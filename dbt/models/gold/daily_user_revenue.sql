{{ config(
    materialized='table',
    schema='gold',
    tags=['gold', 'revenue', 'daily']
) }}

-- Gold: daily revenue aggregated per user, ready for BI / agents
select
    event_date,
    user_id,
    count(*)                                       as event_count,
    sum(case when amount > 0 then amount else 0 end) as gross_revenue,
    sum(amount)                                    as net_amount,
    count(distinct event_type)                     as event_type_count,
    max(ingested_at)                               as last_event_at
from {{ ref('events_cleaned') }}
group by 1, 2
