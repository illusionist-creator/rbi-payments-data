"""Parse every monthly RBI 'Bank-wise ATM/POS/Card Statistics' Excel file in data/raw/
into one tidy dataset. Handles the four layouts RBI has used since April 2011 and
normalises transaction values to Rs million."""
import re, sys, glob, os, warnings
from pathlib import Path
import pandas as pd
import numpy as np

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
RAW, OUT = ROOT / "data" / "raw", ROOT / "data" / "processed"
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]

# canonical metric order for each layout (columns immediately to the right of "Bank Name")
LAYOUTS = {
    "A14":  ["atm_onsite", "atm_offsite", "pos_online", "pos_offline",
             "cc_cards", "cc_atm_vol", "cc_pos_vol", "cc_atm_val", "cc_pos_val",
             "dc_cards", "dc_atm_vol", "dc_pos_vol", "dc_atm_val", "dc_pos_val"],
    "A16x": ["atm_online", "atm_offline", "atm_onsite", "atm_offsite", "pos_online", "pos_offline",
             "cc_cards", "cc_atm_vol", "cc_pos_vol", "cc_atm_val", "cc_pos_val",
             "dc_cards", "dc_atm_vol", "dc_pos_vol", "dc_atm_val", "dc_pos_val"],
    "B16":  ["atm_onsite", "atm_offsite", "pos_online", "pos_offline", "micro_atm", "bharat_qr",
             "cc_cards", "cc_atm_vol", "cc_pos_vol", "cc_atm_val", "cc_pos_val",
             "dc_cards", "dc_atm_vol", "dc_pos_vol", "dc_atm_val", "dc_pos_val"],
    "C26":  ["atm_onsite", "atm_offsite", "pos", "micro_atm", "bharat_qr", "upi_qr", "cc_cards", "dc_cards",
             "cc_pos_vol", "cc_pos_val", "cc_ecom_vol", "cc_ecom_val", "cc_other_vol", "cc_other_val",
             "cc_atm_vol", "cc_atm_val",
             "dc_pos_vol", "dc_pos_val", "dc_ecom_vol", "dc_ecom_val", "dc_other_vol", "dc_other_val",
             "dc_atm_vol", "dc_atm_val", "dc_cashpos_vol", "dc_cashpos_val"],
}
ALL_METRICS = list(dict.fromkeys(c for cols in LAYOUTS.values() for c in cols))
VAL_COLS = [c for c in ALL_METRICS if c.endswith("_val")]
TO_MILLION = {"million": 1.0, "lakh": 0.1, "crore": 10.0, "thousand": 0.001}
GROUP_RE = re.compile(
    r"^(scheduled commercial banks|public sector banks|nationalised banks|nationalized banks|"
    r"sbi (and|&) (its )?associates|state bank group|private sector banks|old private sector banks|"
    r"new private sector banks|foreign banks|payments? banks|small finance banks|"
    r"local area banks|others?)\s*\*?$", re.I)
TOTAL_RE = re.compile(r"^\s*(grand\s+)?total\s*\*?\s*$", re.I)
NULL_TOKENS = {"", "-", "--", "na", "n.a.", "nil", "#ref!", "#div/0!", "#n/a", "#value!"}


def norm(s):
    return re.sub(r"\s+", " ", str(s)).strip().lower()


def pick_sheet(xl, month):
    sheets = [s for s in xl.sheet_names if not s.lower().startswith("var")]
    cand = [s for s in sheets if MONTHS[month - 1] in s.lower()]
    for s in (cand + sheets):
        if xl.parse(s, header=None).shape[0] > 10:
            return s
    return sheets[0]


