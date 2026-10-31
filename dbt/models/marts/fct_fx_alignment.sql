-- Certification check: does every local price equal its USD reference times
-- the official rate of that adjustment?
--   aligned        within tolerance (rounding noise)
--   stale_price    local price was not updated although the rate moved
--   misconverted   updated, but to the wrong amount
with events as (
    select * from {{ ref('int_tariff_events') }}
),

with_prev as (
    select
        *,
        lag(price_local_ex_vat) over (partition by cbs_code order by batch_seq) as previous_price_local,
        lag(official_fx_rate)   over (partition by cbs_code order by batch_seq) as previous_fx_rate
    from events
)

select
    requirement_id,
    batch_seq,
    effective_date,
    cbs_code,
    plan_name,
    business_line,
    billing_mode,
    official_fx_rate,
    price_usd,
    price_local_ex_vat,
    expected_price_local,
    deviation_local,
    case when expected_price_local > 0
         then round(abs(deviation_local) / expected_price_local * 100, 3)
    end as deviation_pct,
    case
        when expected_price_local > 0
             and abs(deviation_local) / expected_price_local <= {{ var('fx_tolerance_pct') }}
            then 'aligned'
        when previous_price_local is not null
             and price_local_ex_vat = previous_price_local
             and official_fx_rate <> previous_fx_rate
            then 'stale_price'
        else 'misconverted'
    end as alignment_status
from with_prev
