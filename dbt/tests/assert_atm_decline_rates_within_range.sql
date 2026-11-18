-- NFS rates leave about 1% of each bank's ATM transactions unclassified, so the three should add up to
-- between 95% and 100.5%. May 2025 is off at almost every bank (6-11% unclassified) and two single rows
-- (PNB Nov 2022, Bank of Maharashtra Mar 2023) are off too; the dashboard drops such rows, and a month whose
-- bad rows carry over a quarter of its volume. Warn, so a new case is seen without stopping the card refresh.
{{ config(severity = 'warn') }}

select period, bank_name, approved_pct + business_decline_pct + technical_decline_pct as total_pct
from {{ ref('stg_npci__atm_declines') }}
where approved_pct + business_decline_pct + technical_decline_pct < 95
   or approved_pct + business_decline_pct + technical_decline_pct > 100.5
