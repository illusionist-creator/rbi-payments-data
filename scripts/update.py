"""One-shot updater: find any new monthly release on RBI's site, download it, re-parse
everything and rebuild the outputs. Safe to run as often as you like (idempotent).

    python scripts/update.py            # normal run
    python scripts/update.py --force    # rebuild outputs even if nothing new was found

Exit code 0 = ran fine (new data or not), 1 = something failed. A log line per run is
appended to data/update_log.txt so a scheduler can run it unattended.
"""
import csv, sys, json, datetime as dt
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import crawl_index, download_raw, parse_raw, build_outputs, build_dashboard   # noqa: E402

ROOT = HERE.parent
INDEX = ROOT / "data" / "index.csv"
MANIFEST = ROOT / "data" / "raw_manifest.json"     # raw filename -> RBI URL it was downloaded from
LOG = ROOT / "data" / "update_log.txt"


def push_sheet():
    """Push the rebuilt CSVs to Google Sheets if the one-time setup has been done; never fail the run."""
    cfg = ROOT / "config" / "gsheet.json"
    key = ROOT / "secrets" / "service_account.json"
    if not (cfg.exists() and key.exists()):
        print("google sheet push skipped: no secrets/service_account.json yet (see README.md)")
        return "not configured"
    try:
        import push_to_gsheet
        push_to_gsheet.main()
        return "ok"
    except SystemExit as e:
        print("google sheet push failed:", e)
        return f"FAILED ({e})"
    except Exception as e:
        print("google sheet push failed:", e)
        return f"FAILED ({type(e).__name__}: {e})"


def index_rows():
    if not INDEX.exists():
        return []
    with INDEX.open(encoding="utf-8") as fh:
        return [r for r in csv.DictReader(fh) if r.get("xls_url") and r.get("year")]


def main(force=False):
    before = {int(r["atmid"]) for r in index_rows()}
    hi = (max(before) if before else 0) + 12          # probe a year's worth of ids past the last known one
    crawl_index.main(1, hi)                           # rewrites data/index.csv (also picks up 'Revised' re-issues)
    rows = index_rows()
    new = sorted({int(r["atmid"]) for r in rows} - before)

    # RBI re-issues revised files under a new URL hash: drop the stale local copy so it is re-fetched
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    changed = []
    for r in rows:
        name = download_raw.target_name(r, r["xls_url"])
        if manifest.get(name) not in (None, r["xls_url"]):
            (download_raw.RAW / name).unlink(missing_ok=True)
            changed.append(name)
        manifest[name] = r["xls_url"]
    MANIFEST.write_text(json.dumps(manifest, indent=1, sort_keys=True))

    if download_raw.main():
        LOG.open("a").write(f"{dt.datetime.now():%Y-%m-%d %H:%M} FAIL download failures, outputs not rebuilt\n")
        return 1
    pushed = "skipped"
    if new or changed or force:
        parse_raw.main()
        build_outputs.main()
        build_dashboard.main()
        pushed = push_sheet()
    msg = f"new atmids={new or 'none'} revised={changed or 'none'} total_months={len(rows)} gsheet={pushed}"
    LOG.open("a").write(f"{dt.datetime.now():%Y-%m-%d %H:%M} OK {msg}\n")
    print(msg)
    return 0


if __name__ == "__main__":
    sys.exit(main(force="--force" in sys.argv))
