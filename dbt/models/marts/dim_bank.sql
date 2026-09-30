-- One row per standard bank: its type, how many spellings RBI has used, and when it was reported.

select
    n.bank_name_std,
    t.bank_type,
    t.bank_type_source,
    count(distinct n.bank_name_published) as published_spellings,
    bool_or(n.is_renamed)                 as has_renamed_spelling,
    min(b.start_date)                     as first_reported,
    max(b.start_date)                     as last_reported
from {{ ref('int_bank_names') }} as n
join {{ ref('stg_rbi__bank_month') }} as b using (bank_name_published)
left join {{ ref('int_bank_types') }} as t using (bank_name_std)
group by all
