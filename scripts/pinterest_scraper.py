# pinterest_scraper.py
"""
Batch import Pinterest board data via RSS into Google Sheets.
Designed to match the ZenQuotes/Goodreads folder structure.
"""

import os
import datetime
import feedparser
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

load_dotenv()

# === CONFIGURATION ===
BOARD_FEEDS = {
    "Motivation-Mondays": "https://www.pinterest.com/billeastmanai/motivation-mondays.rss",
    "Design-Inspirations": "https://www.pinterest.com/billeastmanai/design-inspirations.rss",
}

SHEET_NAME = "Pinterest_Quotes"  # Tab name in your existing Google Sheet
SPREADSHEET_ID = os.getenv("GSPREAD_SHEET_ID")  # same env var as ZenQuotes/Goodreads

# === AUTHENTICATION ===
service_account_info = os.getenv("GOOGLE_SA_JSON")
if not service_account_info:
    raise ValueError("GOOGLE_SA_JSON not found. Ensure environment variable is set.")

creds = Credentials.from_service_account_info(
    eval(service_account_info),
    scopes=["https://www.googleapis.com/auth/spreadsheets"]
)
client = gspread.authorize(creds)
sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

# === UTILITY: APPEND ROW ===
def append_row(data):
    sheet.append_row(data, value_input_option="RAW")

# === MAIN FUNCTION ===
def fetch_pinterest_boards():
    new_rows = []
    today = datetime.date.today().isoformat()

    for board_name, feed_url in BOARD_FEEDS.items():
        print(f"📌 Processing board: {board_name}")
        print(f"🔗 Feed URL: {feed_url}")
        
        feed = feedparser.parse(feed_url)
        print(f"📊 Feed status: {feed.status if hasattr(feed, 'status') else 'Unknown'}")
        print(f"📝 Found {len(feed.entries)} entries")
        
        for entry in feed.entries:
            title = entry.get("title", "").strip()
            link = entry.get("link", "")
            published = entry.get("published", today)
            img_url = ""
            if "enclosures" in entry and len(entry.enclosures) > 0:
                img_url = entry.enclosures[0].get("href", "")
            elif "media_content" in entry:
                img_url = entry.media_content[0].get("url", "")
            new_rows.append(["Pinterest", board_name, title, img_url, link, published, ""])
            print(f"  ✓ Added: {title[:50]}...")
    
    # Append all new rows
    if new_rows:
        sheet.append_rows(new_rows, value_input_option="RAW")
        print(f"✅ Added {len(new_rows)} new Pinterest entries.")
    else:
        print("No new entries found.")

# === RUN ===
if __name__ == "__main__":
    fetch_pinterest_boards()
