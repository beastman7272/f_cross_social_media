import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from datetime import datetime, timezone
import os

BASE_URLS = ["https://www.mindbodygreen.com/financial-wellness/"]

KEYWORDS = ["mindset", "confidence","confident", "growth", "calm", "stress", "purpose", "reflection", "self", 
"focus", "peace", "financial", "wellness", "wealth", "investing", "saving", "budgeting", "debt", "retirement", 
"habits","spending", "mindset", "emotion","freedom", "independence", "security", "stability"]

def get_articles(url):
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
    except Exception as e:
        print(f"⚠️ Error fetching {url}: {e}")
        return []

    soup = BeautifulSoup(res.text, "html.parser")
    cards = soup.select("a[href*='/articles/']")
    results = []

    for c in cards:
        link = c.get("href")
        if not link:
            continue
        if not link.startswith("http"):
            link = f"https://www.mindbodygreen.com{link}"
        title = c.get_text(strip=True)
        if not title:
            continue
        if any(k in title.lower() for k in KEYWORDS):
            results.append((title, link))
    return results


def generate_feed():
    fg = FeedGenerator()
    fg.title("MindBodyGreen Motivation Feed")
    fg.link(href="https://www.mindbodygreen.com", rel="alternate")
    fg.description("Filtered mindset & self-care articles from MindBodyGreen.")
    fg.language("en")

    all_articles = []
    for url in BASE_URLS:
        all_articles.extend(get_articles(url))

    # Deduplicate by link
    seen = set()
    for title, link in all_articles:
        if link in seen:
            continue
        seen.add(link)
        fe = fg.add_entry()
        fe.title(title)
        fe.link(href=link)
        fe.pubDate(datetime.now(timezone.utc).isoformat())

    output_dir = "feeds"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "mindbodygreen_feed.xml")
    fg.rss_file(output_path)
    print(f"✅ Feed generated with {len(seen)} entries at {output_path}")

if __name__ == "__main__":
    generate_feed()
