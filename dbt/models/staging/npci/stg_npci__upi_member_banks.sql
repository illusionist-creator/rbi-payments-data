-- Top-50 UPI member banks per month, without NPCI's Total row or nameless rows. NPCI does not always flag that row
-- (Oct-Dec 2025 arrived with is_total = false), so it is dropped by name as well as by flag.

select
    period,
    trim(bank_name)                 as bank_name,
    sum(cast(volume_mn as double))  as volume_mn,
    sum(cast(value_cr as double))   as value_cr,
    count(*)                        as rows_published
from {{ source('npci', 'upi_member_vol_val') }}
where nullif(trim(bank_name), '') is not null
  and coalesce(cast(is_total as boolean), false) = false
  and lower(trim(bank_name)) not in ('total', 'grand total')
group by all
