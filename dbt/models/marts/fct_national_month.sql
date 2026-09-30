-- RBI's published national Total, one row per month, with the same continuity series as fct_bank_month.

select
    period,
    start_date,
    atmid,
    layout,
    value_unit_published,
    {{ continuity_metrics() }},
    * exclude (period, start_date, atmid, layout, value_unit_published)
from {{ ref('stg_rbi__national_totals') }}
