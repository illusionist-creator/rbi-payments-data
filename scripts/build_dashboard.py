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


BANK_KEY_ALIASES = {"IDFC": "IDFC FIRST"}


def bank_key(s):
    """Stricter than name_key for matching NPCI bank spellings to RBI's: drops BANK/LTD/LIMITED wherever they sit."""
    k = re.sub(r"\b(BANK|LTD|LIMITED)\b", " ", name_key(s))
    k = re.sub(r"\s+", " ", k).strip()
    return BANK_KEY_ALIASES.get(k, k)


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


def build_upi(types_by_key=None, idx_by_key=None):
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
        if "is_total" in mem:
            mem = mem[mem.is_total != True]
        bmonths = sorted(mem.period.unique())
        top, others = series_block(mem, "bank_name", bmonths, ["volume_mn", "value_cr"], top=12)
        upi["bank_months"] = bmonths
        upi["banks"] = [{"n": r["n"], "vol": r["volume_mn"], "val": r["value_cr"]} for r in top]
        upi["banks_others"] = {"vol": others["volume_mn"], "val": others["value_cr"]}
        if types_by_key:
            # share of the top-50 remitter volume by RBI bank group (unmatched names, mostly non-banks, go to Other)
            mm = mem.copy()
            mm["_t"] = mm.bank_name.map(lambda n: types_by_key.get(bank_key(n), 5))
            mm["volume_mn"] = pd.to_numeric(mm.volume_mn, errors="coerce")
            piv = mm.pivot_table(index="_t", columns="period", values="volume_mn", aggfunc="sum").reindex(index=range(6), columns=bmonths)
            tot = piv.sum(axis=0)
            upi["type_share"] = {"months": bmonths, "share": [[(num(v, 4) if not np.isnan(v) else None) for v in (piv.loc[t] / tot).tolist()] for t in range(6)]}
    # transaction quality: NPCI's remitter-bank table reports approval, business-decline and technical-decline rates per bank
    rq = P / "upi_remitter_banks.csv"
    if rq.exists():
        r = pd.read_csv(rq)
        if "type_name" in r:
            r = r[r.type_name == "remitter"]
        need = {"upi_remitter_banks", "total_volume_in_mn", "bd_percent", "td_percent"}
        if need <= set(r.columns):
            r = r.copy()
            for c in ["total_volume_in_mn", "bd_percent", "td_percent", "approved_percent"]:
                if c in r:
                    r[c] = pd.to_numeric(r[c], errors="coerce")
            r = r.dropna(subset=["total_volume_in_mn"])
            qm = sorted(r.period.unique())

            def wavg(x, c):
                w = x.total_volume_in_mn
                return num((x[c].fillna(0) * w).sum() / w.sum(), 3) if w.sum() else None
            g = r.groupby("period")
            quality = {"months": qm, "vol": [num(g.get_group(p).total_volume_in_mn.sum(), 2) for p in qm],
                       "bd": [wavg(g.get_group(p), "bd_percent") for p in qm], "td": [wavg(g.get_group(p), "td_percent") for p in qm],
                       "note": "volume-weighted across the top remitter banks NPCI lists each month"}
            r["_k"] = r.upi_remitter_banks.map(bank_key)
            last12 = r[r.period.isin(qm[-12:])]
            spelling = r.sort_values("period").groupby("_k").upi_remitter_banks.last().map(clean_name)
            qidx = {p: i for i, p in enumerate(qm)}
            banks = []
            for k, x in last12.groupby("_k"):
                xs = x.sort_values("period")
                full = r[r._k == k].sort_values("period").drop_duplicates("period", keep="last")
                bd_s, td_s = [None] * len(qm), [None] * len(qm)
                for row in full.itertuples():
                    bd_s[qidx[row.period]] = num(row.bd_percent, 2); td_s[qidx[row.period]] = num(row.td_percent, 2)
                banks.append({"n": spelling[k], "rbi": idx_by_key.get(k) if idx_by_key else None,
                              "vol": num(xs.total_volume_in_mn.mean(), 2), "bd": wavg(xs, "bd_percent"), "td": wavg(xs, "td_percent"),
                              "bd_last": num(xs.bd_percent.iloc[-1], 2), "months": int(len(xs)), "bd_s": bd_s, "td_s": td_s})
            banks.sort(key=lambda d: -(d["vol"] or 0))
            quality["banks"] = banks[:20]
            upi["quality"] = quality
    # disputes: NPCI's chargeback table per beneficiary bank, summed to a system-wide rate
    cq = P / "upi_chargeback.csv"
    if cq.exists():
        c = pd.read_csv(cq)
        cols = ["chargebacks_received_during_the_month", "chargebacks_accepted_during_the_month", "total_txns_during_the_month"]
        if set(cols) <= set(c.columns):
            for k in cols:
                c[k] = pd.to_numeric(c[k], errors="coerce")
            g = c.groupby("period").agg(rec=(cols[0], "sum"), acc=(cols[1], "sum"), tx=(cols[2], "sum"))
            g = g[g.tx > 0]
            upi["chargebacks"] = {"months": g.index.tolist(), "per10k": [num(v, 3) for v in (g.rec / g.tx * 1e4)],
                                  "received": [num(v, 0) for v in g.rec], "accepted_pct": [num(v, 1) for v in (g.acc / g.rec.replace(0, np.nan) * 100).fillna(0)]}
            # per beneficiary bank, for the banks that match an RBI issuer (NPCI also lists PSP sponsor entries and non-banks)
            if idx_by_key and "beneficiary_bank" in c:
                cm = g.index.tolist(); cidx = {p: i for i, p in enumerate(cm)}
                c["_k"] = c.beneficiary_bank.map(bank_key)
                c = c[c._k.isin(idx_by_key)]
                gb = c.groupby(["_k", "period"]).agg(rec=(cols[0], "sum"), tx=(cols[2], "sum")).reset_index()
                recent = gb[gb.period.isin(cm[-12:])].groupby("_k").tx.sum().sort_values(ascending=False).head(25)
                spelling = c.sort_values("period").groupby("_k").beneficiary_bank.last()
                cbanks = []
                for k in recent.index:
                    x = gb[gb._k == k]
                    s = [None] * len(cm)
                    for row in x.itertuples():
                        if row.tx > 0:
                            s[cidx[row.period]] = num(row.rec / row.tx * 1e4, 3)
                    x12 = x[x.period.isin(cm[-12:])]
                    cbanks.append({"n": clean_name(spelling[k]).title(), "rbi": idx_by_key[k], "tx": num(x12.tx.mean(), 0),
                                   "per10k": num(x12.rec.sum() / x12.tx.sum() * 1e4, 3) if x12.tx.sum() else None, "s": s})
                upi["chargebacks"]["banks"] = cbanks
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
        # district drill-down: NPCI district rows (from Mar 2026) matched to the map's district names
        dmap = ROOT / "dashboard" / "india_districts.json"
        if "district" in sw and dmap.exists():
            import difflib
            geo = json.loads(dmap.read_text(encoding="utf-8"))
            norm = lambda x: re.sub(r"[^A-Z]", "", str(x).upper())
            by_state = {}
            for f in geo["features"]:
                p = f["properties"]
                by_state.setdefault(norm(p["st_nm"]), {})[norm(p["district"])] = p["district"]
            dd = sw[sw["district"].notna()].copy()
            dd["state_key"] = (dd.state_union_territory.astype(str).str.replace("&", " AND ").str.replace("#", "").str.upper()
                        .str.replace(r"\s+", " ", regex=True).str.strip()
                        .replace({"ANDAMAN AND NICOBAR": "ANDAMAN AND NICOBAR ISLANDS", "NCT OF DELHI": "DELHI"}))
            dd["volume_in_mn"] = pd.to_numeric(dd.volume_in_mn, errors="coerce")
            dd["value_in_cr"] = pd.to_numeric(dd.value_in_cr, errors="coerce")
            dmonths = sorted(dd.period.unique())
            # districts renamed since the 2011-based boundaries: NPCI's name -> the map's name
            RENAMED = {"CHHATRAPATISAMBHAJINAGAR": "AURANGABAD", "AHILYANAGAR": "AHMEDNAGAR", "DHARASHIV": "OSMANABAD",
                       "PRAYAGRAJ": "ALLAHABAD", "AYODHYA": "FAIZABAD", "GURUGRAM": "GURGAON", "NUH": "MEWAT",
                       "KAMRUPMETRO": "KAMRUPMETROPOLITAN", "KAMRUPRURAL": "KAMRUP", "SIBSAGAR": "SIVASAGAR", "DARANG": "DARRANG",
                       "SRIBHUMI": "KARIMGANJ", "MARIGAON": "MORIGAON", "KAIMURBHABUA": "KAIMUR", "PASHCHIMCHAMPARAN": "WESTCHAMPARAN",
                       "PURBACHAMPARAN": "EASTCHAMPARAN", "SRIPOTTISRIRAMULUNELLORE": "SPSNELLORE", "YSR": "YSRKADAPA",
                       "ANANTHAPURAMU": "ANANTAPUR", "BELAGAVI": "BELGAUM", "BALLARI": "BELLARY", "VIJAYAPURA": "BIJAPUR",
                       "KALABURAGI": "GULBARGA", "MYSURU": "MYSORE", "SHIVAMOGGA": "SHIMOGA", "TUMAKURU": "TUMKUR",
                       "CHIKKAMAGALURU": "CHIKMAGALUR", "BENGALURUURBAN": "BANGALORE", "BENGALURURURAL": "BANGALORERURAL",
                       "HOSHANGABAD": "NARMADAPURAM", "NARMADAPURAM": "HOSHANGABAD", "KOREA": "KORIYA", "GARIYABAND": "GARIABAND",
                       "BEMETARA": "BAMETARA", "KAWARDHAKABIRDHAM": "KABEERDHAM", "KUTCH": "KACHCHH", "DANG": "DANGS",
                       "AHMEDABAD": "AHMADABAD", "MEHSANA": "MAHESANA", "PANCHMAHAL": "PANCHMAHALS", "ARAVALLI": "ARVALLI",
                       "CHHOTAUDAIPUR": "CHHOTAUDEPUR", "SOUTHANDAMANS": "SOUTHANDAMAN", "DIBANGVALLEY": "UPPERDIBANGVALLEY",
                       "WESTKARBIANAGLONG": "WESTKARBIANGLONG", "SOUTHSALMARA": "SOUTHSALMARAMANKACHAR",
                       "DAKSHINBASTARDANTEWARA": "DAKSHINBASTARDANTEWADA", "BALESHWAR": "BALASORE", "SUNDARGARH": "SUNDERGARH",
                       "TIRUCHIRAPPALLI": "TIRUCHIRAPPALLI", "THOOTHUKKUDI": "THOOTHUKUDI", "KANNIYAKUMARI": "KANYAKUMARI"}
            cache, rows, matched = {}, [], 0
            for r in dd.itertuples():
                sk, dn = norm(r.state_key), norm(r.district)
                key = (sk, dn)
                if key not in cache:
                    cands = by_state.get(sk, {})
                    hit = cands.get(dn) or cands.get(RENAMED.get(dn, ""))
                    if hit is None and cands:
                        best = difflib.get_close_matches(dn, list(cands), n=1, cutoff=0.8)
                        hit = cands[best[0]] if best else None
                    cache[key] = hit
                mp = cache[key]
                matched += mp is not None
                rows.append([dmonths.index(r.period), r.state_key, re.sub(r"\s+", " ", str(r.district)).strip().title(), mp,
                             num(r.volume_in_mn, 2), num(r.value_in_cr, 2)])
            upi["districts"] = {"months": dmonths, "rows": rows}
            print(f"districts: {len(rows)} rows over {len(dmonths)} months, {matched} matched to map boundaries")
    # population for per-person figures (config/state_population.json, crore)
    popf = ROOT / "config" / "state_population.json"
    if "states" in upi and popf.exists():
        pop = {k: v for k, v in json.loads(popf.read_text(encoding="utf-8")).items() if not k.startswith("_")}
        upi["states"]["pop"] = {n: pop[n] for n in upi["states"]["names"] if n in pop}
        upi["states"]["pop_note"] = "population: National Commission on Population projections for 2026, approximate"
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
    types_by_key = {bank_key(name): (TYPE_ORDER.index(t) if t in TYPE_ORDER else 5) for name, t in types.items()}
    idx_by_key = {bank_key(name): i for name, i in bidx.items()}
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
        "upi": build_upi(types_by_key, idx_by_key),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size/1e6:.2f} MB): {len(months)} months, {len(banks)} banks, {len(rows)} rows")
    # page.html is the body fragment the Claude artifact viewer wraps itself; index.html is the same page
    # as a complete document for any ordinary web host or a local folder served over HTTP
    page = OUT.parent / "page.html"
    if page.exists():
        # the page fragment carries a data-URI icon for the artifact viewer; the full document links the real
        # icon files in <head> instead (favicon.svg / .ico / apple-touch-icon.png / manifest live in dashboard/)
        body = re.sub(r'<link rel="icon" href="data:[^"]*">\n?', '', page.read_text(encoding="utf-8"))
        html = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
                '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
                '<link rel="icon" href="favicon.ico" sizes="16x16 32x32 48x48">\n'
                '<link rel="icon" href="favicon.svg" type="image/svg+xml">\n'
                '<link rel="apple-touch-icon" href="apple-touch-icon.png">\n'
                '<link rel="manifest" href="manifest.webmanifest">\n'
                '<meta name="theme-color" content="#8a1c3b">\n'
                '<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}'
                'img{max-width:100%}[hidden]{display:none!important}</style>\n</head>\n<body>\n'
                + body + '\n</body>\n</html>\n')
        (OUT.parent / "index.html").write_text(html, encoding="utf-8")
        print("wrote", OUT.parent / "index.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