def to_num(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return np.nan
    if isinstance(v, (int, float, np.integer, np.floating)):
        return float(v)
    s = str(v).strip().replace(",", "").replace("₹", "")
    if s.lower() in NULL_TOKENS:
        return np.nan
    try:
        return float(s)
    except ValueError:
        return np.nan


def parse_file(path):
    base = os.path.basename(path)
    year, month = int(base[:4]), int(base[5:7])
    atmid = int(re.search(r"atmid(\d+)", base).group(1))
    xl = pd.ExcelFile(path)
    sheet = pick_sheet(xl, month)
    df = xl.parse(sheet, header=None)

    # header row = first row containing 'bank name'
    hdr = bc = None
    for i in range(min(15, len(df))):
        for j, v in enumerate(df.iloc[i]):
            if isinstance(v, str) and "bank name" in v.lower():
                hdr, bc = i, j
                break
        if hdr is not None:
            break
    if hdr is None:
        raise ValueError("no 'Bank Name' header found")

    # numbering row (1..N) within the next 7 rows
    numrow = None
    for i in range(hdr, min(hdr + 8, len(df))):
        vals = [to_num(v) for v in df.iloc[i, bc + 1:]]
        vals = [v for v in vals if not np.isnan(v)]
        if len(vals) >= 12 and vals == list(range(1, len(vals) + 1)):
            numrow = i
            break
    last_hdr = numrow if numrow is not None else hdr + 3
    htext = " | ".join(norm(v) for i in range(max(0, hdr - 1), last_hdr + 1)
                       for v in df.iloc[i] if isinstance(v, str))

    # layout detection
    if "upi qr" in htext:
        layout = "C26"
    elif "micro atm" in htext:
        layout = "B16"
    elif re.search(r"on-?line \| off-?line \| on-?site \| off-?site", htext):
        layout = "A16x"
    else:
        layout = "A14"
    metrics = LAYOUTS[layout]
    ncol = len(metrics)
    if numrow is not None:
        n_numbered = len([v for v in df.iloc[numrow, bc + 1:] if not np.isnan(to_num(v))])
        if n_numbered != ncol:
            raise ValueError(f"layout {layout} expects {ncol} cols but numbering row has {n_numbered}")

    # unit of the value columns: only look at header text within the mapped column range
    utext = " ".join(norm(v) for i in range(hdr, last_hdr + 1)
                     for v in df.iloc[i, bc + 1:bc + 1 + ncol] if isinstance(v, str))
    if re.search(r"rs\s*'?\s*000|thousand", utext):
        unit = "thousand"
    elif "lakh" in utext:
        unit = "lakh"
    elif "crore" in utext and not re.search(r"mili|milli", utext):
        unit = "crore"
    elif re.search(r"mili|milli|` mill", utext):
        unit = "million"
    elif year < 2019 or (year == 2019 and month < 7):
        unit = "million"          # a few early files omit the unit; RBI used Rs million throughout
    else:
        raise ValueError("cannot determine value unit from header: " + utext[:200])

    # data rows start right after the numbering row if there is one, else right after the
    # 'Bank Name' row (sub-header rows carry no numbers and are skipped by the n_ok test)
    data_start = numrow + 1 if numrow is not None else hdr + 1
    rows, group, total = [], None, None
    for i in range(data_start, len(df)):
        name = df.iat[i, bc]
        name_s = re.sub(r"\s+", " ", str(name)).strip() if isinstance(name, str) else ""
        left = [str(v).strip() for v in df.iloc[i, :bc] if isinstance(v, str) and str(v).strip()]
        nums = [to_num(v) for v in df.iloc[i, bc + 1:bc + 1 + ncol]]
        n_ok = sum(0 if np.isnan(v) else 1 for v in nums)
        label = name_s or (left[0] if left else "")
        if TOTAL_RE.match(label) or (not name_s and left and TOTAL_RE.match(left[-1])):
            # some files carry a 'Total' per bank group followed by a 'Grand Total';
            # keep the last one seen and stop only at an explicit grand total
            if n_ok >= ncol // 2:
                total = dict(zip(metrics, nums))
                if "grand" in label.lower():
                    break
            continue
        if not name_s and not left:
            continue
        if n_ok == 0 and (GROUP_RE.match(label) or re.search(r"banks?( in india)?\s*\*?$", label, re.I)):
            group = re.sub(r"\s*\*$", "", label)
            continue
        if n_ok == 0 or (numrow is not None and i == numrow) or not name_s:
            continue
        if len(name_s) > 60 or re.match(r"^\d+\s", name_s):
            continue      # footnote text that spilled into the bank column
        rec = {"bank_name_published": name_s, "bank_group": group}
        rec.update(zip(metrics, nums))
        rows.append(rec)
    if not rows:
        raise ValueError("no bank rows parsed")
    banks = pd.DataFrame(rows)

    meta = dict(file=base, atmid=atmid, year=year, month=month, sheet=sheet, layout=layout,
                value_unit_published=unit, n_banks=len(banks), has_total=total is not None)
    # validation: sum of banks vs published total, per metric
    checks = {}
    if total is not None:
        for m in metrics:
            s, t = banks[m].sum(skipna=True), total[m]
            if np.isnan(t):
                checks[m] = "no_total"
            elif abs(s - t) <= max(1.0, 0.005 * abs(t)):
                checks[m] = "ok"
            else:
                checks[m] = f"MISMATCH sum={s:.6g} total={t:.6g}"
    meta["n_mismatch"] = sum(1 for v in checks.values() if v.startswith("MISMATCH"))
    meta["mismatches"] = "; ".join(f"{k}: {v}" for k, v in checks.items() if v.startswith("MISMATCH"))[:400]

    period = f"{year:04d}-{month:02d}"
    banks.insert(0, "period", period)
    banks.insert(1, "atmid", atmid)
    banks["layout"] = layout
    banks["value_unit_published"] = unit
    tot = None
    if total is not None:
        tot = {"period": period, "atmid": atmid, "layout": layout, "value_unit_published": unit}
        tot.update(total)
    return meta, banks, tot


def add_million_cols(df):
    factor = df["value_unit_published"].map(TO_MILLION)
    for c in VAL_COLS:
        if c in df:
            df[c + "_mn"] = df[c] * factor
    return df


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    metas, frames, totals = [], [], []
    for path in sorted(glob.glob(str(RAW / "*.xls*"))):
        try:
            meta, banks, tot = parse_file(path)
            frames.append(banks)
            if tot:
                totals.append(tot)
        except Exception as e:
            meta = dict(file=os.path.basename(path), error=str(e))
            print("ERROR", meta["file"], e)
        metas.append(meta)
    log = pd.DataFrame(metas)
    log.to_csv(OUT / "parse_log.csv", index=False)

    all_banks = add_million_cols(pd.concat(frames, ignore_index=True))
    cols = ["period", "atmid", "layout", "value_unit_published", "bank_group", "bank_name_published"] + \
           [m for m in ALL_METRICS if m in all_banks] + [c + "_mn" for c in VAL_COLS if c in all_banks]
    all_banks = all_banks[cols]
    all_banks.to_csv(OUT / "bank_month_all_metrics_raw.csv", index=False)
    tdf = add_million_cols(pd.DataFrame(totals))
    tdf.to_csv(OUT / "national_totals_raw.csv", index=False)

    print(f"files parsed: {len(frames)}/{len(metas)}; bank-month rows: {len(all_banks)}; totals rows: {len(tdf)}")
    if "layout" in log:
        print("layouts:", log.groupby("layout").size().to_dict())
        print("units:", log.groupby("value_unit_published").size().to_dict())
        bad = log[log["n_mismatch"].fillna(0) > 0]
        print("files with sum-vs-total mismatches:", len(bad))
        for _, r in bad.iterrows():
            print("  ", r["file"], r["layout"], "|", str(r["mismatches"])[:300])
        nt = log[log["has_total"] == False]
        print("files with no Total row:", list(nt["file"]) if len(nt) else "none")
    return 0


if __name__ == "__main__":
    sys.exit(main())
