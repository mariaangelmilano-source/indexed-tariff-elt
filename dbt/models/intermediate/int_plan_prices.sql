-- All price sheets in one shape, de-duplicated per (log, plan).
-- Exact duplicate lines in the log are kept out of the history but counted,
-- so the batch scorecard can report them.
with unioned as (
    select * from {{ ref('stg_prepaid_plans') }}
    union all
    select * from {{ ref('stg_postpaid_plans') }}
    union all
    select * from {{ ref('stg_b2b_access') }}
    union all
    select * from {{ ref('stg_b2b_inbound_access') }}
),

ranked as (
    select
        *,
        row_number() over (partition by requirement_id, cbs_code order by source_row) as rn,
        count(*)     over (partition by requirement_id, cbs_code)                     as lines_in_log
    from unioned
)

select
    requirement_id, source_sheet, business_line, billing_mode, cbs_code, bo_code,
    platform_code, plan_name, product, product_type, price_usd, price_local_ex_vat,
    source_file, source_row, lines_in_log
from ranked
where rn = 1
