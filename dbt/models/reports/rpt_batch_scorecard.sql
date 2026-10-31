-- One line per price log: what a revenue-assurance analyst needs to sign off
-- (or reject) an adjustment.
with b as (select * from {{ ref('stg_tariff_batches') }}),

alignment as (
    select
        requirement_id,
        count(*)                                                     as plans_logged,
        sum(case when alignment_status = 'aligned' then 1 else 0 end)      as plans_aligned,
        sum(case when alignment_status = 'stale_price' then 1 else 0 end)  as plans_stale,
        sum(case when alignment_status = 'misconverted' then 1 else 0 end) as plans_misconverted
    from {{ ref('fct_fx_alignment') }}
    group by requirement_id
),

dupes as (
    select requirement_id, sum(lines_in_log - 1) as duplicate_lines
    from {{ ref('int_tariff_events') }}
    group by requirement_id
),

missed as (
    select requirement_id, count(*) as plans_missing
    from {{ ref('rpt_missed_adjustments') }}
    group by requirement_id
),

split as (
    select requirement_id,
           sum(case when pct_ok and amount_ok then 0 else 1 end) as split_errors
    from {{ ref('rpt_revenue_split_check') }}
    group by requirement_id
),

quarantined as (
    select source_file, count(*) as rows_quarantined
    from {{ ref('stg_quarantine') }}
    group by source_file
)

select
    b.requirement_id,
    b.batch_seq,
    b.effective_date,
    b.cut_number,
    b.official_fx_rate,
    coalesce(a.plans_logged, 0)        as plans_logged,
    coalesce(a.plans_aligned, 0)       as plans_aligned,
    coalesce(a.plans_stale, 0)         as plans_stale,
    coalesce(a.plans_misconverted, 0)  as plans_misconverted,
    coalesce(m.plans_missing, 0)       as plans_missing,
    coalesce(s.split_errors, 0)        as split_errors,
    coalesce(d.duplicate_lines, 0)     as duplicate_lines,
    coalesce(q.rows_quarantined, 0)    as rows_quarantined,
    case when coalesce(a.plans_stale, 0) + coalesce(a.plans_misconverted, 0)
              + coalesce(m.plans_missing, 0) + coalesce(s.split_errors, 0)
              + coalesce(q.rows_quarantined, 0) = 0
         then 'certified' else 'needs_review' end as certification_status
from b
left join alignment a   on a.requirement_id = b.requirement_id
left join dupes d       on d.requirement_id = b.requirement_id
left join missed m      on m.requirement_id = b.requirement_id
left join split s       on s.requirement_id = b.requirement_id
left join quarantined q on q.source_file = b.source_file
