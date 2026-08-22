import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from email.utils import format_datetime
import xml.etree.ElementTree as ET
import json
import html
import re

SITE = "https://www.soleretriever.com"
NIKE_PAGE = f"{SITE}/news/tags/nike"
FEED_FILE = "sole-retriever-nike.xml"

HEADERS = {
   "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/139 Safari/537.36"
}

session = requests.Session()
session.headers.update(HEADERS)


def get_article_details(url):
   try:
       response = session.get(url, timeout=30)
       response.raise_for_status()

       soup = BeautifulSoup(response.text, "html.parser")

       # TITLE
       title = None

       h1 = soup.find("h1")
       if h1:
           title = h1.get_text(" ", strip=True)

       if not title:
           meta = soup.find("meta", property="og:title")
           if meta:
               title = meta.get("content")

       # IMAGE
       image = None

       meta = soup.find("meta", property="og:image")
       if meta:
           image = meta.get("content")

       if not image:
           meta = soup.find("meta", attrs={"name": "twitter:image"})
           if meta:
               image = meta.get("content")

       # DATE
       published = None

       meta = soup.find(
           "meta",
           property="article:published_time"
       )

       if meta:
           published = meta.get("content")

       # JSON-LD
       if not published:
           for script in soup.find_all(
               "script",
               type="application/ld+json"
           ):
               try:
                   data = json.loads(
                       script.string or script.get_text()
                   )

                   objects = data if isinstance(data, list) else [data]

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

       # Look for visible date such as:
       # August 21, 2026
       if not published:
           text = soup.get_text(" ", strip=True)

           match = re.search(
               r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}",
               text
           )

           if match:
               try:
                   date = datetime.strptime(
                       match.group(0),
                       "%B %d, %Y"
                   ).replace(tzinfo=timezone.utc)

               except Exception:
                   date = datetime.now(timezone.utc)

           else:
               date = datetime.now(timezone.utc)

       else:
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

       if not title:
           return None

       return {
           "title": title,
           "url": url,
           "image": image,
           "date": date
       }

   except Exception as error:
       print(f"Could not read {url}: {error}")
       return None


# =========================================================
# FIND NIKE ARTICLES
# =========================================================

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

for link in soup.find_all(
   "a",
   href=True
):

   href = link["href"]

   # ONLY collect actual Sole Retriever article URLs.
   # This prevents category/tag/navigation pages
   # from being added to the RSS feed.
   if href.startswith("/news/articles/"):

       url = SITE + href

       if url not in seen:
           seen.add(url)
           urls.append(url)

   if len(urls) >= 40:
       break


# =========================================================
# GET ARTICLE INFORMATION
# =========================================================

articles = []

for url in urls:

   print(f"Checking {url}")

   article = get_article_details(url)

   if article:
       articles.append(article)


# =========================================================
# REMOVE DUPLICATES
# =========================================================

unique_articles = {}

for article in articles:
   unique_articles[article["url"]] = article

articles = list(unique_articles.values())


# =========================================================
# NEWEST FIRST
# =========================================================

articles.sort(
   key=lambda article: article["date"],
   reverse=True
)


# =========================================================
# CREATE RSS FEED
# =========================================================

rss = ET.Element(
   "rss",
   {
       "version": "2.0",
       "xmlns:media": "http://search.yahoo.com/mrss/"
   }
)

channel = ET.SubElement(
   rss,
   "channel"
)

ET.SubElement(
   channel,
   "title"
).text = "Sole Retriever — Nike"

ET.SubElement(
   channel,
   "link"
).text = NIKE_PAGE

ET.SubElement(
   channel,
   "description"
).text = "Latest Nike news from Sole Retriever"

ET.SubElement(
   channel,
   "language"
).text = "en"


# =========================================================
# ADD ARTICLES
# =========================================================

for article in articles:

   item = ET.SubElement(
       channel,
       "item"
   )

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
       {
           "isPermaLink": "true"
       }
   ).text = article["url"]

   ET.SubElement(
       item,
       "pubDate"
   ).text = format_datetime(
       article["date"]
   )

   # IMAGE
   if article["image"]:

       image_url = article["image"]

       # Media RSS
       ET.SubElement(
           item,
           "{http://search.yahoo.com/mrss/}content",
           {
               "url": image_url,
               "medium": "image"
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

       # Image in description
       image_html = (
           '<img src="'
           + html.escape(image_url, quote=True)
           + '" />'
       )

       description_html = (
           image_html
           + "<br><br>"
           + html.escape(article["title"])
       )

       ET.SubElement(
           item,
           "description"
       ).text = description_html


# =========================================================
# SAVE RSS FEED
# =========================================================

tree = ET.ElementTree(rss)

tree.write(
   FEED_FILE,
   encoding="utf-8",
   xml_declaration=True
)

print(
   f"RSS feed updated with {len(articles)} Nike articles."
)
