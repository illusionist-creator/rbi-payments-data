-- Every published spelling mapped to one standard bank name.

with published as (
    select distinct bank_name_published
    from {{ ref('stg_rbi__bank_month') }}
),

normalised as (
    select
        bank_name_published,
        {{ normalise_bank_name('bank_name_published') }} as bank_name_normalised
    from published
)

select
    n.bank_name_published,
    n.bank_name_normalised,
    coalesce(a.bank_name_std, n.bank_name_normalised) as bank_name_std,
    a.alias is not null                                as is_renamed
from normalised as n
left join {{ ref('bank_name_aliases') }} as a
    on a.alias = n.bank_name_normalised
