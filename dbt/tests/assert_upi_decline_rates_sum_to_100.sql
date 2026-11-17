-- For every remitter bank, approved + business-declined + technically-declined must be 100% of its
-- transactions, within half a point of rounding. Rows where NPCI left a rate blank are skipped.

select period, bank_name, approved_pct, business_decline_pct, technical_decline_pct,
       approved_pct + business_decline_pct + technical_decline_pct as total_pct
from {{ ref('stg_npci__upi_remitter_banks') }}
where not isnan(approved_pct + business_decline_pct + technical_decline_pct)
  and abs(approved_pct + business_decline_pct + technical_decline_pct - 100) > 0.5
