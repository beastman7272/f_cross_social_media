import os
import requests
from bs4 import BeautifulSoup
import hashlib
import time
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# -----------------------
# CONFIGURATION
# -----------------------

TAGS = [
    "financial-independence",
    "confidence",
    "growth",
    "leadership",
    "self-care",
    "money-mindset",
    "empowerment"
]

BASE_URL = "https://www.goodreads.com/quotes/tag/"
MAX_PAGES = 5
MIN_LEN, MAX_LEN = 60, 250
SOURCE = "Goodreads"
SLEEP_TIME = (5, 8)  # polite delay range in seconds

# Google Sheet configuration (same as ZenQuotes)
SHEET_NAME = "Goodreads"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
CREDS_FILE = "sa.json"  # same service account file as ZenQuotes
SPREADSHEET_ID = os.getenv("GSPREAD_SHEET_ID", "").strip()  # same sheet as ZenQuotes

# -----------------------
# HELPER FUNCTIONS
# -----------------------

def get_google_sheet():
    """Authenticate and return the Goodreads worksheet."""
    creds = Credentials.from_service_account_file("sa.json", scopes=SCOPES)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID)
    try:
        ws = sheet.worksheet(SHEET_NAME)
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title=SHEET_NAME, rows="1000", cols="8")
        ws.append_row(["timestamp", "source", "tag", "quote", "author", "url", "char_count", "dedupe_key"])
    return ws


def fetch_page(url):
    """Fetch HTML from a Goodreads tag page."""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; BillEastmanAI-Scraper/1.0)"}
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.text


def parse_quotes(html, tag):
    """Extract quotes and authors from Goodreads HTML."""
    soup = BeautifulSoup(html, "html.parser")
    quotes_data = []

    quote_divs = soup.find_all("div", class_="quoteText")
    for div in quote_divs:
        # Extract text and author
        full_text = div.get_text(strip=True, separator=" ")
        parts = full_text.split("―")
        quote = parts[0].strip("“”\"' ").replace("\n", " ")
        author = parts[1].split(",")[0].strip() if len(parts) > 1 else "Unknown"

        # Clean up quote
        if quote.endswith("..."):
            quote = quote[:-3].strip()

        quote = " ".join(quote.split())  # collapse whitespace
        if not (MIN_LEN <= len(quote) <= MAX_LEN):
            continue

        quotes_data.append({
            "tag": tag,
            "quote": quote,
            "author": author,
            "url": f"{BASE_URL}{tag}",
            "char_count": len(quote)
        })

    return quotes_data


def compute_key(quote, author):
    """Return hash-based dedupe key."""
    normalized = f"{quote.strip().lower()}|{author.strip().lower()}"
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


def dedupe(new_quotes, existing_keys):
    """Filter out quotes already in sheet."""
    unique = []
    for q in new_quotes:
        key = compute_key(q["quote"], q["author"])
        if key not in existing_keys:
            q["dedupe_key"] = key
            unique.append(q)
    return unique


def get_existing_keys(ws):
    """Return set of existing dedupe keys from the sheet."""
    try:
        col = ws.col_values(8)[1:]  # skip header
        return set(col)
    except Exception:
        return set()


def write_to_sheets(ws, quotes):
    """Append quotes to Google Sheet."""
    rows = []
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    for q in quotes:
        rows.append([
            timestamp,
            SOURCE,
            q["tag"],
            q["quote"],
            q["author"],
            q["url"],
            q["char_count"],
            q["dedupe_key"]
        ])
    if rows:
        ws.append_rows(rows, value_input_option="USER_ENTERED")


# -----------------------
# MAIN SCRAPER
# -----------------------

def main():
    ws = get_google_sheet()
    existing_keys = get_existing_keys(ws)

    total_added = 0
    for tag in TAGS:
        tag_total = 0
        print(f"\nScraping tag: {tag}")
        for page in range(1, MAX_PAGES + 1):
            url = f"{BASE_URL}{tag}?page={page}"
            try:
                html = fetch_page(url)
                quotes = parse_quotes(html, tag)
                new_quotes = dedupe(quotes, existing_keys)
                if new_quotes:
                    write_to_sheets(ws, new_quotes)
                    existing_keys.update(q["dedupe_key"] for q in new_quotes)
                    tag_total += len(new_quotes)
                time.sleep(SLEEP_TIME[0])  # polite delay
            except Exception as e:
                print(f"Error on {url}: {e}")
                continue

        print(f"Tag '{tag}': added {tag_total} new quotes")
        total_added += tag_total

    print(f"\n✅ Done. Total new quotes added: {total_added}")


if __name__ == "__main__":
    main()
