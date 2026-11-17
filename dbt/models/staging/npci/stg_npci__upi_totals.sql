-- National UPI totals per month, P2P and P2M, in million transactions and Rs crore.

select
    period,
    cast(period || '-01' as date)          as start_date,
    cast(total_volume_mn as double)        as upi_volume_mn,
    cast(total_value_cr as double)         as upi_value_cr,
    cast(p_2_p_volume_mn as double)        as p2p_volume_mn,
    cast(p_2_p_value_cr as double)         as p2p_value_cr,
    cast(p_2_m_volume_mn as double)        as p2m_volume_mn,
    cast(p_2_m_value_cr as double)         as p2m_value_cr
from {{ source('npci', 'upi_p2p_p2m') }}
