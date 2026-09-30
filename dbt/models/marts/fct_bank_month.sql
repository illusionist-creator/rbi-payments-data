-- Every metric RBI has published, one row per bank per month, with standard bank names and types
-- and the series that stay comparable across layout changes. Replaces bank_month_all_metrics.csv.

select
    b.period,
    b.start_date,
    b.atmid,
    b.layout,
    b.value_unit_published,
    t.bank_type,
    b.bank_group_published,
    n.bank_name_std,
    b.bank_name_published,
    {{ continuity_metrics() }},
    b.* exclude (period, start_date, atmid, layout, value_unit_published,
                 bank_group_published, bank_name_published)
from {{ ref('stg_rbi__bank_month') }} as b
join {{ ref('int_bank_names') }} as n using (bank_name_published)
left join {{ ref('int_bank_types') }} as t using (bank_name_std)
