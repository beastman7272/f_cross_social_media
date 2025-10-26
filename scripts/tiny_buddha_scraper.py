import os
import feedparser
import re
import html
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

load_dotenv()

# ==== CONFIG ====
FEED_URL = "https://tinybuddha.com/feed/"
SPREADSHEET_ID = os.getenv("GSPREAD_SHEET_ID", "").strip()
SHEET_NAME = "Tiny_Buddha"

# Google Sheets auth
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
service_account_info = os.getenv("GOOGLE_SA_JSON")
if not service_account_info:
    raise ValueError("GOOGLE_SA_JSON not found. Ensure environment variable is set.")

creds = Credentials.from_service_account_info(
    eval(service_account_info),
    scopes=SCOPES
)
client = gspread.authorize(creds)
spreadsheet = client.open_by_key(SPREADSHEET_ID)
sheet = spreadsheet.worksheet(SHEET_NAME)

# Fetch existing URLs to avoid duplicates
existing_urls = set(row[4] for row in sheet.get_all_values()[1:] if len(row) > 4)

# Parse feed
feed = feedparser.parse(FEED_URL)

def extract_first_strong(html_block):
    """Extract first <strong>...</strong> text."""
    match = re.search(r"<strong>(.*?)</strong>", html_block, re.DOTALL | re.IGNORECASE)
    if not match:
        return None
    text = re.sub("<.*?>", "", match.group(1))
    return html.unescape(text.strip())

new_rows = []
for entry in feed.entries:
    url = entry.link
    if url in existing_urls:
        continue

    raw_html = entry.get("description", "") or entry.get("content", [{}])[0].get("value", "")
    quote = extract_first_strong(raw_html)
    author = entry.get("author", "Unknown")
    date = entry.get("published", "")
    title = entry.get("title", "")
    source = "Tiny Buddha"

    new_rows.append([date, source, quote or title, author, url, "Needs Review"])

if new_rows:
    sheet.append_rows(new_rows)
    print(f"✅ Added {len(new_rows)} new Tiny Buddha entries.")
else:
    print("No new Tiny Buddha entries found.")
