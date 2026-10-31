-- Plans that appeared in the previous price log but are missing from the
-- current one: the adjustment was never certified for them.
with events as (
    select requirement_id, batch_seq, cbs_code, plan_name, business_line, billing_mode,
           price_local_ex_vat
    from {{ ref('int_tariff_events') }}
),

batches as (
    select requirement_id, batch_seq, effective_date, official_fx_rate
    from {{ ref('stg_tariff_batches') }}
)

select
    cur.requirement_id,
    cur.effective_date,
    cur.official_fx_rate,
    prev.cbs_code,
    prev.plan_name,
    prev.business_line,
    prev.billing_mode,
    prev.requirement_id       as last_seen_in_requirement,
    prev.price_local_ex_vat   as last_logged_price_local
from batches cur
inner join events prev
    on prev.batch_seq = cur.batch_seq - 1
left join events now_
    on now_.batch_seq = cur.batch_seq
   and now_.cbs_code = prev.cbs_code
where now_.cbs_code is null
