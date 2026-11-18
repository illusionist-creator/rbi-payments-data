-- NPCI's shared ATM network (NFS): withdrawals and other ATM transactions made with one bank's card at
-- another bank's ATM, per card-issuing bank per month. Rates are percentages; volumes in millions.

select
    period,
    trim(issuer_bank_name)                   as bank_name,
    cast(total_volume_mn as double)          as volume_mn,
    cast(approved_percent as double)         as approved_pct,
    cast(bd_percent as double)               as business_decline_pct,
    cast(td_percent as double)               as technical_decline_pct
from {{ source('npci', 'nfs_atm_declines') }}
where nullif(trim(issuer_bank_name), '') is not null
