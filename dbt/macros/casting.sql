{#- Raw tables are all text. These helpers cast safely and identically on
    DuckDB and BigQuery: blank strings become NULL, so a bad value shows up
    in a not_null / range test instead of breaking the load. -#}

{% macro to_numeric(col) -%}
    cast(nullif(trim({{ col }}), '') as {{ dbt.type_numeric() }})
{%- endmacro %}

{% macro to_int(col) -%}
    cast(nullif(trim({{ col }}), '') as {{ dbt.type_int() }})
{%- endmacro %}

{% macro to_text(col) -%}
    nullif(trim({{ col }}), '')
{%- endmacro %}
