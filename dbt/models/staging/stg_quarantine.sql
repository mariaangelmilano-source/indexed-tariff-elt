select
    {{ to_text('table_name') }}   as table_name,
    {{ to_text('source_file') }}  as source_file,
    {{ to_int('row_number') }}    as source_row,
    {{ to_text('reason') }}       as reason,
    {{ to_text('raw_record') }}   as raw_record
from {{ source('raw', 'quarantine') }}
