-- UPI AutoPay per remitter bank: mandate executions (recurring debits) and registrations, one row per
-- stage, bank and month. NPCI published raw counts until Nov 2024 and millions from Dec 2024; a month whose
-- total is over 100,000 is read as raw counts. IndusInd appears twice in two months, so rows are merged.

with unioned as (
    select 'execution' as stage, * from {{ source('npci', 'upi_autopay_exec') }}
    union all by name
    select 'registration' as stage, * from {{ source('npci', 'upi_autopay_reg') }}
),

typed as (
    select
        stage,
        period,
        trim(remitter_bank)                    as bank_name,
        cast(total_volume as double)           as volume_raw,
        cast(approved_percent as double)       as approved_pct,
        cast(bd_percent as double)             as business_decline_pct,
        cast(td_percent as double)             as technical_decline_pct
    from unioned
    where nullif(trim(remitter_bank), '') is not null
),

scaled as (
    select *,
        case when sum(volume_raw) over (partition by stage, period) > 100000
             then volume_raw / 1e6 else volume_raw end as volume_mn
    from typed
)

select
    stage,
    period,
    bank_name,
    sum(volume_mn)                                                        as volume_mn,
    sum(approved_pct * volume_mn) / nullif(sum(volume_mn), 0)             as approved_pct,
    sum(business_decline_pct * volume_mn) / nullif(sum(volume_mn), 0)     as business_decline_pct,
    sum(technical_decline_pct * volume_mn) / nullif(sum(volume_mn), 0)    as technical_decline_pct,
    count(*)                                                              as rows_merged
from scaled
group by stage, period, bank_name
