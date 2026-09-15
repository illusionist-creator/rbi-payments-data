"""Collect NPCI's UPI ecosystem statistics (https://www.npci.org.in/product/ecosystem-statistics/upi).

The page is a React app fed by /api/ecosystem-statistics/get-statistics, one call per tab and month.
NPCI's edge blocks Python's HTTP stack by TLS fingerprint but accepts curl with Chrome headers, so
every request goes through curl. Raw JSON is kept per tab/month under data/npci/raw/, and one CSV per
tab is written to data/processed/upi_<tab>.csv.

    python scripts/npci_upi.py            # fetch anything missing (plus re-check the last 3 months), rebuild CSVs
    python scripts/npci_upi.py --rebuild  # only rebuild the CSVs from the raw JSON already on disk
"""
import csv, json, shutil, subprocess, sys, time, datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "npci" / "raw"
OUT = ROOT / "data" / "processed"
API = "https://www.npci.org.in/api/ecosystem-statistics/get-statistics"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
FIRST = (2016, 4)                      # UPI went live in April 2016
RECHECK_LAST = 3                       # months always re-fetched (NPCI revises recent months)
# (tab_name, type_name, short name used for files)
SERIES = [
    ("upi-apps", None, "apps"),
    ("p2p-and-p2m-transactions", None, "p2p_p2m"),
    ("top50-member", "remitter", "remitter_banks"),
    ("top50-member", "beneficiary", "beneficiary_banks"),
    ("top-15-psps", "payer", "payer_psp"),
    ("top-15-psps", "payee", "payee_psp"),
    ("mcc", "top-mccs", "mcc"),
    ("statewise-statistic", None, "statewise"),
    ("chargeback", None, "chargeback"),
    ("top-50-mem-vol-val", None, "member_vol_val"),
]
META = {"id", "created_at", "updated_at", "published_at", "created_by_id", "updated_by_id", "locale",
        "localizations", "publishedAt", "createdAt", "updatedAt", "srno", "sr_no", "month_value",
        "product_name", "tab_name", "year", "month"}
HEADERS = [
    "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept: application/json, text/plain, */*", "Accept-Language: en-US,en;q=0.9",
    "Referer: https://www.npci.org.in/product/ecosystem-statistics/upi",
    'sec-ch-ua: "Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
    "sec-ch-ua-mobile: ?0", 'sec-ch-ua-platform: "Windows"',
    "Sec-Fetch-Dest: empty", "Sec-Fetch-Mode: cors", "Sec-Fetch-Site: same-origin",
]
CURL = shutil.which("curl") or shutil.which("curl.exe")


def month_iter(start=FIRST, end=None):
    y, m = start
    ey, em = end or (dt.date.today().year, dt.date.today().month)
    while (y, m) <= (ey, em):
        yield y, m
        m += 1
        if m > 12:
            y, m = y + 1, 1


def rows_of(d):
    """NPCI returns a list of rows, except tables with merged cells (MCC) which wrap it in a dict."""
    r = d.get("results")
    if isinstance(r, dict):
        r = r.get("tableDetail") or next((v for v in r.values() if isinstance(v, list)), [])
    return list(r or [])


