#!/usr/bin/env python3
import os, json, re, csv, hashlib, datetime, pathlib
from typing import List, Dict, Any
import requests

# ---------- Config ----------
BASE_URL = "https://zenquotes.io/api/quotes"
SHEET_ID = os.getenv("GSPREAD_SHEET_ID", "").strip()
SHEET_NAME = os.getenv("SHEET_NAME", "Content Bank")

# CSV output path in repo (intermediate store)
today = datetime.datetime.now()
csv_dir = pathlib.Path("data")
csv_dir.mkdir(parents=True, exist_ok=True)
csv_path = csv_dir / f"zenquotes_{today.strftime('%Y-%m')}.csv"

# Google Sheets auth via gspread
USE_SHEETS = bool(SHEET_ID)
GOOGLE_SA_JSON = os.getenv("GOOGLE_SA_JSON", "")

# ---------- Helpers ----------
def normalize_text(q: str) -> str:
    # Trim whitespace, leading/trailing quotes/dashes
    q = q.strip()
    q = re.sub(r'^[\s"“”\'‘’\-–—]+', '', q)
    q = re.sub(r'[\s"“”\'‘’\-–—]+$', '', q)
    q = re.sub(r'\s+', ' ', q)
    return q.strip()

def make_hash(quote: str, author: str) -> str:
    key = (normalize_text(quote).lower() + "||" + (author or "").lower()).encode("utf-8")
    return hashlib.sha256(key).hexdigest()

def fetch_quotes() -> List[Dict[str, Any]]:
    resp = requests.get(BASE_URL, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"API error: {data.get('message')}")
    return data if isinstance(data, list) else []

def light_filter(item: Dict[str, Any]) -> bool:
    # Keep if char count between ~60–220
    q = item.get("q", "") or ""
    c_raw = item.get("c", "")
    try:
        c = int(c_raw)
    except Exception:
        c = len(q)
    return 60 <= c <= 220

def to_sheet_row(item: Dict[str, Any]) -> List[str]:
    now_iso = datetime.datetime.now().isoformat(timespec="seconds")
    q = normalize_text(item.get("q", "") or "")
    a = (item.get("a", "") or "").strip()
    h = item.get("h", "") or ""
    return [
        now_iso,                       # Date Added
        "ZenQuotes API",               # Source
        q,                             # Quote
        a,                             # Author
        "https://zenquotes.io/",       # URL
        "Needs Review",                # Status
        "",                            # Notes
        h,                             # HTML (optional)
        "Inspirational quotes provided by ZenQuotes API"  # Attribution
    ]

def ensure_headers_in_csv(path: pathlib.Path):
    if not path.exists():
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Date Added","Source","Quote","Author","URL","Status","Notes","HTML","Attribution"
            ])

def write_csv_rows(path: pathlib.Path, rows: List[List[str]]):
    ensure_headers_in_csv(path)
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows)

def append_to_sheet(rows: List[List[str]]):
    # Lazy import to avoid dependency if not used
    import gspread
    from google.oauth2.service_account import Credentials

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    info = json.loads(GOOGLE_SA_JSON)
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    client = gspread.authorize(creds)

    sh = client.open_by_key(SHEET_ID)
    try:
        ws = sh.worksheet(SHEET_NAME)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=SHEET_NAME, rows="1000", cols="9")
        ws.append_row(["Date Added","Source","Quote","Author","URL","Status","Notes","HTML","Attribution"])
    ws.append_rows(rows, value_input_option="RAW")

# ---------- Main ----------
def main():
    # Fetch quotes from API
    try:
        batch = fetch_quotes()
    except Exception as e:
        print(f"[warn] fetch failed: {e}")
        batch = []
    
    # Normalize and filter quotes
    filtered = []
    for it in batch:
        it = dict(it)  # shallow copy
        it["q"] = normalize_text(it.get("q", "") or "")
        it["a"] = (it.get("a", "") or "").strip()
        if it["q"] and light_filter(it):
            filtered.append(it)
    
    # Deduplicate by normalized quote+author
    seen = set()
    deduped = []
    for it in filtered:
        h = make_hash(it["q"], it.get("a", ""))
        if h not in seen:
            seen.add(h)
            deduped.append(it)

    # Prepare rows
    rows = [to_sheet_row(it) for it in deduped]

    # Write CSV in repo (monthly file)
    write_csv_rows(csv_path, rows)
    print(f"[info] wrote {len(rows)} rows to {csv_path}")

    # Append to Google Sheet
    if USE_SHEETS and GOOGLE_SA_JSON:
        try:
            append_to_sheet(rows)
            print(f"[info] appended {len(rows)} rows to Google Sheet {SHEET_ID} / {SHEET_NAME}")
        except Exception as e:
            print(f"[warn] could not append to Google Sheet: {e}")
    else:
        print("[info] Sheets disabled or missing credentials; skipped append.")

if __name__ == "__main__":
    main()
