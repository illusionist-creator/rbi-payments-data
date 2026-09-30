-- Same check for the full bank-month table (bank_month_all_metrics.csv).

{{ assert_same_rows(
    ref('fct_bank_month'),
    'bank_month_all_metrics.csv',
    key=['period', 'bank_name_published'],
    text_cols=['period', 'layout', 'value_unit_published', 'bank_type', 'bank_group_published',
               'bank_name_std', 'bank_name_published'],
    date_cols=['start_date']
) }}
