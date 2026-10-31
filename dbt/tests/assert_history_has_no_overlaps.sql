-- Structural rule (error): a plan cannot have two versions valid on the same day.
select a.cbs_code, a.valid_from
from {{ ref('fct_tariff_history') }} a
inner join {{ ref('fct_tariff_history') }} b
    on a.cbs_code = b.cbs_code
   and a.tariff_version_id <> b.tariff_version_id
   and b.valid_from between a.valid_from and coalesce(a.valid_to, b.valid_from)
