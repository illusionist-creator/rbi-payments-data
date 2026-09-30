{# Compares a model with a CSV written by the pandas pipeline, row by row on `key`.
   Returns every row missing from either side, and every row where a column differs: text and dates
   exactly, numbers beyond a relative tolerance of 1e-9 (the two engines print floats differently). #}
{% macro assert_same_rows(model, csv_file, key, text_cols, date_cols=[]) %}
{%- set cols = adapter.get_columns_in_relation(model) | map(attribute='name') | list %}
{%- set path = var('processed_dir') ~ '/' ~ csv_file %}

with dbt_side as (
    select {% for c in cols %}{{ normalise_for_compare(c, text_cols, date_cols) }}{{ ", " if not loop.last }}{% endfor %}
    from {{ model }}
),

pandas_side as (
    select {% for c in cols %}{{ normalise_for_compare(c, text_cols, date_cols) }}{{ ", " if not loop.last }}{% endfor %}
    from read_csv('{{ path }}', header = true, sample_size = -1, all_varchar = true)
),

joined as (
    select
        {% for k in key %}coalesce(d.{{ k }}, p.{{ k }}) as {{ k }}, {% endfor %}
        d.{{ key[0] }} is null as missing_in_dbt,
        p.{{ key[0] }} is null as missing_in_pandas,
        list_filter([
            {%- for c in cols if c not in key %}
            {%- if c in text_cols or c in date_cols %}
            case when d.{{ c }} is distinct from p.{{ c }} then '{{ c }}' end
            {%- else %}
            case when (d.{{ c }} is null) <> (p.{{ c }} is null)
                   or abs(d.{{ c }} - p.{{ c }}) > 1e-9 * greatest(1.0, abs(p.{{ c }})) then '{{ c }}' end
            {%- endif %}{{ "," if not loop.last }}
            {%- endfor %}
        ], x -> x is not null) as differing_columns
    from dbt_side as d
    full outer join pandas_side as p
        on {% for k in key %}d.{{ k }} = p.{{ k }}{{ " and " if not loop.last }}{% endfor %}
)

select *
from joined
where missing_in_dbt or missing_in_pandas or len(differing_columns) > 0
{% endmacro %}


{% macro normalise_for_compare(c, text_cols, date_cols) %}
    {%- if c in text_cols -%}
        cast({{ c }} as varchar) as {{ c }}
    {%- elif c in date_cols -%}
        cast(cast({{ c }} as date) as varchar) as {{ c }}
    {%- else -%}
        try_cast({{ c }} as double) as {{ c }}
    {%- endif -%}
{% endmacro %}
