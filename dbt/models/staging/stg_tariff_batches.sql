with src as (
    select
        {{ to_text('requirement_id') }}         as requirement_id,
        cast({{ to_text('effective_date') }} as date) as effective_date,
        {{ to_numeric('official_fx_rate') }}    as official_fx_rate,
        {{ to_int('cut_number') }}              as cut_number,
        {{ to_text('_source_file') }}           as source_file
    from {{ source('raw', 'tariff_batches') }}
)

select
    *,
    {{ dbt.date_trunc('month', 'effective_date') }} as tariff_month,
    row_number() over (order by effective_date, requirement_id) as batch_seq
from src
