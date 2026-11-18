-- NPCI switched AutoPay volumes from raw counts to millions in Dec 2024 and staging rescales by the month's
-- total. If NPCI changes unit again, a month-on-month jump of 20x or more shows up here and stops the build.

with monthly as (
    select stage, period, sum(volume_mn) as volume_mn
    from {{ ref('stg_npci__autopay_banks') }}
    group by stage, period
),

paired as (
    select *, lag(volume_mn) over (partition by stage order by period) as prev_mn
    from monthly
)

select stage, period, volume_mn, prev_mn
from paired
where prev_mn > 0 and (volume_mn / prev_mn > 20 or volume_mn / prev_mn < 0.05)
