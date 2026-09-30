{# Casts every published metric to double and adds a Rs-million copy of each value column.
   Expects the relation to be joined to seed value_units as `u`. #}
{% macro published_metrics(prefix='') %}
    {%- for c in var('count_cols') %}
    cast({{ prefix }}{{ c }} as double) as {{ c }},
    {%- endfor %}
    {%- for c in var('value_cols') %}
    cast({{ prefix }}{{ c }} as double) as {{ c }},
    cast({{ prefix }}{{ c }} as double) * u.to_million as {{ c }}_mn{{ "," if not loop.last }}
    {%- endfor %}
{% endmacro %}


{# Row-wise sum that stays null when every input is null (pandas sum(min_count=1)). #}
{% macro sum_present(cols) %}
    case when {{ cols | join(' is null and ') }} is null then null
         else {% for c in cols %}coalesce({{ c }}, 0){{ " + " if not loop.last }}{% endfor %} end
{% endmacro %}


{# Series that stay comparable across RBI's three layouts. From Mar 2022 (C26) RBI reports one PoS
   count and splits card payments into PoS / online / other, so payments = the sum of the three. #}
{% macro continuity_metrics() %}
    {{ sum_present(['atm_onsite', 'atm_offsite']) }}                   as atm_total,
    case when layout = 'C26' then pos
         else {{ sum_present(['pos_online', 'pos_offline']) }} end         as pos_terminals,
    {%- for card in ['cc', 'dc'] %}
    case when layout = 'C26' then {{ sum_present([card ~ '_pos_vol', card ~ '_ecom_vol', card ~ '_other_vol']) }}
         else {{ card }}_pos_vol end                                     as {{ card }}_payments_vol,
    case when layout = 'C26' then {{ sum_present([card ~ '_pos_val_mn', card ~ '_ecom_val_mn', card ~ '_other_val_mn']) }}
         else {{ card }}_pos_val_mn end                                  as {{ card }}_payments_val_mn{{ "," if not loop.last }}
    {%- endfor %}
{% endmacro %}


{# The same bank has been spelt ~190 ways since 2011. Normalise case, punctuation, "The" and
   "Limited" here; genuine renames are handled by seed bank_name_aliases. #}
{% macro normalise_bank_name(col) %}
    regexp_replace(
        regexp_replace(
            trim(regexp_replace(
                regexp_replace(replace(upper({{ col }}), '&', ' AND '), '[.,''’]', '', 'g'),
                '\s+', ' ', 'g')),
            '^THE\s+', ''),
        '\bLIMITED\b', 'LTD', 'g')
{% endmacro %}
