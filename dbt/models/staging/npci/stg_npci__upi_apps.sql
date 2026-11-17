-- One row per UPI app per month across both of NPCI's layouts (the table was redesigned in Dec 2020).
-- NPCI sometimes lists the same app twice in a month; the rows are summed, as the dashboard does.

with unified as (
    select
        period,
        trim(coalesce(application_name, upi_application_name))                     as app_name,
        case when application_name is null then 'pre_dec_2020' else 'current' end as layout,
        cast(coalesce(total_volume_mn, upi_volume_mn) as double)                   as total_volume_mn,
        cast(coalesce(total_value_cr, upi_value_cr) as double)                     as total_value_cr,
        -- only the current layout separates customer-initiated payments from B2B, B2C and on-us
        cast(customer_initiated_transactions_volume_mn as double)                  as customer_volume_mn,
        cast(customer_initiated_transactions_value_cr as double)                   as customer_value_cr
    from {{ source('npci', 'upi_apps') }}
)

select
    period,
    app_name,
    layout,
    sum(total_volume_mn)    as total_volume_mn,
    sum(total_value_cr)     as total_value_cr,
    sum(customer_volume_mn) as customer_volume_mn,
    sum(customer_value_cr)  as customer_value_cr,
    count(*)                as rows_published
from unified
group by all
