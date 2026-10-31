-- Business rule (warn): every local price must equal USD price x official rate.
-- Warn rather than fail: these rows are findings for the analyst, not pipeline bugs.
{{ config(severity='warn') }}
select * from {{ ref('fct_fx_alignment') }} where alignment_status <> 'aligned'
