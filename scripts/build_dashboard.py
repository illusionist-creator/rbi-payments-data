"""Write dashboard/data.json - the compact dataset the HTML dashboard loads.

Bank rows are stored columnar-by-row as [monthIdx, bankIdx, m1..m14] with values in Rs million
for money and plain counts elsewhere; national totals carry the extra post-2022 metrics.
"""
import json, re, sys
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "dashboard" / "data.json"
BANK_COLS = ["atm_onsite", "atm_offsite", "pos_terminals", "cc_cards", "cc_atm_vol", "cc_payments_vol",
             "cc_atm_val_mn", "cc_payments_val_mn", "dc_cards", "dc_atm_vol", "dc_payments_vol",
             "dc_atm_val_mn", "dc_payments_val_mn"]
NAT_COLS = BANK_COLS + ["micro_atm", "bharat_qr", "upi_qr", "cc_pos_vol", "cc_ecom_vol", "cc_other_vol",
                        "cc_pos_val_mn", "cc_ecom_val_mn", "cc_other_val_mn", "dc_pos_vol", "dc_ecom_vol",
                        "dc_other_vol", "dc_pos_val_mn", "dc_ecom_val_mn", "dc_other_val_mn",
                        "dc_cashpos_vol", "dc_cashpos_val_mn"]
TYPE_ORDER = ["Public Sector Banks", "Private Sector Banks", "Foreign Banks", "Small Finance Banks", "Payment Banks"]


def num(v, nd=1):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    r = round(float(v), nd)
    return int(r) if r == int(r) else r


UPI_ALIASES = {"PHONEPE": "PhonePe", "PHONE PE": "PhonePe", "GOOGLE PAY": "Google Pay", "GOOGLE PAY APPS": "Google Pay",
               "PAYTM": "Paytm", "PAYTM PAYMENTS BANK APP": "Paytm", "PAYTM APPS": "Paytm", "PAYTM OCL": "Paytm", "CRED": "CRED", "BHIM": "BHIM",
               "FAMAPP BY TRIO": "FamPay", "FAMAPP": "FamPay", "NAVI TECHNOLOGIES": "Navi", "KOTAK MAHINDRA BANK APPS": "Kotak",
               "AMAZON PAY": "Amazon Pay", "WHATSAPP": "WhatsApp", "NAVI": "Navi", "SUPER MONEY": "super.money",
               "SUPERMONEY": "super.money", "FAMPAY": "FamPay", "SLICE": "slice", "GROWW": "Groww", "MOBIKWIK": "MobiKwik",
               "FLIPKART UPI": "Flipkart UPI", "AIRTEL PAYMENTS BANK APPS": "Airtel Thanks", "AIRTEL THANKS": "Airtel Thanks",
               "BAJAJ PAY": "Bajaj Pay", "JUPITER": "Jupiter", "KIWI": "Kiwi", "TATA NEU": "Tata Neu", "ICICI BANK APPS": "ICICI iMobile",
               "HDFC BANK APPS": "HDFC PayZapp", "SBI YONO": "SBI YONO", "YONO SBI": "SBI YONO", "AXIS BANK APPS": "Axis Mobile"}


def name_key(s):
    """Spelling-insensitive key: 'Yes bank Ltd.' / 'YES BANK LTD' / 'Paytm (OCL )' collapse together."""
    k = re.sub(r"[#*]+", "", str(s)).upper()
    k = re.sub(r"\(.*?\)", " ", k)
    k = re.sub(r"\b(LTD|LIMITED|PVT|PRIVATE|BANK LTD|APPS?)\b\.?", " ", k)
    k = re.sub(r"[^A-Z0-9]+", " ", k).strip()
    return k


def clean_name(s):
    s = re.sub(r"[#*]+", "", str(s)).strip()
    s = re.sub(r"\s*\(.*?\)\s*", " ", s).strip()
    s = re.sub(r"\s+", " ", s)
    key = re.sub(r"[^A-Z0-9 .]", "", s.upper()).strip()
    return UPI_ALIASES.get(key, s)


