{#- One staging shape for every price sheet of the log (the four Pentaho
    transformations of the thesis collapse into this macro). -#}
{% macro stage_plan_sheet(source_table, business_line, billing_mode) %}
select
    {{ to_text('requirement_id') }}                    as requirement_id,
    '{{ source_table }}'                               as source_sheet,
    '{{ business_line }}'                              as business_line,
    '{{ billing_mode }}'                               as billing_mode,
    {{ to_text('cbs_code') }}                          as cbs_code,
    {{ to_text('bo_code') }}                           as bo_code,
    {{ to_text('platform_code') }}                     as platform_code,
    {{ to_text('plan_name') }}                         as plan_name,
    {{ to_text('product') }}                           as product,
    {{ to_text('product_type') }}                      as product_type,
    {{ to_numeric('price_usd') }}                      as price_usd,
    {{ to_numeric('price_local_ex_vat') }}             as price_local_ex_vat,
    {{ to_text('_source_file') }}                      as source_file,
    {{ to_int('_row_number') }}                        as source_row
from {{ source('raw', source_table) }}
{% endmacro %}
