# RBI Bank-wise ATM / POS / Card Statistics — historic data + auto-updater

Source: https://rbi.org.in/scripts/atmview.aspx (monthly Excel per release, `ATMView.aspx?atmid=N`).
Feeds the Tableau Public workbook *Indian Payments Ecosystem Dashboard*.

## What is here

| Path | What |
|---|---|
| `data/raw/` | Every monthly Excel exactly as published by RBI, named `YYYY-MM_atmid<N>.xls[x]` (Apr 2011 → latest) |
| `data/index.csv` | One row per RBI release: atmid, label, year, month, revised flag, Excel/PDF URLs |
| `data/processed/RBI_ATM_POS_CARDS_ALL.xlsx` / `.csv` | **Drop-in replacement for the Tableau data source** (same 16 columns, same sheet name `RBI ATM_POS_CARDS_2016_to_2022`, values in Rs million) plus `bank_type` and `bank_name_published` |
| `data/processed/bank_month_all_metrics.csv` | Everything RBI publishes, one row per bank per month, raw values plus `_mn` (Rs million) versions |
| `data/processed/national_totals.csv` | RBI's published "Total" row for each month |
| `data/processed/parse_log.csv` | Per-file layout, unit, bank count, and sum-vs-total check |
| `scripts/update.py` | Run this to pull anything new and rebuild all outputs |

## Keeping it updated

```
cd D:\Personal\rbi-payments-data
python scripts\update.py
```

It re-scans RBI's release ids, downloads new or re-issued ("Revised") files, re-parses everything and rebuilds
the outputs only if something changed. Each run appends a line to `data/update_log.txt`.
RBI publishes a month roughly 6–8 weeks after month-end, so a monthly schedule is enough. To run it on the
1st and 15th at 09:00 via Windows Task Scheduler:

```
schtasks /Create /TN "RBI ATM stats update" /SC MONTHLY /D 1,15 /ST 09:00 ^
  /TR "cmd /c cd /d D:\Personal\rbi-payments-data && python scripts\update.py >> data\update_console.log 2>&1"
```

Requires Python 3 with `requests`, `pandas`, `openpyxl`, `xlrd`, and for the Google Sheet push `gspread`, `google-auth`.

## Google Sheets → Tableau Public auto-refresh

Tableau Public can refresh a published workbook by itself only when its data source is a Google Sheet.
`update.py` therefore pushes the processed CSVs to a Google Sheet after every rebuild, once this one-time
setup is done (about 10 minutes):

1. **Service account.** In https://console.cloud.google.com create (or pick) a project, enable the
   *Google Sheets API* and *Google Drive API*, then *IAM & Admin → Service Accounts → Create service account*.
   Open it, *Keys → Add key → JSON*, and save the downloaded file as `secrets/service_account.json`.
   Note the service account's e-mail (`something@project-id.iam.gserviceaccount.com`).
2. **Sheet.** In your own Google Drive create a blank Google Sheet named `RBI ATM_POS_CARDS_ALL`, share it with the
   service-account e-mail as *Editor*, and paste the ID from its URL
   (`docs.google.com/spreadsheets/d/<ID>/edit`) into `spreadsheet_id` in `config/gsheet.json`.
   (Leave `spreadsheet_id` empty and put your e-mail in `share_with` if you would rather let the script create the sheet.)
3. **Test.** `python scripts\push_to_gsheet.py --check` confirms access; `python scripts\push_to_gsheet.py` loads the
   tabs `RBI_ATM_POS_CARDS_ALL` and `national_totals`.
4. **Tableau.** Open the workbook in Tableau Desktop (Public edition), *Data → New Data Source → Google Sheets*, sign in,
   pick the sheet and the `RBI_ATM_POS_CARDS_ALL` tab, then *Data → Replace Data Source* from the old Excel source to
   the new one (the column names are identical, so every calculated field keeps working). Publish to Tableau Public
   with **"Keep my data in sync"** ticked. Tableau Public then re-reads the sheet once a day.

From then on the scheduled `update.py` run keeps the sheet current and Tableau Public keeps the dashboard current.
The sheet holds ~10.7k rows × 18 columns, far below Google's 10-million-cell limit.

## The HTML dashboard

`dashboard/` holds *India Card Monitor*, a single-page replacement for the Tableau dashboard (D3, no build step):

| File | What |
|---|---|
| `dashboard/page.html` | The page itself (body fragment). Edit this one. |
| `dashboard/data.json` | Compact dataset the page loads, written by `scripts/build_dashboard.py` (every `update.py` run) |
| `dashboard/index.html` | `page.html` wrapped as a complete document, generated alongside `data.json` |

**Live, self-updating copy:** https://illusionist-creator.github.io/rbi-payments-data/ (GitHub Pages, deployed by the
workflow below; repo https://github.com/illusionist-creator/rbi-payments-data). A snapshot is also published as a Claude artifact at https://claude.ai/artifact/C3jGdhAEUCkfuy6KrxrPoU.
To view locally, serve the folder over HTTP (`python -m http.server 8765 --directory dashboard`) and open
`http://127.0.0.1:8765/index.html`; opening the file directly blocks the `data.json` fetch.

