# dbt transformation layer

The pandas step `scripts/build_outputs.py` rebuilt as a dbt project on DuckDB, with tests that pin
it to the pandas output row for row, plus NPCI's UPI tables and a mart that puts cards and UPI on one
calendar. 10,759 bank-month rows, 185 monthly releases (Apr 2011 to the latest), 190 published bank
spellings resolved to 86 banks.

**It gates the dashboard.** `.github/workflows/update.yml` runs `dbt build` after pulling new data and
before committing or deploying anything: if a test fails, nothing is published and the last good version
stays live. The docs (models, columns, tests, lineage graph) are deployed with the dashboard at
https://illusionist-creator.github.io/rbi-payments-data/dbt/.

```
cd dbt
py -3.12 -m venv .venv && .venv\Scripts\pip install -r requirements.txt
set DBT_PROFILES_DIR=.
.venv\Scripts\dbt build          # seeds, models and every test
.venv\Scripts\dbt docs generate && .venv\Scripts\dbt docs serve   # lineage graph and column docs
```

The sources are the parser's CSVs in `../data/processed`, read in place by DuckDB, so there is no load
step. `.github/workflows/dbt.yml` runs the same build on pull requests that touch this folder.

## Layers

| Layer | Model | What it does |
|---|---|---|
| seeds | `value_units` | Published unit → Rs million factor (million, lakh, thousand, crore) |
| | `bank_name_aliases` | Genuine renames RBI's spelling alone can't resolve (Ratnakar → RBL, Catholic Syrian → CSB, IDFC → IDFC First) |
| | `bank_type_manual` | Bank type for banks that closed before RBI printed group headings |
| staging | `stg_rbi__bank_month`, `stg_rbi__national_totals` | Types every metric; converts each value column to Rs million from the unit seed |
| intermediate | `int_bank_names` | Normalises case, punctuation, "The", "Limited", then applies the alias seed |
| | `int_bank_types` | Latest RBI group heading per bank, falling back to the manual seed |
| marts | `fct_bank_month` | Every metric per bank per month, plus series that survive RBI's layout changes |
| | `fct_national_month` | RBI's printed national Total, same series |
| | `dim_bank` | One row per bank: type, where the type came from, spellings used, first and last month reported |
| | `rpt_tableau_cards` | The Tableau workbook's 16-column contract |
| | `fct_payments_month` | Cards (RBI) and UPI (NPCI) on one monthly calendar in one unit: average payment per rail, UPI's share of merchant payments |
| staging (NPCI) | `stg_npci__upi_totals` | National UPI volume and value, P2P and P2M |
| | `stg_npci__upi_apps` | Per-app volumes across NPCI's two layouts (the table was redesigned in Dec 2020) |
| | `stg_npci__upi_member_banks` | Top-50 member banks, with NPCI's Total row dropped by flag *and* by name (it arrived unflagged Oct-Dec 2025) |
| | `stg_npci__upi_remitter_banks` | Approval, business-decline and technical-decline rates per remitter bank |
| | `stg_npci__autopay_banks` | UPI AutoPay executions and registrations per remitter bank, volumes rescaled to millions across NPCI's Dec 2024 unit change |
| | `stg_npci__atm_declines` | NFS (shared ATM network) approval and decline rates per card issuer |

RBI changed its layout three times (Jul 2019, May 2020, Mar 2022) and its value unit twice. The
`continuity_metrics` macro keeps `atm_total`, `pos_terminals` and card payments comparable across
all of them: from Mar 2022 RBI reports one PoS count and splits card payments into PoS, online and
other, so payments become the sum of the three.

## Tests

| Test | Guards against |
|---|---|
| `assert_bank_rows_reconcile_to_national_total` | Every month, every metric: bank rows sum to RBI's printed Total within 0.5% (the parser's own tolerance) |
| `assert_unit_conversion_matches_parser` | The unit seed reproduces the parser's Rs-million values |
| `assert_bank_month_matches_pandas`, `assert_tableau_output_matches_pandas` | The dbt marts differ from the pandas CSVs in any row or column (numbers to a relative 1e-9) |
| `unique_combination` on `fct_bank_month` | Two rows for the same bank spelling in one month |
| `assert_upi_p2p_plus_p2m_equals_total` | NPCI's P2P and P2M series not adding up to its UPI total (0.1%) |
| `assert_upi_member_banks_within_national_total` | NPCI's Total row slipping into the bank list and doubling a month |
| `assert_upi_decline_rates_sum_to_100` | A bank's approved + declined rates not summing to 100% (half a point of rounding allowed) |
| `assert_autopay_volume_unit_is_consistent` | A 20x month-on-month jump in AutoPay volume: NPCI changing its unit again (it moved from counts to millions in Dec 2024) |
| `assert_autopay_rates_sum_to_100` (warn) | AutoPay rows whose rates don't add up; about 20 known (Mar 2022, Dec 2023) |
| `assert_atm_decline_rates_within_range` (warn) | NFS rows outside 95-100.5%; May 2025 is off at almost every bank |
| relationships, accepted values, not null, unique | Unknown layouts or units, orphan banks, unmapped bank types |

Two checks are set to warn rather than fail, because they describe NPCI's own data and not a bug here:
one nameless row in the Apr 2017 member table (dropped in staging), and Slice Small Finance Bank listed
twice in some 2026 remitter tables.

The parity tests were checked by breaking `rpt_tableau_cards` on purpose: changing one expression
made them fail on exactly the 3,370 rows it affects.
