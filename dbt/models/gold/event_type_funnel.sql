{{ config(
    materialized='table',
    schema='gold',
    tags=['gold', 'funnel', 'events']
) }}

-- Gold: event funnel per day (count + revenue per event type)
select
    event_date,
    event_type,
    count(distinct user_id)      as unique_users,
    count(*)                     as total_events,
    sum(amount)                  as total_amount,
    avg(amount)                  as avg_amount
from {{ ref('events_cleaned') }}
group by 1, 2
