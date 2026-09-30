-- The 16-column schema the Tableau workbook was built on (plus bank_type and bank_name_published).
-- Replaces RBI_ATM_POS_CARDS_ALL.csv; column names must not change or the workbook's fields break.

select
    start_date,
    bank_name_std                                           as bank_names,
    atm_onsite                                              as no_atms_on_site,
    atm_offsite                                             as no_atms_off_site,
    case when layout = 'C26' then pos else pos_online end   as no_pos_on_line,
    case when layout = 'C26' then 0 else pos_offline end    as no_pos_off_line,
    cc_cards                                                as no_credit_cards,
    cc_atm_vol                                              as no_credit_card_atm_txn,
    cc_payments_vol                                         as no_credit_card_pos_txn,
    cc_atm_val_mn                                           as no_credit_card_atm_txn_value_in_mn,
    cc_payments_val_mn                                      as no_credit_card_pos_txn_value_in_mn,
    dc_cards                                                as no_debit_cards,
    dc_atm_vol                                              as no_debit_card_atm_txn,
    dc_payments_vol                                         as no_debit_card_pos_txn,
    dc_atm_val_mn                                           as no_debit_card_atm_txn_value_in_mn,
    dc_payments_val_mn                                      as no_debit_card_pos_txn_value_in_mn,
    bank_type,
    bank_name_published
from {{ ref('fct_bank_month') }}
