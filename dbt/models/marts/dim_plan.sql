with events as (
    select * from {{ ref('int_tariff_events') }}
),

latest as (
    select
        *,
        row_number() over (partition by cbs_code order by batch_seq desc) as rn
    from events
)

select
    l.cbs_code,
    l.plan_name,
    l.business_line,
    l.billing_mode,
    l.product,
    l.product_type,
    l.price_usd           as current_price_usd,
    l.price_local_ex_vat  as current_price_local,
    l.effective_date      as last_adjusted_on,
    agg.first_seen_on,
    agg.adjustments_logged
from latest l
inner join (
    select cbs_code, min(effective_date) as first_seen_on, count(*) as adjustments_logged
    from events
    group by cbs_code
) agg on agg.cbs_code = l.cbs_code
where l.rn = 1
