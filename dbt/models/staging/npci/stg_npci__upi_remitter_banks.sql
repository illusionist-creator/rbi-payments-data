-- How each remitter bank's UPI payments ended: approved, declined for a business reason (wrong PIN,
-- insufficient funds) or declined for a technical one (the bank's systems). Rates are percentages.

select
    period,
    trim(upi_remitter_banks)                 as bank_name,
    cast(total_volume_in_mn as double)       as volume_mn,
    cast(approved_percent as double)         as approved_pct,
    cast(bd_percent as double)               as business_decline_pct,
    cast(td_percent as double)               as technical_decline_pct
from {{ source('npci', 'upi_remitter_banks') }}
where nullif(trim(upi_remitter_banks), '') is not null