def series_block(df, name_col, months, cols, top=12, min_months=1):
    """Turn a long table (period, name, metrics) into {names, per-name arrays} keeping the top entities by latest value."""
    midx = {m: i for i, m in enumerate(months)}
    df = df[df.period.isin(midx)].copy()
    df["_k"] = df[name_col].map(name_key)
    # display name: the alias if one exists, else the most recent spelling NPCI used
    latest_spelling = df.sort_values("period").groupby("_k")[name_col].last().map(clean_name)
    aliased = df.groupby("_k")[name_col].agg(lambda x: next((UPI_ALIASES[k] for k in x.map(lambda v: re.sub(r"[^A-Z0-9 .]", "", clean_name(v).upper()).strip()) if k in UPI_ALIASES), None))
    df["_n"] = df["_k"].map(aliased.fillna(latest_spelling))
    g = df.groupby(["_n", "period"])[cols].sum(min_count=1).reset_index()
    latest = g.period.max()                                   # last month that has rows for this table
    order = g[g.period == latest].sort_values(cols[0], ascending=False)["_n"].tolist()
    seen = set(order)
    order += [n for n in g.groupby("_n")[cols[0]].max().sort_values(ascending=False).index if n not in seen]
    out = []
    for n in order[:top]:
        sub = g[g._n == n]
        rec = {"n": n}
        for c in cols:
            arr = [None] * len(months)
            for p, v in zip(sub.period, sub[c]):
                arr[midx[p]] = num(v, 2)
            rec[c] = arr
        out.append(rec)
    # everything outside the top list, summed per month
    rest = g[~g._n.isin(order[:top])].groupby("period")[cols].sum(min_count=1)
    others = {c: [num(rest[c].get(m), 2) if m in rest.index else None for m in months] for c in cols}
    return out, others


def build_upi():
    P = ROOT / "data" / "processed"
    if not (P / "upi_p2p_p2m.csv").exists():
        return None
    tot = pd.read_csv(P / "upi_p2p_p2m.csv").sort_values("period").drop_duplicates("period", keep="last")
    months = sorted(tot.period.unique())
    totals = {k: [num(v, 2) for v in tot.set_index("period").reindex(months)[c].tolist()] for k, c in
              [("vol", "total_volume_mn"), ("val", "total_value_cr"), ("p2p_vol", "p_2_p_volume_mn"), ("p2p_val", "p_2_p_value_cr"),
               ("p2m_vol", "p_2_m_volume_mn"), ("p2m_val", "p_2_m_value_cr")] if c in tot}
    upi = {"months": months, "totals": totals, "unit": "volume in million transactions, value in Rs crore"}
    apps = pd.read_csv(P / "upi_apps.csv") if (P / "upi_apps.csv").exists() else None
    if apps is not None and "customer_initiated_transactions_volume_mn" in apps:
        top, others = series_block(apps, "application_name", months,
                                   ["customer_initiated_transactions_volume_mn", "customer_initiated_transactions_value_cr"], top=12)
        upi["apps"] = [{"n": r["n"], "vol": r["customer_initiated_transactions_volume_mn"], "val": r["customer_initiated_transactions_value_cr"]} for r in top]
        upi["apps_others"] = {"vol": others["customer_initiated_transactions_volume_mn"], "val": others["customer_initiated_transactions_value_cr"]}
    psp = pd.read_csv(P / "upi_payer_psp.csv") if (P / "upi_payer_psp.csv").exists() else None
    if psp is not None and "payer_psp" in psp:
        top, _ = series_block(psp, "payer_psp", months, ["total_volume_in_mn"], top=10)
        upi["payer_psp"] = [{"n": r["n"], "vol": r["total_volume_in_mn"]} for r in top]
    mem = pd.read_csv(P / "upi_member_vol_val.csv") if (P / "upi_member_vol_val.csv").exists() else None
    if mem is not None and "bank_name" in mem:
        bmonths = sorted(mem.period.unique())
        top, others = series_block(mem, "bank_name", bmonths, ["volume_mn", "value_cr"], top=12)
        upi["bank_months"] = bmonths
        upi["banks"] = [{"n": r["n"], "vol": r["volume_mn"], "val": r["value_cr"]} for r in top]
        upi["banks_others"] = {"vol": others["volume_mn"], "val": others["value_cr"]}
    mcc = pd.read_csv(P / "upi_mcc.csv") if (P / "upi_mcc.csv").exists() else None
    if mcc is not None and "description" in mcc and "volume_in_mn" in mcc:
        last = mcc[mcc.period == mcc.period.max()].copy()
        last["volume_in_mn"] = pd.to_numeric(last.volume_in_mn, errors="coerce")
        last = last[~last.description.astype(str).str.strip().str.lower().isin(["total", "grand total", "others", "all other categories"])]
        upi["mcc_month"] = mcc.period.max()
        upi["mcc"] = [{"n": re.sub(r"\s+", " ", str(r.description)).strip(), "code": str(r.mcc), "vol": num(r.volume_in_mn, 2), "val": num(r.value_in_cr, 2)}
                      for r in last.sort_values("volume_in_mn", ascending=False).head(15).itertuples()]
    sw = pd.read_csv(P / "upi_statewise.csv") if (P / "upi_statewise.csv").exists() else None
    if sw is not None and "state_union_territory" in sw:
        st = sw[sw["district"].isna()] if "district" in sw else sw
        st = st.copy()
        st["_n"] = (st.state_union_territory.astype(str).str.replace(r"\s*Total\s*$", "", regex=True).str.replace("#", "")
                    .str.replace("&", " AND ").str.replace(r"\s+", " ", regex=True).str.strip().str.upper()
                    .replace({"ANDAMAN AND NICOBAR": "ANDAMAN AND NICOBAR ISLANDS", "NCT OF DELHI": "DELHI", "ORISSA": "ODISHA",
                              "PONDICHERRY": "PUDUCHERRY", "UTTARANCHAL": "UTTARAKHAND"}))
        st["volume_in_mn"] = pd.to_numeric(st.volume_in_mn, errors="coerce")
        st["value_in_cr"] = pd.to_numeric(st.value_in_cr, errors="coerce")
        smonths = sorted(st.period.unique())
        names = sorted(st._n.unique())
        piv_v = st.pivot_table(index="_n", columns="period", values="volume_in_mn", aggfunc="sum").reindex(index=names, columns=smonths)
        piv_c = st.pivot_table(index="_n", columns="period", values="value_in_cr", aggfunc="sum").reindex(index=names, columns=smonths)
        upi["states"] = {"months": smonths, "names": names,
                         "vol": [[num(v, 2) for v in row] for row in piv_v.values.tolist()],
                         "val": [[num(v, 2) for v in row] for row in piv_c.values.tolist()]}
    return upi


