-- One row per plan per tariff adjustment, enriched with the batch
-- "constants" (requirement, effective date, official FX rate, cut) and the
-- price the plan should have after conversion.
with prices as (
    select * from {{ ref('int_plan_prices') }}
),

batches as (
    select * from {{ ref('stg_tariff_batches') }}
)

select
    p.requirement_id,
    b.batch_seq,
    b.effective_date,
    b.tariff_month,
    b.cut_number,
    b.official_fx_rate,
    p.cbs_code,
    p.plan_name,
    p.business_line,
    p.billing_mode,
    p.source_sheet,
    p.product,
    p.product_type,
    p.price_usd,
    p.price_local_ex_vat,
    round(p.price_usd * b.official_fx_rate, 2)                         as expected_price_local,
    p.price_local_ex_vat - round(p.price_usd * b.official_fx_rate, 2)  as deviation_local,
    p.lines_in_log,
    p.source_file,
    p.source_row
from prices p
inner join batches b
    on p.requirement_id = b.requirement_id
