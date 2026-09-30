-- RBI's printed Total row, one per release, on the same footing as stg_rbi__bank_month.

select
    r.period,
    cast(r.period || '-01' as date)    as start_date,
    cast(r.atmid as integer)           as atmid,
    r.layout,
    r.value_unit_published,
    {{ published_metrics('r.') }}
from {{ source('rbi', 'national_totals_raw') }} as r
left join {{ ref('value_units') }} as u using (value_unit_published)
