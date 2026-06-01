{{ config(
    materialized='table',
    schema='gold',
    tags=['gold', 'revenue', 'categorical']
) }}

-- Gold: revenue broken down by event category
with events as (
    select e.*, c.event_category
    from {{ ref('events_cleaned') }} e
    join {{ ref('event_categorizer') }} c on e.event_type = c.event_type
)
select
    event_date,
    event_category,
    count(distinct user_id)    as unique_users,
    count(*)                  as event_count,
    sum(amount)               as gross_revenue,
    avg(amount)               as avg_amount
from events
group by 1, 2
