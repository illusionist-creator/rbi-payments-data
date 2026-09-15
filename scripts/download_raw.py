"""Download every monthly Excel (and optionally PDF) file listed in data/index.csv
into data/raw/, named YYYY-MM_atmid<N>.<ext>. Skips files already present."""
import csv, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "data" / "index.csv"
RAW = ROOT / "data" / "raw"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36",
      "Referer": "https://rbi.org.in/scripts/ATMView.aspx"}

def target_name(row, url):
    ext = url.rsplit(".", 1)[-1].lower()
    return f"{int(float(row['year'])):04d}-{int(float(row['month'])):02d}_atmid{row['atmid']}.{ext}"

def download(row, url, sess, tries=3):
    dest = RAW / target_name(row, url)
    if dest.exists() and dest.stat().st_size > 0:
        return dest, "exists"
    for t in range(tries):
        try:
            r = sess.get(url, headers=UA, timeout=120)
            if r.status_code == 200 and len(r.content) > 0:
                dest.write_bytes(r.content)
                return dest, f"ok {len(r.content)}"
            status = f"http {r.status_code}"
        except Exception as e:
            status = f"err {e}"
        time.sleep(2 * (t + 1))
    return dest, f"FAILED {status}"

def main(include_pdf=False, workers=4):
    RAW.mkdir(parents=True, exist_ok=True)
    rows = [r for r in csv.DictReader(INDEX.open(encoding="utf-8")) if r.get("xls_url") and r.get("year")]
    jobs = [(r, r["xls_url"]) for r in rows]
    if include_pdf:
        jobs += [(r, r["pdf_url"]) for r in rows if r.get("pdf_url")]
    sess = requests.Session()
    failed = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(download, r, u, sess): (r, u) for r, u in jobs}
        for f in as_completed(futs):
            dest, status = f.result()
            print(dest.name, status, flush=True)
            if status.startswith("FAILED"):
                failed.append((dest.name, status))
    print(f"done: {len(jobs)} jobs, {len(failed)} failed")
    for n, s in failed:
        print("  ", n, s)
    return 1 if failed else 0

if __name__ == "__main__":
    sys.exit(main(include_pdf="--pdf" in sys.argv))