## Hands-off refresh (GitHub Actions)

`.github/workflows/update.yml` runs on GitHub's servers every Monday and Thursday at 09:00 IST (and on demand
from the Actions tab). Each run: checks RBI for new or revised months, downloads them, re-parses everything,
rebuilds `data/processed/*` and `dashboard/data.json`, commits the result to `main`, and deploys `dashboard/`
to GitHub Pages. RBI publishes a month roughly 6–8 weeks after month-end, so most runs find nothing and exit quietly.

The Google Sheet push runs in the workflow only if the service-account key is stored as a repository secret named
`GSHEET_SA_JSON`. Add it once from this folder with:

```
gh secret set GSHEET_SA_JSON < secrets\service_account.json
```

Because the workflow commits data back to the repo, run `git pull` before running `update.py` locally.

## UPI data from NPCI

`scripts/npci_upi.py` collects NPCI's *UPI Ecosystem Statistics*
(https://www.npci.org.in/product/ecosystem-statistics/upi) through the same JSON API the page itself uses,
one call per table and month, and keeps every month's raw response under `data/npci/raw/<table>/YYYY-MM.json`.
NPCI's edge blocks Python's HTTP stack (TLS fingerprint) but accepts curl with Chrome headers, so the
collector shells out to curl, which is present on Windows 10+ and on GitHub's runners.

| CSV in `data/processed/` | NPCI table | From |
|---|---|---|
| `upi_apps.csv` | UPI Applications (per-app customer-initiated, B2C, B2B, total volume/value) | Jun 2020 |
| `upi_p2p_p2m.csv` | P2P and P2M totals per month | Apr 2020 |
| `upi_remitter_banks.csv`, `upi_beneficiary_banks.csv` | Top 50 member banks, approval and decline rates | Jan 2020 |
| `upi_payer_psp.csv`, `upi_payee_psp.csv` | Top 15 PSPs | 2021 |
| `upi_mcc.csv` | Merchant category classification | 2016 |
| `upi_member_vol_val.csv` | Top 50 banks by volume and value | 2016 |
| `upi_statewise.csv` | State and district statistics | recent months |
| `upi_chargeback.csv` | Chargebacks by beneficiary bank | 2021 |

Volumes are in millions of transactions and values in ₹ crore, as NPCI publishes them. The collector re-reads
the latest three months on every run because NPCI revises them; `update.py` runs it before rebuilding the
dashboard data, and a failure on NPCI's side never blocks the RBI refresh.

## How RBI's format changed and how it is reconciled

| Period | Layout | Value unit as published | Notes |
|---|---|---|---|
| Apr 2011 – Jun 2019 | 14 columns: ATM on/off-site, POS on/off-line, credit & debit cards outstanding, txns and value at ATM / at POS | Rs million | Aug 2013 has an extra ATM online/offline split; a few 2012–14 files carry per-group subtotals |
| Jul 2019 – Apr 2020 | same 14 columns | Rs lakh | |
| May 2020 – Feb 2022 | + Micro ATMs, Bharat QR | Rs lakh | RBI starts printing bank-group headings |
| Mar 2022 → | 26 columns: single PoS count, + UPI QR; card payments split into PoS / online (e-com) / others; cash withdrawal at ATM (and at PoS for debit) | Rs '000 | |

The parser detects the layout from the header, checks that the number of columns matches, and checks every metric:
the sum of the bank rows must equal RBI's published Total (all 184 files pass).

Mapping of the new (Mar 2022 →) columns onto the 16-column Tableau schema:

* `no_pos_on_line` = PoS terminals; `no_pos_off_line` = 0 (RBI no longer splits them) — so *Total POS* stays right.
* `no_*_card_pos_txn` / `..._value_in_mn` = card **payments** = at PoS + online (e-com) + others.
* `no_*_card_atm_txn` / `..._value_in_mn` = cash withdrawals at ATMs.
* Debit-card cash withdrawal at PoS is excluded from both (it is in `bank_month_all_metrics.csv` as `dc_cashpos_*`).

All values are converted to **Rs million** (`lakh ÷ 10`, `'000 ÷ 1000`). Continuity across both unit changes was
verified on the national totals.

## Bank names

RBI has spelt the same bank 190 different ways since 2011 (case, "Ltd"/"Limited", renames such as Ratnakar → RBL,
Catholic Syrian → CSB, IDFC → IDFC First, Hongkong and Shanghai Bkg Corpn → HSBC). `bank_names` /
`bank_name_std` is the standardised name (RBI's latest spelling, 86 banks); the original text is kept in
`bank_name_published`. `bank_type` (Public / Private / Foreign / Payment / Small Finance) comes from RBI's own
group headings where printed, otherwise from a small manual table in `scripts/build_outputs.py`.

## Known data caveats (RBI's, not the parser's)

* Nov–Dec 2016 (demonetisation) and Apr–May 2020 (lockdown) show genuine 30–80% swings.
* Some months are re-issued as "Revised"; `update.py` re-downloads a file whenever RBI changes its URL.
* Early files sometimes leave a bank blank for a metric; those cells are empty, not zero.
