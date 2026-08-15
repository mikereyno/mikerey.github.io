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


def get_image_info(url):
   try:
       response = session.head(
           url,
           timeout=20,
           allow_redirects=True
       )

       content_type = response.headers.get(
           "Content-Type",
           ""
       ).split(";")[0].strip()

       content_length = response.headers.get(
           "Content-Length",
           "0"
       )

       try:
           content_length = int(content_length)
       except Exception:
           content_length = 0

       if not content_type.startswith("image/"):
           content_type = "image/jpeg"

       return content_type, content_length

   except Exception:
       return "image/jpeg", 0


def get_article(url):
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

       # --------------------------------------------
       # TITLE
       # --------------------------------------------

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

       # --------------------------------------------
       # IMAGE
       # --------------------------------------------

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

       # --------------------------------------------
       # DATE
       # --------------------------------------------

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
                       script.string
                       or script.get_text()
                   )

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

               except Exception:
                   pass

       # House of Heat date
       if not published:

           text = soup.get_text(
               " ",
               strip=True
           )

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

       # --------------------------------------------
       # CONVERT DATE
       # --------------------------------------------

       if published:

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

       else:

           date = datetime.now(
               timezone.utc
           )

       if not title:
           return None

       # Get real image MIME type and size
       image_type = None
       image_size = 0

       if image:

           image_type, image_size = (
               get_image_info(image)
           )

       return {
           "title": title,
           "url": url,
           "image": image,
           "image_type": image_type,
           "image_size": image_size,
           "date": date
       }

   except Exception as error:

       print(
           "Error reading "
           + url
           + ": "
           + str(error)
       )

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

   if (
       href.startswith("/nike/")
       and href != "/nike/"
   ):

       url = SITE + href

       if url not in seen:

           seen.add(url)
           urls.append(url)

   if len(urls) >= 30:
       break


# =========================================================
# GET ARTICLES
# =========================================================

articles = []

for url in urls:

   print(
       "Checking: "
       + url
   )

   article = get_article(url)

   if article:

       articles.append(article)


# Newest first
articles.sort(
   key=lambda x: x["date"],
   reverse=True
)


# =========================================================
# CREATE RSS
# =========================================================

rss = ET.Element(
   "rss",
   {
       "version": "2.0",
       "xmlns:media":
           "http://search.yahoo.com/mrss/",
       "xmlns:content":
           "http://purl.org/rss/1.0/modules/content/"
   }
)

channel = ET.SubElement(
   rss,
   "channel"
)

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
).text = (
   "Latest Nike news from House of Heat"
)

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

   # -----------------------------------------------------
   # IMAGE
   # -----------------------------------------------------

   if article["image"]:

       image_url = article["image"]
       image_type = article["image_type"]
       image_size = article["image_size"]

       # MEDIA RSS CONTENT
       ET.SubElement(
           item,
           "{http://search.yahoo.com/mrss/}content",
           {
               "url": image_url,
               "medium": "image",
               "type": image_type,
               "fileSize": str(image_size)
           }
       )

       # MEDIA RSS THUMBNAIL
       ET.SubElement(
           item,
           "{http://search.yahoo.com/mrss/}thumbnail",
           {
               "url": image_url
           }
       )

       # STANDARD RSS ENCLOSURE
       ET.SubElement(
           item,
           "enclosure",
           {
               "url": image_url,
               "length": str(image_size),
               "type": image_type
           }
       )

       # CONTENT:ENCODED
       html_content = (
           '<p>'
           '<img src="'
           + html.escape(
               image_url,
               quote=True
           )
           + '" alt="'
           + html.escape(
               article["title"],
               quote=True
           )
           + '" />'
           '</p>'
           '<p>'
           + html.escape(
               article["title"]
           )
           + '</p>'
       )

       ET.SubElement(
           item,
           "{http://purl.org/rss/1.0/modules/content/}encoded"
       ).text = html_content

       # DESCRIPTION
       ET.SubElement(
           item,
           "description"
       ).text = html_content


# =========================================================
# WRITE FEED
# =========================================================

tree = ET.ElementTree(
   rss
)

tree.write(
   FEED_FILE,
   encoding="utf-8",
   xml_declaration=True
)


# =========================================================
# TURN HTML INTO CDATA
# =========================================================

with open(
   FEED_FILE,
   "r",
   encoding="utf-8"
) as file:

   xml = file.read()


def convert_cdata(
   match
):

   content = match.group(1)

   content = html.unescape(
       content
   )

   return (
       "<description><![CDATA["
       + content
       + "]]></description>"
   )


xml = re.sub(
   r"<description>(.*?)</description>",
   convert_cdata,
   xml,
   flags=re.DOTALL
)


# CONTENT:ENCODED CDATA

def convert_content_cdata(
   match
):

   content = match.group(1)

   content = html.unescape(
       content
   )

   return (
       "<content:encoded><![CDATA["
       + content
       + "]]></content:encoded>"
   )


xml = re.sub(
   r"<content:encoded>(.*?)</content:encoded>",
   convert_content_cdata,
   xml,
   flags=re.DOTALL
)


# =========================================================
# SAVE FINAL FEED
# =========================================================

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
