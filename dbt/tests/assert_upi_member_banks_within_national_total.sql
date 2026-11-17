-- If NPCI's Total row slips past the filter in stg_npci__upi_member_banks, that month's bank sum
-- roughly doubles. The top-50 table counts slightly differently from the national series (it runs up to
-- ~2% above it in Jan-Mar 2025), so this flags anything more than 25% over, not any excess at all.

with banks as (
    select period, sum(volume_mn) as banks_volume_mn
    from {{ ref('stg_npci__upi_member_banks') }}
    group by period
)

select b.period, b.banks_volume_mn, t.upi_volume_mn
from banks as b
join {{ ref('stg_npci__upi_totals') }} as t using (period)
where b.banks_volume_mn > 1.25 * t.upi_volume_mn
