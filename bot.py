import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import requests
import time
import feedparser
import os
import re
import urllib.parse
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta

# -----------------------------
# Telegram bilgileri
TELEGRAM_BOT_TOKEN = "8184765049:AAGS-X9Qa829_kV7hiWFistjN3G3QdJs1SY"
CHAT_ID = 5250165372
KEYWORDS = ["tefeci", "tefecilik", "pos tefe"]
# -----------------------------

# Fake server Render için
def fake_server():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot running")
    server = HTTPServer(("", 10000), Handler)
    server.serve_forever()

threading.Thread(target=fake_server, daemon=True).start()

# RSS ayarları
RSS_URLS = [
    "https://news.google.com/rss/search?q=tefeci+OR+tefecilik+when:1d&hl=tr&gl=TR&ceid=TR:tr",
]

# Gönderilen linkleri kaydet
if os.path.exists("sent_links.txt"):
    with open("sent_links.txt", "r") as f:
        sent_links = set(line.strip() for line in f)
else:
    sent_links = set()

first_run = True

def save_links():
    with open("sent_links.txt", "w") as f:
        for link in sent_links:
            f.write(link + "\n")

# Link normalize etme (Google RSS -> site link)
def normalize_link(link):
    if "news.google.com/rss/articles/" in link:
        try:
            parsed = urllib.parse.urlparse(link)
            qs = urllib.parse.parse_qs(parsed.query)
            if "url" in qs:
                return qs["url"][0]
        except:
            return link
    return link

# Resim çıkarma
def extract_image(entry):
    if hasattr(entry, 'media_content') and entry.media_content:
        return entry.media_content[0]['url']
    elif hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
        return entry.media_thumbnail[0]['url']
    else:
        m = re.search(r'<img[^>]+src="([^"]+)"', getattr(entry, 'summary', ''))
        if m:
            return m.group(1)
    # Og:image den dene
    try:
        url = normalize_link(entry.link)
        resp = requests.get(url, timeout=5)
        if resp.ok:
            soup = BeautifulSoup(resp.text, "html.parser")
            og = soup.find("meta", property="og:image")
            if og and og.get("content"):
                return og["content"]
    except:
        return None
    return None

def send_news(entry):
    link = normalize_link(entry.link)
    title = entry.title
    summary = getattr(entry, 'summary', '')
    image_url = extract_image(entry)

    message_text = f'📢 <a href="{link}">{title}</a>\n\n{summary}'

    try:
        if image_url:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto",
                data={"chat_id": CHAT_ID, "caption": message_text, "parse_mode": "HTML", "photo": image_url}
            )
        else:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                data={"chat_id": CHAT_ID, "text": message_text, "parse_mode": "HTML"}
            )
    except Exception as e:
        print("Telegram gönderme hatası:", e)

def fetch_google_search():
    """Google Search ile haberleri çek (basit scraping)"""
    headers = {"User-Agent": "Mozilla/5.0"}
    for keyword in KEYWORDS:
        query = urllib.parse.quote(keyword)
        url = f"https://www.google.com/search?q={query}&tbm=nws"
        try:
            resp = requests.get(url, headers=headers, timeout=5)
            if not resp.ok:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            results = soup.select("div.GI74Re a")
            for a in results:
                link = a.get("href")
                if not link:
                    continue
                # Normalize link
                if link in sent_links:
                    continue
                title = a.get_text()
                entry = type("Entry", (object,), {})()  # sahte entry objesi
                entry.link = link
                entry.title = title
                entry.summary = ""
                send_news(entry)
                sent_links.add(link)
                save_links()
        except Exception as e:
            print("Google search hatası:", e)

def check_news():
    global first_run
    # RSS haberleri
    for RSS_URL in RSS_URLS:
        try:
            feed = feedparser.parse(RSS_URL)
        except Exception as e:
            print("RSS parse hatası:", e)
            continue

        for entry in feed.entries:
            link = normalize_link(entry.link)
            if link in sent_links:
                continue

            published_time = getattr(entry, 'published_parsed', None)
            if published_time:
                published_dt = datetime.fromtimestamp(time.mktime(published_time), tz=timezone.utc)
                if datetime.now(timezone.utc) - published_dt > timedelta(days=1):
                    continue

            content = (entry.title + " " + getattr(entry, 'summary', '')).lower()
            if any(k in content for k in KEYWORDS):
                if not first_run:
                    send_news(entry)
                sent_links.add(link)
                save_links()
    first_run = False

    # Google Search haberleri
    fetch_google_search()

print("Bot çalışıyor...")

while True:
    try:
        check_news()
    except Exception as e:
        print("Hata:", e)
    time.sleep(180)
