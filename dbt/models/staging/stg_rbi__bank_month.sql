-- One row per bank per release, typed, with every value also converted to Rs million.
-- The parser's own *_mn columns are dropped here and recomputed from the unit seed;
-- tests/assert_unit_conversion_matches_parser.sql checks the two agree.

select
    r.period,
    cast(r.period || '-01' as date)    as start_date,
    cast(r.atmid as integer)           as atmid,
    r.layout,
    r.value_unit_published,
    r.bank_group                       as bank_group_published,
    r.bank_name_published,
    {{ published_metrics('r.') }}
from {{ source('rbi', 'bank_month_all_metrics_raw') }} as r
left join {{ ref('value_units') }} as u using (value_unit_published)