def main():
    b = pd.read_csv(ROOT / "data" / "processed" / "bank_month_all_metrics.csv")
    n = pd.read_csv(ROOT / "data" / "processed" / "national_totals.csv")
    months = sorted(b.period.unique())
    midx = {m: i for i, m in enumerate(months)}
    latest = months[-1]
    # bank order: by latest-month credit cards then debit cards, so index 0 is the biggest issuer
    last = b[b.period == latest].set_index("bank_name_std")
    cards = b.groupby("bank_name_std")[["cc_cards", "dc_cards"]].last().fillna(0)
    order = (cards.cc_cards + cards.dc_cards / 10).sort_values(ascending=False).index.tolist()
    types = b.groupby("bank_name_std")["bank_type"].first()
    span = b.groupby("bank_name_std")["period"].agg(["min", "max"])
    banks, bidx = [], {}
    for i, name in enumerate(order):
        bidx[name] = i
        banks.append({"n": name, "t": TYPE_ORDER.index(types[name]) if types[name] in TYPE_ORDER else 5,
                      "from": span.loc[name, "min"], "to": span.loc[name, "max"]})
    rows = []
    for r in b.itertuples(index=False):
        rows.append([midx[r.period], bidx[r.bank_name_std]] + [num(getattr(r, c)) for c in BANK_COLS])
    nat = n.sort_values("period")
    national = {c: [num(v) for v in nat[c].tolist()] for c in NAT_COLS if c in nat}
    layout = nat.layout.tolist()
    data = {
        "generated": pd.Timestamp.today().strftime("%Y-%m-%d"),
        "source": "RBI - Bank-wise ATM/POS/Card Statistics (https://rbi.org.in/scripts/atmview.aspx)",
        "months": months,
        "types": TYPE_ORDER + ["Other"],
        "bank_cols": BANK_COLS,
        "banks": banks,
        "rows": rows,
        "national": national,
        "layout": layout,
        "value_unit": "Rs million",
        "upi": build_upi(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size/1e6:.2f} MB): {len(months)} months, {len(banks)} banks, {len(rows)} rows")
    # page.html is the body fragment the Claude artifact viewer wraps itself; index.html is the same page
    # as a complete document for any ordinary web host or a local folder served over HTTP
    page = OUT.parent / "page.html"
    if page.exists():
        html = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
                '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
                '<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}'
                'img{max-width:100%}[hidden]{display:none!important}</style>\n</head>\n<body>\n'
                + page.read_text(encoding="utf-8") + '\n</body>\n</html>\n')
        (OUT.parent / "index.html").write_text(html, encoding="utf-8")
        print("wrote", OUT.parent / "index.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
