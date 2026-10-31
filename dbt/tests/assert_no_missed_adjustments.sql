{{ config(severity='warn') }}
select * from {{ ref('rpt_missed_adjustments') }}
