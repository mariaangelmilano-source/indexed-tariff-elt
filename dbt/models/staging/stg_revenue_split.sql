select
    {{ to_text('requirement_id') }}           as requirement_id,
    {{ to_text('plan_cbs_code') }}            as plan_cbs_code,
    {{ to_text('plan_name') }}                as plan_name,
    {{ to_text('component_code') }}           as component_code,
    {{ to_text('component_name') }}           as component_name,
    {{ to_numeric('split_pct') }}             as split_pct,
    {{ to_numeric('component_amount_local') }} as component_amount_local,
    {{ to_text('_source_file') }}             as source_file,
    {{ to_int('_row_number') }}               as source_row
from {{ source('raw', 'revenue_split') }}
