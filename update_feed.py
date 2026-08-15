import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from email.utils import format_datetime
import xml.etree.ElementTree as ET
import json
import html
import re
from urllib.parse import urlparse

SITE = "https://houseofheat.co"
NIKE_PAGE = SITE + "/nike"
FEED_FILE = "nike.xml"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

session = requests.Session()
session.headers.update(HEADERS)


def get_image_type(url):
    path = urlparse(url).path.lower()

    if ".png" in path:
        return "image/png"

    if ".webp" in path:
        return "image/webp"

    if ".gif" in path:
        return "image/gif"

    return "image/jpeg"


def get_article(url):
    try:
        response = session.get(url, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        title = None

        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(" ", strip=True)

        if not title:
            meta = soup.find("meta", property="og:title")
            if meta:
                title = meta.get("content")

        image = None

        meta = soup.find("meta", property="og:image")
        if meta:
            image = meta.get("content")

        if not image:
            meta = soup.find(
                "meta",
                attrs={"name": "twitter:image"}
            )
            if meta:
                image = meta.get("content")

        published = None

        meta = soup.find(
            "meta",
            property="article:published_time"
        )

        if meta:
            published = meta.get("content")

        if not published:
            for script in soup.find_all(
                "script",
                type="application/ld+json"
            ):
                try:
                    data = json.loads(
                        script.string or script.get_text()
                    )

                    objects = (
                        data if isinstance(data, list)
                        else [data]
                    )

                    for obj in objects:
                        if not isinstance(obj, dict):
                            continue

                        if obj.get("datePublished"):
                            published = obj["datePublished"]
                            break

                        graph = obj.get("@graph")

                        if graph:
                            for item in graph:
                                if (
                                    isinstance(item, dict)
                                    and item.get("datePublished")
                                ):
                                    published = item["datePublished"]
                                    break

                        if published:
                            break

                except Exception:
                    pass

        if not published:
            text = soup.get_text(" ", strip=True)

            match = re.search(
                r"Date:\s*(\d{4})\.(\d{2})\.(\d{2})",
                text
            )

            if match:
                published = (
                    match.group(1)
                    + "-"
                    + match.group(2)
                    + "-"
                    + match.group(3)
                    + "T00:00:00+00:00"
                )

        if published:
            try:
                date = datetime.fromisoformat(
                    published.replace("Z", "+00:00")
                )

                if date.tzinfo is None:
                    date = date.replace(
                        tzinfo=timezone.utc
                    )

            except Exception:
                date = datetime.now(timezone.utc)
        else:
            date = datetime.now(timezone.utc)

        if not title:
            return None

        return {
            "title": title,
            "url": url,
            "image": image,
            "date": date
        }

    except Exception as error:
        print("Error reading " + url + ": " + str(error))
        return None


response = session.get(
    NIKE_PAGE,
    timeout=30
)

response.raise_for_status()

soup = BeautifulSoup(
    response.text,
    "html.parser"
)

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


articles = []

for url in urls:
    print("Checking: " + url)

    article = get_article(url)

    if article:
        articles.append(article)


articles.sort(
    key=lambda x: x["date"],
    reverse=True
)


rss = ET.Element(
    "rss",
    {
        "version": "2.0",
        "xmlns:media": "http://search.yahoo.com/mrss/"
    }
)

channel = ET.SubElement(rss, "channel")

ET.SubElement(
    channel,
    "title"
).text = "House of Heat - Nike"

ET.SubElement(
    channel,
    "link"
).text = NIKE_PAGE

ET.SubElement(
    channel,
    "description"
).text = "Latest Nike news from House of Heat"

ET.SubElement(
    channel,
    "language"
).text = "en"


for article in articles:

    item = ET.SubElement(channel, "item")

    ET.SubElement(
        item,
        "title"
    ).text = article["title"]

    ET.SubElement(
        item,
        "link"
    ).text = article["url"]

    ET.SubElement(
        item,
        "guid",
        {"isPermaLink": "true"}
    ).text = article["url"]

    ET.SubElement(
        item,
        "pubDate"
    ).text = format_datetime(article["date"])

    if article["image"]:

        image_url = article["image"]
        mime_type = get_image_type(image_url)

        ET.SubElement(
            item,
            "{http://search.yahoo.com/mrss/}content",
            {
                "url": image_url,
                "medium": "image",
                "type": mime_type
            }
        )

        ET.SubElement(
            item,
            "{http://search.yahoo.com/mrss/}thumbnail",
            {
                "url": image_url
            }
        )

        ET.SubElement(
            item,
            "enclosure",
            {
                "url": image_url,
                "type": mime_type,
                "length": "0"
            }
        )

        description_html = (
            '<img src="'
            + html.escape(image_url, quote=True)
            + '" alt="" />'
            + "<br><br>"
            + html.escape(article["title"])
        )

        ET.SubElement(
            item,
            "description"
        ).text = description_html


tree = ET.ElementTree(rss)

tree.write(
    FEED_FILE,
    encoding="utf-8",
    xml_declaration=True
)


with open(
    FEED_FILE,
    "r",
    encoding="utf-8"
) as file:
    xml = file.read()


pattern = re.compile(
    r"<description>(.*?)</description>",
    re.DOTALL
)


def make_cdata(match):
    content = match.group(1)
    content = html.unescape(content)

    return (
        "<description><![CDATA["
        + content
        + "]]></description>"
    )


xml = pattern.sub(
    make_cdata,
    xml
)


with open(
    FEED_FILE,
    "w",
    encoding="utf-8"
) as file:
    file.write(xml)


print(
    "Feed updated with "
    + str(len(articles))
    + " Nike articles."
)
