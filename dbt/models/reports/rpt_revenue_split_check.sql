-- Each bundle's components (voice / sms / data) must add up to 100 % and to
-- the bundle's local price.
with split as (
    select
        requirement_id,
        plan_cbs_code,
        max(plan_name)               as plan_name,
        count(*)                     as components,
        sum(split_pct)               as total_pct,
        sum(component_amount_local)  as total_amount_local
    from {{ ref('stg_revenue_split') }}
    group by requirement_id, plan_cbs_code
)

select
    s.*,
    e.price_local_ex_vat                                  as plan_price_local,
    abs(s.total_pct - 100) <= {{ var('split_tolerance_pct') }} as pct_ok,
    e.price_local_ex_vat is not null
        and abs(s.total_amount_local - e.price_local_ex_vat) <= 0.05 * s.components
                                                          as amount_ok
from split s
left join {{ ref('int_tariff_events') }} e
    on e.requirement_id = s.requirement_id
   and e.cbs_code = s.plan_cbs_code
