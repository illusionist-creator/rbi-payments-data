-- NPCI's P2P and P2M series must add up to its published UPI total, in volume and value, within 0.1%.
-- Returns the months that don't.

select period, upi_volume_mn, p2p_volume_mn + p2m_volume_mn as parts_volume_mn,
       upi_value_cr, p2p_value_cr + p2m_value_cr as parts_value_cr
from {{ ref('stg_npci__upi_totals') }}
where abs(p2p_volume_mn + p2m_volume_mn - upi_volume_mn) > 0.001 * upi_volume_mn
   or abs(p2p_value_cr + p2m_value_cr - upi_value_cr) > 0.001 * upi_value_cr
