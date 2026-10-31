-- Price history per plan (type-2 style): each adjustment is valid until the
-- day before the next one. This is the "dynamic price inventory" the thesis
-- set out to build, queryable by code, name, billing mode and period.
with events as (
    select * from {{ ref('int_tariff_events') }}
),

windowed as (
    select
        *,
        lag(price_local_ex_vat) over (partition by cbs_code order by batch_seq) as previous_price_local,
        lag(price_usd)          over (partition by cbs_code order by batch_seq) as previous_price_usd,
        lead(effective_date)    over (partition by cbs_code order by batch_seq) as next_effective_date
    from events
)

select
    cbs_code || '-' || requirement_id                  as tariff_version_id,
    cbs_code,
    plan_name,
    business_line,
    billing_mode,
    requirement_id,
    cut_number,
    tariff_month,
    effective_date                                      as valid_from,
    case when next_effective_date is not null
         then cast({{ dbt.dateadd('day', -1, 'next_effective_date') }} as date)
    end                                                 as valid_to,
    next_effective_date is null                         as is_current,
    official_fx_rate,
    price_usd,
    price_local_ex_vat,
    previous_price_local,
    case when previous_price_local > 0
         then round((price_local_ex_vat - previous_price_local) / previous_price_local * 100, 2)
    end                                                 as pct_change_local,
    coalesce(price_usd <> previous_price_usd, false)    as usd_list_price_changed
from windowed
