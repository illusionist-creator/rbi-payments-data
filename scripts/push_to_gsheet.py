"""Push the processed CSVs to a Google Sheet so Tableau Public can auto-refresh from it.

    python scripts/push_to_gsheet.py            # push every tab listed in config/gsheet.json
    python scripts/push_to_gsheet.py --check    # only verify credentials + sheet access, write nothing

Setup (one time) is described in README.md: a Google Cloud service account whose JSON key is saved at
secrets/service_account.json, and a Google Sheet shared with that service account as Editor.
"""
import json, sys, time
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "gsheet.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]


def load_config():
    if not CONFIG.exists():
        sys.exit(f"missing {CONFIG} - copy config/gsheet.example.json to gsheet.json and fill it in")
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    cred = ROOT / cfg.get("credentials", "secrets/service_account.json")
    if not cred.exists():
        sys.exit(f"missing service-account key {cred} - see README.md, section 'Google Sheets'")
    cfg["_cred_path"] = cred
    return cfg


def client(cfg):
    import gspread
    from google.oauth2.service_account import Credentials
    creds = Credentials.from_service_account_file(str(cfg["_cred_path"]), scopes=SCOPES)
    return gspread.authorize(creds), creds.service_account_email


def open_or_create(gc, cfg, sa_email):
    if cfg.get("spreadsheet_id"):
        try:
            return gc.open_by_key(cfg["spreadsheet_id"]), False
        except Exception as e:
            sys.exit(f"cannot open spreadsheet {cfg['spreadsheet_id']}: {e}\n"
                     f"share the sheet with {sa_email} as Editor, or clear spreadsheet_id to let the script create one")
    sh = gc.create(cfg.get("spreadsheet_title", "RBI ATM_POS_CARDS_ALL"))
    for who in cfg.get("share_with", []):
        sh.share(who, perm_type="user", role="writer", notify=False)
    cfg["spreadsheet_id"] = sh.id
    CONFIG.write_text(json.dumps({k: v for k, v in cfg.items() if not k.startswith("_")}, indent=2), encoding="utf-8")
    return sh, True


def frame_to_values(csv_path):
    df = pd.read_csv(csv_path)
    for c in df.columns:
        if c.endswith("_date"):
            df[c] = pd.to_datetime(df[c]).dt.strftime("%Y-%m-%d")
    df = df.astype(object).where(df.notna(), "")
    return [list(df.columns)] + df.values.tolist()


def push_tab(sh, title, csv_path, chunk=4000):
    values = frame_to_values(csv_path)
    nrows, ncols = len(values), len(values[0])
    try:
        ws = sh.worksheet(title)
        ws.clear()
        ws.resize(rows=nrows, cols=ncols)
    except Exception:
        ws = sh.add_worksheet(title=title, rows=nrows, cols=ncols)
    for start in range(0, nrows, chunk):          # chunked so no single request gets too large
        block = values[start:start + chunk]
        ws.update(range_name=f"A{start + 1}", values=block, value_input_option="USER_ENTERED")
        time.sleep(0.5)                             # stay well inside the 60 writes/minute quota
    ws.freeze(rows=1)
    return nrows - 1, ncols


def main(check_only=False):
    cfg = load_config()
    gc, sa_email = client(cfg)
    sh, created = open_or_create(gc, cfg, sa_email)
    print(f"{'created' if created else 'opened'} spreadsheet: {sh.url}")
    if check_only:
        print("access OK; tabs present:", [w.title for w in sh.worksheets()])
        return 0
    for tab, rel in cfg["tabs"].items():
        rows, cols = push_tab(sh, tab, ROOT / rel)
        print(f"  {tab}: {rows} rows x {cols} cols from {rel}")
    # drop the default empty 'Sheet1' that comes with a freshly created spreadsheet
    for ws in sh.worksheets():
        if ws.title == "Sheet1" and ws.title not in cfg["tabs"] and len(sh.worksheets()) > 1:
            sh.del_worksheet(ws)
    print("done:", sh.url)
    return 0


if __name__ == "__main__":
    sys.exit(main(check_only="--check" in sys.argv))
