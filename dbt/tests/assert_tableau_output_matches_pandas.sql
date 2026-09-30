-- The dbt build must reproduce RBI_ATM_POS_CARDS_ALL.csv from scripts/build_outputs.py row for row,
-- so the Tableau workbook can be switched to this model without any field changing.

{{ assert_same_rows(
    ref('rpt_tableau_cards'),
    'RBI_ATM_POS_CARDS_ALL.csv',
    key=['start_date', 'bank_name_published'],
    text_cols=['bank_names', 'bank_type', 'bank_name_published'],
    date_cols=['start_date']
) }}
