"""Write dashboard/data.json - the compact dataset the HTML dashboard loads.

Bank rows are stored columnar-by-row as [monthIdx, bankIdx, m1..m14] with values in Rs million
for money and plain counts elsewhere; national totals carry the extra post-2022 metrics.
"""
import json, sys
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
