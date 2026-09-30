-- The Rs-million values rebuilt here from seed value_units must equal the *_mn columns the parser wrote.

with parser as (
    select * from {{ source('rbi', 'bank_month_all_metrics_raw') }}
),

rebuilt as (
    select * from {{ ref('stg_rbi__bank_month') }}
)

{%- for c in var('value_cols') %}
select '{{ c }}' as metric, r.period, r.bank_name_published, r.{{ c }}_mn as rebuilt, p.{{ c }}_mn as parser
from rebuilt as r
join parser as p
    on p.period = r.period and p.bank_name_published = r.bank_name_published
where r.{{ c }}_mn is distinct from p.{{ c }}_mn
  and not (abs(r.{{ c }}_mn - p.{{ c }}_mn) <= 1e-9 * greatest(1.0, abs(p.{{ c }}_mn)))
{{ "union all" if not loop.last }}
{%- endfor %}
