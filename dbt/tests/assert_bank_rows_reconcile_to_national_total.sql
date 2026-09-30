-- For every month and every metric, the bank rows must add up to RBI's printed Total, within the
-- same tolerance the parser uses (0.5% or 1 unit, whichever is larger). Returns the months that don't.
-- Totals that RBI left blank are skipped, as are metrics absent from a month's layout.

{%- set metrics = var('count_cols') + var('value_cols') %}

with bank_sums as (
    select
        period,
        {%- for m in metrics %}
        sum({{ m }}) as {{ m }}{{ "," if not loop.last }}
        {%- endfor %}
    from {{ ref('fct_bank_month') }}
    group by period
),

compared as (
    {%- for m in metrics %}
    select '{{ m }}' as metric, n.period, s.{{ m }} as bank_sum, n.{{ m }} as national_total
    from {{ ref('fct_national_month') }} as n
    join bank_sums as s using (period)
    where n.{{ m }} is not null and s.{{ m }} is not null
    {{ "union all" if not loop.last }}
    {%- endfor %}
)

select *
from compared
where abs(bank_sum - national_total) > greatest(1.0, 0.005 * abs(national_total))
