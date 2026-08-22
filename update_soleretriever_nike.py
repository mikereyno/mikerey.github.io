import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from email.utils import format_datetime
import xml.etree.ElementTree as ET
import json
import html
import re
from urllib.parse import urljoin


SITE = "https://www.soleretriever.com"
NIKE_PAGE = f"{SITE}/news/tags/nike"
FEED_FILE = "sole-retriever-nike-v2.xml"

HEADERS = {
   "User-Agent": (
       "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
       "AppleWebKit/537.36 Chrome/139 Safari/537.36"
   )
}

session = requests.Session()
session.headers.update(HEADERS)


# =========================================================
# BRAND / CATEGORY PAGES TO REJECT
# =========================================================

REJECTED_CATEGORY_TITLES = {
   "nike news",
   "crocs news",
   "adidas news",
   "new balance news",
   "jordan news",
   "air jordan news",
   "reebok news",
   "puma news",
   "asics news",
   "skechers news",
   "under armour news",
   "vans news",
   "saucony news",
}


def is_rejected_category(title):
   """
   Reject brand/category pages that can sometimes appear
   as links within Sole Retriever navigation.
   """

   if not title:
       return True

   cleaned = re.sub(
       r"\s+",
       " ",
       title.strip().lower()
   )

   return cleaned in REJECTED_CATEGORY_TITLES


# =========================================================
# GET ARTICLE DETAILS
# =========================================================

def get_article_details(url):
   try:
       response = session.get(
           url,
           timeout=30
       )

       response.raise_for_status()

       soup = BeautifulSoup(
           response.text,
           "html.parser"
       )

       # -------------------------------------------------
       # TITLE
       # -------------------------------------------------

       title = None

       h1 = soup.find("h1")

       if h1:
           title = h1.get_text(
               " ",
               strip=True
           )

       if not title:
           meta = soup.find(
               "meta",
               property="og:title"
           )

           if meta:
               title = meta.get("content")

       if not title:
           return None

       # Reject category/news landing pages
       if is_rejected_category(title):
           print(
               f"Skipping category page: {title}"
           )
           return None

       # -------------------------------------------------
       # IMAGE
       # -------------------------------------------------

       image = None

       meta = soup.find(
           "meta",
           property="og:image"
       )

       if meta:
           image = meta.get("content")

       if not image:
           meta = soup.find(
               "meta",
               attrs={
                   "name": "twitter:image"
               }
           )

           if meta:
               image = meta.get("content")

       # -------------------------------------------------
       # DATE
       # -------------------------------------------------

       published = None

       meta = soup.find(
           "meta",
           property="article:published_time"
       )

       if meta:
           published = meta.get("content")

       # -------------------------------------------------
       # JSON-LD DATE
       # -------------------------------------------------

       if not published:

           for script in soup.find_all(
               "script",
               type="application/ld+json"
           ):

               try:

                   raw = (
                       script.string
                       or script.get_text()
                   )

                   data = json.loads(raw)

                   objects = (
                       data
                       if isinstance(data, list)
                       else [data]
                   )

                   for obj in objects:

                       if not isinstance(
                           obj,
                           dict
                       ):
                           continue

                       if obj.get(
                           "datePublished"
                       ):
                           published = obj[
                               "datePublished"
                           ]
                           break

                       graph = obj.get(
                           "@graph"
                       )

                       if graph:

                           for item in graph:

                               if (
                                   isinstance(
                                       item,
                                       dict
                                   )
                                   and item.get(
                                       "datePublished"
                                   )
                               ):
                                   published = item[
                                       "datePublished"
                                   ]
                                   break

                       if published:
                           break

                   if published:
                       break

               except Exception:
                   pass

       # -------------------------------------------------
       # FALLBACK VISIBLE DATE
       # -------------------------------------------------

       if not published:

           text = soup.get_text(
               " ",
               strip=True
           )

           match = re.search(
               r"(January|February|March|April|May|June|"
               r"July|August|September|October|November|December)"
               r"\s+\d{1,2},\s+\d{4}",
               text
           )

           if match:

               try:

                   date = datetime.strptime(
                       match.group(0),
                       "%B %d, %Y"
                   ).replace(
                       tzinfo=timezone.utc
                   )

               except Exception:

                   date = datetime.now(
                       timezone.utc
                   )

           else:

               date = datetime.now(
                   timezone.utc
               )

       else:

           try:

               date = datetime.fromisoformat(
                   published.replace(
                       "Z",
                       "+00:00"
                   )
               )

               if date.tzinfo is None:

                   date = date.replace(
                       tzinfo=timezone.utc
                   )

           except Exception:

               date = datetime.now(
                   timezone.utc
               )

       # -------------------------------------------------
       # RETURN ARTICLE
       # -------------------------------------------------

       return {
           "title": title,
           "url": url,
           "image": image,
           "date": date
       }

   except Exception as error:

       print(
           f"Could not read {url}: {error}"
       )

       return None


