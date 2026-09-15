"""Crawl RBI 'Bankwise ATM/POS/Card Statistics' pages (ATMView.aspx?atmid=N)
and build an index of every monthly release with its Excel/PDF links."""
import re, csv, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import requests

BASE = "https://rbi.org.in/scripts/ATMView.aspx?atmid={}"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"}
OUT = Path(__file__).resolve().parent.parent / "data" / "index.csv"

MONTHS = {m: i for i, m in enumerate(
    ["january","february","march","april","may","june","july","august","september","october","november","december"], 1)}

def parse(atmid, html):
    rec = {"atmid": atmid, "label": "", "year": "", "month": "", "xls_url": "", "xls_size": "", "pdf_url": "", "pdf_size": "", "has_html_table": 0, "revised": 0}
    m = re.search(r"alt='(?:Document|PDF) - ([^']*)'", html)
    if m:
        rec["label"] = m.group(1).strip()
    else:
        # fall back to the page-level list entry text if present
        m = re.search(r"Bank-?wise ATM/POS/Card Statistics\s*-\s*([A-Za-z]+\s*,?\s*\d{4}[^<\"']*)", html)
        if m:
            rec["label"] = "Bank-wise ATM/POS/Card Statistics - " + m.group(1).strip()
    clean = re.sub(r"<[^>]+>", "", rec["label"])
    rec["revised"] = 1 if "revised" in clean.lower() else 0
    clean = re.sub(r"\(.*?\)", "", clean)
    tail = clean.split(" - ", 1)[-1] if " - " in clean else clean
    lm = re.search(r"([A-Za-z]+)[\s,\-]*(\d{4})", tail)
    if lm:
        mon = lm.group(1).lower().replace("jaunary", "january")
        if mon in MONTHS:
            rec["month"] = MONTHS[mon]
            rec["year"] = int(lm.group(2))
    rec["label"] = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", rec["label"])).strip()
    x = re.search(r"href='(https://rbidocs\.rbi\.org\.in/rdocs/ATM/DOCs/[^']+)'", html, re.I)
    if x:
        rec["xls_url"] = x.group(1)
        s = re.search(r"id='SDOC_[^']+'[^>]*>([^<]+)<", html)
        rec["xls_size"] = s.group(1).strip() if s else ""
    p = re.search(r"href='(https://rbidocs\.rbi\.org\.in/rdocs/ATM/PDFs/[^']+)'", html, re.I)
    if p:
        rec["pdf_url"] = p.group(1)
        s = re.search(r"id='SPDF_[^']+'[^>]*>([^<]+)<", html)
        rec["pdf_size"] = s.group(1).strip() if s else ""
    rec["has_html_table"] = 1 if re.search(r'class="tablebg"[^>]*>\s*<tr', html) and html.count("<tr") > 30 else 0
    return rec

def fetch(atmid, sess, tries=3):
    for t in range(tries):
        try:
            r = sess.get(BASE.format(atmid), headers=UA, timeout=60)
            if r.status_code == 200:
                return atmid, r.text
        except Exception as e:
            err = e
        time.sleep(2 * (t + 1))
    return atmid, ""

def main(lo=1, hi=220, workers=6):
    sess = requests.Session()
    recs = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(fetch, i, sess) for i in range(lo, hi + 1)]
        for f in as_completed(futs):
            atmid, html = f.result()
            if html:
                recs[atmid] = parse(atmid, html)
            else:
                recs[atmid] = {"atmid": atmid, "label": "FETCH_FAILED"}
            print(atmid, recs[atmid].get("label"), recs[atmid].get("xls_url", "")[-12:], flush=True)
    rows = [recs[k] for k in sorted(recs)]
    keys = ["atmid","label","year","month","revised","xls_url","xls_size","pdf_url","pdf_size","has_html_table"]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in keys})
    print("wrote", OUT, len(rows))

if __name__ == "__main__":
    lo = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    hi = int(sys.argv[2]) if len(sys.argv) > 2 else 220
    main(lo, hi)
