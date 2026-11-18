-- Approved + business-declined + technically-declined should be 100% for every AutoPay row. About 20 rows
-- (Mar 2022, Dec 2023) don't add up, and the dashboard leaves them out of its averages; warn so a new batch
-- is seen without blocking the publish.
{{ config(severity = 'warn') }}

select stage, period, bank_name, approved_pct + business_decline_pct + technical_decline_pct as total_pct
from {{ ref('stg_npci__autopay_banks') }}
where abs(approved_pct + business_decline_pct + technical_decline_pct - 100) > 1.5