# =========================================================
# FIND NIKE ARTICLES
# =========================================================

print(
   f"Fetching Nike page: {NIKE_PAGE}"
)

response = session.get(
   NIKE_PAGE,
   timeout=30
)

response.raise_for_status()

soup = BeautifulSoup(
   response.text,
   "html.parser"
)


# =========================================================
# COLLECT ARTICLE LINKS
# =========================================================

urls = []
seen = set()


for link in soup.find_all(
   "a",
   href=True
):

   href = link.get("href", "").strip()

   # Convert relative URLs to absolute URLs
   url = urljoin(
       SITE,
       href
   )

   # -----------------------------------------------------
   # ONLY REAL ARTICLE URLS
   # -----------------------------------------------------

   if not re.match(
       r"^https://www\.soleretriever\.com/news/articles/",
       url
   ):
       continue

   # -----------------------------------------------------
   # READ THE LINK TEXT
   # -----------------------------------------------------

   link_title = link.get_text(
       " ",
       strip=True
   )

   # Reject category/navigation links
   if is_rejected_category(
       link_title
   ):
       print(
           f"Skipping category link: {link_title}"
       )
       continue

   # -----------------------------------------------------
   # REMOVE QUERY STRING / FRAGMENT
   # -----------------------------------------------------

   url = url.split("?")[0]
   url = url.split("#")[0]

   # -----------------------------------------------------
   # DEDUPLICATE
   # -----------------------------------------------------

   if url in seen:
       continue

   seen.add(url)

   urls.append(url)

   print(
       f"Found Nike article: {url}"
   )

   # Keep a reasonable number of articles
   if len(urls) >= 40:
       break


print(
   f"Found {len(urls)} possible Nike articles."
)


# =========================================================
# GET ARTICLE INFORMATION
# =========================================================

articles = []


for url in urls:

   print(
       f"Checking article: {url}"
   )

   article = get_article_details(
       url
   )

   if not article:
       continue

   # -----------------------------------------------------
   # FINAL CATEGORY CHECK
   # -----------------------------------------------------

   if is_rejected_category(
       article["title"]
   ):
       print(
           f"Rejected category: "
           f"{article['title']}"
       )
       continue

   articles.append(
       article
   )


# =========================================================
# REMOVE DUPLICATES
# =========================================================

unique_articles = {}


for article in articles:

   unique_articles[
       article["url"]
   ] = article


articles = list(
   unique_articles.values()
)


# =========================================================
# NEWEST FIRST
# =========================================================

articles.sort(
   key=lambda article: article["date"],
   reverse=True
)


print(
   f"Final Nike article count: "
   f"{len(articles)}"
)


# =========================================================
# CREATE RSS FEED
# =========================================================

rss = ET.Element(
   "rss",
   {
       "version": "2.0",
       "xmlns:media":
           "http://search.yahoo.com/mrss/"
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
).text = (
   "Latest Nike news from Sole Retriever"
)


ET.SubElement(
   channel,
   "language"
).text = "en"


# =========================================================
# ADD ARTICLES TO RSS
# =========================================================

for article in articles:

   item = ET.SubElement(
       channel,
       "item"
   )

   # TITLE
   ET.SubElement(
       item,
       "title"
   ).text = article["title"]

   # LINK
   ET.SubElement(
       item,
       "link"
   ).text = article["url"]

   # GUID
   ET.SubElement(
       item,
       "guid",
       {
           "isPermaLink": "true"
       }
   ).text = article["url"]

   # DATE
   ET.SubElement(
       item,
       "pubDate"
   ).text = format_datetime(
       article["date"]
   )

   # -----------------------------------------------------
   # IMAGE
   # -----------------------------------------------------

   if article["image"]:

       image_url = article[
           "image"
       ]

       # Media RSS image
       ET.SubElement(
           item,
           "{http://search.yahoo.com/mrss/}"
           "content",
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

       # Image inside description
       image_html = (
           '<img src="'
           + html.escape(
               image_url,
               quote=True
           )
           + '" />'
       )

       description_html = (
           image_html
           + "<br><br>"
           + html.escape(
               article["title"]
           )
       )

       ET.SubElement(
           item,
           "description"
       ).text = description_html


# =========================================================
# SAVE RSS FEED
# =========================================================

tree = ET.ElementTree(
   rss
)


tree.write(
   FEED_FILE,
   encoding="utf-8",
   xml_declaration=True
)


print(
   f"RSS feed updated successfully."
)

print(
   f"Saved {len(articles)} Nike articles "
   f"to {FEED_FILE}"
)
