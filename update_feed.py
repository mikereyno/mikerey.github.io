import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from email.utils import format_datetime
import xml.etree.ElementTree as ET

SITE = "https://houseofheat.co"
NIKE_PAGE = f"{SITE}/nike"
FEED_FILE = "nike.xml"

headers = {
    "User-Agent": "Mozilla/5.0 (RSS Feed Reader)"
}

# Get the Nike page
response = requests.get(NIKE_PAGE, headers=headers, timeout=30)
response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

articles = []
seen = set()

# Find links to articles in the Nike section
for link in soup.find_all("a", href=True):
    href = link["href"]

    if href.startswith("/nike/") and href != "/nike/":
        url = SITE + href

        if url in seen:
            continue

        title = link.get_text(" ", strip=True)

        if not title or len(title) < 10:
            continue

        seen.add(url)
        articles.append((title, url))

    if len(articles) >= 30:
        break

# Create RSS feed
rss = ET.Element("rss", version="2.0")
channel = ET.SubElement(rss, "channel")

ET.SubElement(channel, "title").text = "House of Heat — Nike"
ET.SubElement(channel, "link").text = NIKE_PAGE
ET.SubElement(channel, "description").text = "Latest Nike news from House of Heat"
ET.SubElement(channel, "language").text = "en"

now = format_datetime(datetime.now(timezone.utc))

for title, url in articles:
    item = ET.SubElement(channel, "item")

    ET.SubElement(item, "title").text = title
    ET.SubElement(item, "link").text = url
    ET.SubElement(item, "guid", isPermaLink="true").text = url
    ET.SubElement(item, "pubDate").text = now

tree = ET.ElementTree(rss)
tree.write(FEED_FILE, encoding="utf-8", xml_declaration=True)

print(f"Created RSS feed with {len(articles)} Nike articles.")
