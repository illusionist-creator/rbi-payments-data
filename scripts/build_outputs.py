"""Turn the parsed bank-month rows into the final deliverables:

  data/processed/bank_month_all_metrics.csv   every metric RBI ever published, values also in Rs million
  data/processed/national_totals.csv          RBI's published 'Total' row per month
  data/processed/RBI_ATM_POS_CARDS_ALL.csv    the 16-column schema used by the Tableau workbook
  data/processed/RBI_ATM_POS_CARDS_ALL.xlsx   same, as Excel (sheet name kept identical to the old source)
"""
import re, sys
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "processed"
TABLEAU_SHEET = "RBI ATM_POS_CARDS_2016_to_2022"   # sheet name the published workbook already points at

# ---- bank name standardisation -------------------------------------------------------------
# canonical = the name RBI uses in its latest releases (upper case, no trailing full stop)
ALIASES = {
    "AMERICAN EXPRESS": "AMERICAN EXPRESS BANKING CORPORATION",
    "AMERICAN EXPRESS BKG CORP": "AMERICAN EXPRESS BANKING CORPORATION",
    "BANDHAN BANK": "BANDHAN BANK LTD",
    "BARCLAYS BANK": "BARCLAYS BANK PLC",
    "CATHOLIC SYRIAN BANK LTD": "CSB BANK LTD",
    "CITIBANK": "CITI BANK",
    "CITY UNION BANK": "CITY UNION BANK LTD",
    "DBS LTD": "DBS INDIA BANK LTD",
    "DBS BANK": "DBS INDIA BANK LTD",
    "DEVELOPMENT CREDIT BANK": "DCB BANK LTD",
    "DEVELOPMENT CREDIT BANK LTD": "DCB BANK LTD",
    "DEUTSCHE BANK": "DEUTSCHE BANK LTD",
    "DHANALAKSHMI BANK LTD": "DHANALAXMI BANK LTD",
    "HSBC": "HSBC LTD",
    "HONGKONG AND SHANGHAI BKG CORPN": "HSBC LTD",
    "IDBI LTD": "IDBI BANK LTD",
    "IDFC BANK LTD": "IDFC FIRST BANK LTD",
    "ING VYSYA BANK": "ING VYSYA BANK LTD",
    "JAMMU AND KASHMIR BANK": "JAMMU AND KASHMIR BANK LTD",
    "LAXMI VILAS BANK LTD": "LAKSHMI VILAS BANK LTD",
    "RATNAKAR BANK LTD": "RBL BANK LTD",
    "RBS (ABN AMRO)": "ROYAL BANK OF SCOTLAND N V",
    "SBI COMM AND INT BANK LTD": "SBI COMMERCIAL AND INTERNATIONAL BANK LTD",
    "SBM BANK INDIA": "SBM BANK INDIA LTD",
    "SOUTH INDIAN BANK LTD": "SOUTH INDIAN BANK",
    "STANDARD CHARTERED BANK": "STANDARD CHARTERED BANK LTD",
    "TAMILNADU MERCANTILE BANK LTD": "TAMILNAD MERCANTILE BANK LTD",
}
# bank type for banks that disappeared before RBI started printing group headings (mid-2020)
BANK_TYPE_MANUAL = {
    "Public Sector Banks": ["ALLAHABAD BANK", "ANDHRA BANK", "CORPORATION BANK", "DENA BANK", "ORIENTAL BANK OF COMMERCE",
                            "SYNDICATE BANK", "UNITED BANK OF INDIA", "VIJAYA BANK", "STATE BANK OF BIKANER AND JAIPUR",
                            "STATE BANK OF HYDERABAD", "STATE BANK OF MYSORE", "STATE BANK OF PATIALA",
                            "STATE BANK OF TRAVANCORE", "IDBI BANK LTD"],
    "Private Sector Banks": ["ING VYSYA BANK LTD", "LAKSHMI VILAS BANK LTD", "SBI COMMERCIAL AND INTERNATIONAL BANK LTD"],
    "Foreign Banks": ["OMAN INTERNATIONAL BANK SAO", "ROYAL BANK OF SCOTLAND N V", "FIRSTRAND BANK"],
    "Payment Banks": ["ADITYA BIRLA IDEA PAYMENTS BANK"],
}