def fetch(tab, type_name, year, month, size=1000, tries=3):
    q = f"product_name=UPI&tab_name={tab}" + (f"&type_name={type_name}" if type_name else "") + \
        f"&year={year}&month={MONTHS[month-1]}&page_no=1&sort_by=asc&size={size}&locale=en"
    cmd = [CURL, "-s", "--compressed", "--max-time", "60"] + sum([["-H", h] for h in HEADERS], []) + [API + "?" + q]
    for t in range(tries):
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        try:
            j = json.loads(r.stdout)
            d = j.get("data") or {}
            if not isinstance(d, dict):
                return None
            rows = rows_of(d)
            total = d.get("totalCount") or 0
            if total and len(rows) < total:          # server caps a page at 500 rows: walk the rest
                page = 2
                while len(rows) < total and page < 50:
                    cmd2 = cmd[:-1] + [API + "?" + q.replace("page_no=1", f"page_no={page}")]
                    r2 = subprocess.run(cmd2, capture_output=True, text=True, encoding="utf-8", errors="replace")
                    more = rows_of((json.loads(r2.stdout).get("data") or {}))
                    if not more:
                        break
                    rows += more
                    page += 1
            return {"tab": tab, "type": type_name, "year": year, "month": month, "total": total,
                    "title": (d.get("table_headers") or {}).get("main_header_title"),
                    "headers": (d.get("table_headers") or {}).get("headers"),
                    "file": d.get("fileUrl"), "results": rows} if total else None
        except (json.JSONDecodeError, AttributeError):
            time.sleep(3 * (t + 1))
    raise RuntimeError(f"NPCI API failed for {tab}/{type_name} {year}-{month:02d}: {r.stdout[:120]!r}")


def raw_path(short, y, m):
    return RAW / short / f"{y:04d}-{m:02d}.json"


def collect():
    """Fetch months not on disk (and re-check the latest ones). Returns the list of new/changed files."""
    if not CURL:
        raise SystemExit("curl is required for NPCI (their edge blocks Python's TLS fingerprint)")
    today = dt.date.today()
    recheck = {(y, m) for y, m in month_iter((today.year - 1, today.month))}
    recheck = sorted(recheck)[-RECHECK_LAST:]
    changed = []
    for tab, typ, short in SERIES:
        have = {tuple(int(x) for x in p.stem.split("-")) for p in (RAW / short).glob("*.json")}
        last_have = max(have) if have else None
        for y, m in month_iter():
            # skip months that are on disk, and gaps before the first stored month once we have data
            if (y, m) in have and (y, m) not in recheck:
                continue
            if last_have and (y, m) < last_have and (y, m) not in have and (y, m) < recheck[0]:
                continue                                   # a permanent gap in NPCI's archive
            rec = fetch(tab, typ, y, m)
            if rec is None:
                continue
            p = raw_path(short, y, m)
            p.parent.mkdir(parents=True, exist_ok=True)
            new = json.dumps(rec, ensure_ascii=False, sort_keys=True)
            if not p.exists() or p.read_text(encoding="utf-8") != new:
                p.write_text(new, encoding="utf-8")
                changed.append(p.name.replace(".json", "") + " " + short)
            time.sleep(0.25)
        print(f"{short}: {len(list((RAW / short).glob('*.json')))} months on disk", flush=True)
    return changed


def to_num(v):
    if v is None:
        return ""
    s = str(v).strip().replace(",", "")
    if s in ("", "-", "NA", "N/A", "nil", "Nil"):
        return ""
    if s.endswith("%"):
        s = s[:-1]
    try:
        f = float(s)
        return int(f) if f.is_integer() and "." not in s else f
    except ValueError:
        return str(v).strip()


def build_csvs():
    OUT.mkdir(parents=True, exist_ok=True)
    summary = {}
    for tab, typ, short in SERIES:
        files = sorted((RAW / short).glob("*.json"))
        if not files:
            continue
        rows, cols = [], []
        for p in files:
            rec = json.loads(p.read_text(encoding="utf-8"))
            period = p.stem
            for r in rec["results"]:
                out = {"period": period}
                for k, v in r.items():
                    if k in META or k.startswith("__"):
                        continue
                    out[k] = to_num(v)
                    if k not in cols:
                        cols.append(k)
                rows.append(out)
        with (OUT / f"upi_{short}.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["period"] + cols, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        summary[short] = (len(files), files[0].stem, files[-1].stem, len(rows))
    for k, (n, a, b, r) in summary.items():
        print(f"  upi_{k}.csv: {n} months {a}..{b}, {r} rows")
    return summary


def main(rebuild_only=False):
    changed = [] if rebuild_only else collect()
    build_csvs()
    print(f"npci: {len(changed)} new/changed month files")
    return changed


if __name__ == "__main__":
    main(rebuild_only="--rebuild" in sys.argv)
