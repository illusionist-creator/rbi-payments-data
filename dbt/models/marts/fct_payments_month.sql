-- RBI's card statistics and NPCI's UPI statistics on one monthly calendar. The two are published by
-- different bodies in different units; this is where they meet. Volumes in million transactions,
-- values in Rs crore, average payments in rupees.

with cards as (
    select
        period,
        cc_payments_vol / 1e6         as cc_volume_mn,
        cc_payments_val_mn / 10       as cc_value_cr,
        dc_payments_vol / 1e6         as dc_volume_mn,
        dc_payments_val_mn / 10       as dc_value_cr,
        cc_cards / 1e6                as cc_cards_mn,
        dc_cards / 1e6                as dc_cards_mn
    from {{ ref('fct_national_month') }}
),

upi as (
    select * exclude (start_date) from {{ ref('stg_npci__upi_totals') }}
),

joined as (
    select
        coalesce(c.period, u.period) as period,
        c.* exclude (period),
        u.* exclude (period)
    from cards as c
    full outer join upi as u using (period)
)

select
    period,
    cast(period || '-01' as date)                                      as start_date,
    cc_volume_mn is not null                                           as has_card_data,
    upi_volume_mn is not null                                          as has_upi_data,
    * exclude (period),
    -- average payment, in rupees
    cc_value_cr  * 10 / nullif(cc_volume_mn, 0)                        as cc_avg_payment_rs,
    dc_value_cr  * 10 / nullif(dc_volume_mn, 0)                        as dc_avg_payment_rs,
    p2m_value_cr * 10 / nullif(p2m_volume_mn, 0)                       as upi_p2m_avg_payment_rs,
    p2p_value_cr * 10 / nullif(p2p_volume_mn, 0)                       as upi_p2p_avg_payment_rs,
    -- merchant payments: card payments at shops and online versus UPI person-to-merchant
    cc_volume_mn + dc_volume_mn + p2m_volume_mn                        as merchant_volume_mn,
    p2m_volume_mn / nullif(cc_volume_mn + dc_volume_mn + p2m_volume_mn, 0) as upi_share_of_merchant_volume,
    p2m_value_cr  / nullif(cc_value_cr + dc_value_cr + p2m_value_cr, 0)    as upi_share_of_merchant_value
from joined