def std_name(name):
    s = str(name).upper().replace("&", " AND ")
    s = re.sub(r"[.,'’]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"^THE\s+", "", s)
    s = re.sub(r"\bLIMITED\b", "LTD", s)
    return ALIASES.get(s, s)


def std_group(g):
    """Collapse RBI's sub-headings (Nationalised Banks, State Bank Group, Old/New Private...) to five types."""
    s = str(g).lower()
    if "nationalis" in s or "nationaliz" in s or "state bank" in s or "public sector" in s:
        return "Public Sector Banks"
    if "private" in s:
        return "Private Sector Banks"
    if "foreign" in s:
        return "Foreign Banks"
    if "payment" in s:
        return "Payment Banks"
    if "small finance" in s:
        return "Small Finance Banks"
    return None


def add_bank_type(df):
    """One bank type per canonical bank: RBI's own group heading (latest one seen) where available, else manual."""
    known = df[df.bank_group_published.notna()].assign(t=lambda x: x.bank_group_published.map(std_group))
    known = known[known.t.notna()].sort_values("period")
    latest = known.groupby("bank_name_std")["t"].last()
    manual = {b: t for t, banks in BANK_TYPE_MANUAL.items() for b in banks}
    df["bank_type"] = df.bank_name_std.map(latest).fillna(df.bank_name_std.map(manual))
    return df


def first_sum(df, cols):
    """Row-wise sum that stays NaN when none of the columns is present/populated."""
    present = [c for c in cols if c in df]
    return df[present].sum(axis=1, min_count=1)


def main():
    b = pd.read_csv(OUT / "bank_month_all_metrics_raw.csv")
    b = b.rename(columns={"bank_group": "bank_group_published"})
    b["bank_name_std"] = b.bank_name_published.map(std_name)
    b["start_date"] = pd.to_datetime(b.period + "-01")
    b = add_bank_type(b)

    # continuity metrics across the three definitions RBI has used
    c26 = b.layout.eq("C26")
    b["pos_terminals"] = np.where(c26, b["pos"], first_sum(b, ["pos_online", "pos_offline"]))
    b["atm_total"] = first_sum(b, ["atm_onsite", "atm_offsite"])
    for card in ("cc", "dc"):
        b[f"{card}_payments_vol"] = np.where(c26, first_sum(b, [f"{card}_pos_vol", f"{card}_ecom_vol", f"{card}_other_vol"]),
                                             b[f"{card}_pos_vol"])
        b[f"{card}_payments_val_mn"] = np.where(c26, first_sum(b, [f"{card}_pos_val_mn", f"{card}_ecom_val_mn", f"{card}_other_val_mn"]),
                                                b[f"{card}_pos_val_mn"])
    lead = ["period", "start_date", "atmid", "layout", "value_unit_published", "bank_type", "bank_group_published",
            "bank_name_std", "bank_name_published"]
    derived = ["atm_total", "pos_terminals", "cc_payments_vol", "cc_payments_val_mn", "dc_payments_vol", "dc_payments_val_mn"]
    rest = [c for c in b.columns if c not in lead + derived]
    b = b[lead + derived + rest].sort_values(["start_date", "bank_type", "bank_name_std"], na_position="last")
    b.to_csv(OUT / "bank_month_all_metrics.csv", index=False, date_format="%Y-%m-%d")

    # ---- Tableau workbook schema ----
    t = pd.DataFrame({
        "start_date": b.start_date,
        "bank_names": b.bank_name_std,
        "no_atms_on_site": b.atm_onsite,
        "no_atms_off_site": b.atm_offsite,
        "no_pos_on_line": np.where(c26, b["pos"], b.pos_online),
        "no_pos_off_line": np.where(c26, 0, b.pos_offline),
        "no_credit_cards": b.cc_cards,
        "no_credit_card_atm_txn": b.cc_atm_vol,
        "no_credit_card_pos_txn": b.cc_payments_vol,
        "no_credit_card_atm_txn_value_in_mn": b.cc_atm_val_mn,
        "no_credit_card_pos_txn_value_in_mn": b.cc_payments_val_mn,
        "no_debit_cards": b.dc_cards,
        "no_debit_card_atm_txn": b.dc_atm_vol,
        "no_debit_card_pos_txn": b.dc_payments_vol,
        "no_debit_card_atm_txn_value_in_mn": b.dc_atm_val_mn,
        "no_debit_card_pos_txn_value_in_mn": b.dc_payments_val_mn,
        "bank_type": b.bank_type,
        "bank_name_published": b.bank_name_published,
    })
    t.to_csv(OUT / "RBI_ATM_POS_CARDS_ALL.csv", index=False, date_format="%Y-%m-%d")
    with pd.ExcelWriter(OUT / "RBI_ATM_POS_CARDS_ALL.xlsx", engine="openpyxl") as xw:
        t.to_excel(xw, sheet_name=TABLEAU_SHEET, index=False)

    # ---- national totals ----
    n = pd.read_csv(OUT / "national_totals_raw.csv")
    n["start_date"] = pd.to_datetime(n.period + "-01")
    c = n.layout.eq("C26")
    n["pos_terminals"] = np.where(c, n["pos"], first_sum(n, ["pos_online", "pos_offline"]))
    n["atm_total"] = first_sum(n, ["atm_onsite", "atm_offsite"])
    for card in ("cc", "dc"):
        n[f"{card}_payments_vol"] = np.where(c, first_sum(n, [f"{card}_pos_vol", f"{card}_ecom_vol", f"{card}_other_vol"]), n[f"{card}_pos_vol"])
        n[f"{card}_payments_val_mn"] = np.where(c, first_sum(n, [f"{card}_pos_val_mn", f"{card}_ecom_val_mn", f"{card}_other_val_mn"]), n[f"{card}_pos_val_mn"])
    lead = ["period", "start_date", "atmid", "layout", "value_unit_published"]
    n = n[lead + derived + [x for x in n.columns if x not in lead + derived]].sort_values("start_date")
    n.to_csv(OUT / "national_totals.csv", index=False, date_format="%Y-%m-%d")

    print(f"bank-month rows: {len(b)} | months: {b.period.nunique()} ({b.period.min()} to {b.period.max()})")
    print(f"distinct published names: {b.bank_name_published.nunique()} -> standardised: {b.bank_name_std.nunique()}")
    print("bank_type missing for:", sorted(b[b.bank_type.isna()].bank_name_std.unique().tolist()) or "none")
    print("outputs written to", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
