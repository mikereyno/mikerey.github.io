import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from email.utils import format_datetime
import xml.etree.ElementTree as ET
import json
import re

SITE = "https://houseofheat.co"
NIKE_PAGE = f"{SITE}/nike"
FEED_FILE = "nike.xml"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (RSS Feed Reader)"
}

session = requests.Session()
session.headers.update(HEADERS)


def get_article_details(url):
    """Get the real title, publication date and featured image."""

    try:
        response = session.get(url, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Better article title
        title = None

        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(" ", strip=True)

        if not title:
            og_title = soup.find("meta", property="og:title")
            if og_title:
                title = og_title.get("content")

        # Featured image
        image = None

        og_image = soup.find("meta", property="og:image")
        if og_image:
            image = og_image.get("content")

        if not image:
            twitter_image = soup.find("meta", attrs={"name": "twitter:image"})
            if twitter_image:
                image = twitter_image.get("content")

        # Publication date
        published = None

        # Open Graph
        meta_date = soup.find("meta", property="article:published_time")
        if meta_date:
            published = meta_date.get("content")

        # JSON-LD
        if not published:
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(script.string or script.get_text())

                    objects = data if isinstance(data, list) else [data]

                    for obj in objects:
                        if isinstance(obj, dict):
                            if obj.get("datePublished"):
                                published = obj["datePublished"]
                                break

                            if obj.get("@graph"):
                                for item in obj["@graph"]:
                                    if isinstance(item, dict) and item.get("datePublished"):
                                        published = item["datePublished"]
                                        break

                        if published:
                            break

                except Exception:
                    pass

        # House of Heat's visible "Date:2026.08.14" format
        if not published:
            text = soup.get_text(" ", strip=True)
            match = re.search(r"Date:\s*(\d{4})\.(\d{2})\.(\d{2})", text)

            if match:
                published = f"{match.group(1)}-{match.group(2)}-{match.group(3)}T00:00:00+00:00"

        # Final fallback
        if not published:
            published = datetime.now(timezone.utc).isoformat()

        try:
            date = datetime.fromisoformat(published.replace("Z", "+00:00"))

            if date.tzinfo is None:
                date = date.replace(tzinfo=timezone.utc)

        except Exception:
            date = datetime.now(timezone.utc)

        return {
            "title": title,
            "url": url,
            "image": image,
            "date": date
        }

    except Exception as e:
        print(f"Could not read {url}: {e}")
        return None


# ---------------------------------------------------------
# Get Nike article links
# ---------------------------------------------------------

response = session.get(NIKE_PAGE, timeout=30)
response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

urls = []
seen = set()

for link in soup.find_all("a", href=True):

    href = link["href"]

    if href.startswith("/nike/") and href != "/nike/":

        url = SITE + href

        if url not in seen:
            seen.add(url)
            urls.append(url)

    if len(urls) >= 30:
        break


# ---------------------------------------------------------
# Build article information
# ---------------------------------------------------------

articles = []

for url in urls:

    print(f"Checking {url}")

    article = get_article_details(url)

    if article and article["title"]:
        articles.append(article)


# Newest first
articles.sort(
    key=lambda x: x["date"],
    reverse=True
)


# ---------------------------------------------------------
# Create RSS feed
# ---------------------------------------------------------

rss = ET.Element(
    "rss",
    {
        "version": "2.0",
        "xmlns:media": "http://search.yahoo.com/mrss/"
    }
)

channel = ET.SubElement(rss, "channel")

ET.SubElement(channel, "title").text = "House of Heat — Nike"
ET.SubElement(channel, "link").text = NIKE_PAGE
ET.SubElement(channel, "description").text = "Latest Nike news from House of Heat"
ET.SubElement(channel, "language").text = "en"

for article in articles:

    item = ET.SubElement(channel, "item")

    ET.SubElement(item, "title").text = article["title"]
    ET.SubElement(item, "link").text = article["url"]

    ET.SubElement(
        item,
        "guid",
        {"isPermaLink": "true"}
    ).text = article["url"]

    ET.SubElement(
        item,
        "pubDate"
    ).text = format_datetime(article["date"])

    # Featured image
    if article["image"]:

        ET.SubElement(
            item,
            "{http://search.yahoo.com/mrss/}content",
            {
                "url": article["image"],
                "medium": "image"
            }
    # Featured image
if article["image"]:

    image_url = article["image"]

    # Media RSS
    ET.SubElement(
        item,
        "{http://search.yahoo.com/mrss/}content",
        {
            "url": image_url,
            "medium": "image",
            "type": "image/jpeg"
        }
    )

    # Standard RSS enclosure
    ET.SubElement(
        item,
        "enclosure",
        {
            "url": image_url,
            "type": "image/jpeg",
            "length": "0"
        }
    )

    # Image inside description for readers that look there
    description = (
        f'<img src="{image_url}" alt="" />'
        f'<p>{article["title"]}</p>'
    )

    ET.SubElement(
        item,
        "description"
    ).text = description


# Write feed
tree = ET.ElementTree(rss)

tree.write(
    FEED_FILE,
    encoding="utf-8",
    xml_declaration=True
)

print(f"RSS feed updated with {len(articles)} Nike articles.")
