# dbt transformation layer

The pandas step `scripts/build_outputs.py` rebuilt as a dbt project on DuckDB, with tests that pin
it to the pandas output row for row. 10,759 bank-month rows, 185 monthly releases (Apr 2011 to the
latest), 190 published bank spellings resolved to 86 banks.

```
cd dbt
py -3.12 -m venv .venv && .venv\Scripts\pip install -r requirements.txt
set DBT_PROFILES_DIR=.
.venv\Scripts\dbt build          # seeds, models and every test
.venv\Scripts\dbt docs generate && .venv\Scripts\dbt docs serve   # lineage graph and column docs
```

The sources are the parser's CSVs in `../data/processed`, read in place by DuckDB, so there is no load
step. `.github/workflows/dbt.yml` runs `dbt build` after every data refresh and on any change here.

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
| relationships, accepted values, not null, unique | Unknown layouts or units, orphan banks, unmapped bank types |

The parity tests were checked by breaking `rpt_tableau_cards` on purpose: changing one expression
made them fail on exactly the 3,370 rows it affects.
