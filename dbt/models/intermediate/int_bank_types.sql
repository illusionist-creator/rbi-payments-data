-- One bank type per standard bank. RBI only started printing group headings in mid-2020, so the
-- latest heading seen wins, and banks that closed before then fall back to seed bank_type_manual.

with headings as (
    select
        n.bank_name_std,
        b.period,
        case
            when regexp_matches(lower(b.bank_group_published), 'nationalis|nationaliz|state bank|public sector')
                then 'Public Sector Banks'
            when lower(b.bank_group_published) like '%private%'       then 'Private Sector Banks'
            when lower(b.bank_group_published) like '%foreign%'       then 'Foreign Banks'
            when lower(b.bank_group_published) like '%payment%'       then 'Payment Banks'
            when lower(b.bank_group_published) like '%small finance%' then 'Small Finance Banks'
        end as bank_type
    from {{ ref('stg_rbi__bank_month') }} as b
    join {{ ref('int_bank_names') }} as n using (bank_name_published)
    where b.bank_group_published is not null
),

latest_heading as (
    select bank_name_std, arg_max(bank_type, period) as bank_type
    from headings
    where bank_type is not null
    group by bank_name_std
),

banks as (
    select distinct bank_name_std from {{ ref('int_bank_names') }}
)

select
    b.bank_name_std,
    coalesce(h.bank_type, m.bank_type) as bank_type,
    case when h.bank_type is not null then 'rbi_heading'
         when m.bank_type is not null then 'manual_seed' end as bank_type_source
from banks as b
left join latest_heading as h using (bank_name_std)
left join {{ ref('bank_type_manual') }} as m using (bank_name_std)
