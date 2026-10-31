{{ config(severity='warn') }}
select * from {{ ref('rpt_revenue_split_check') }} where not (pct_ok and amount_ok)
