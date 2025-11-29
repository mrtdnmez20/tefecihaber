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
# -----------------------------

# Fake server (Render için)
def fake_server():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot running")

        def do_HEAD(self):
            self.send_response(200)
            self.end_headers()

    server = HTTPServer(("", 10000), Handler)
    server.serve_forever()

threading.Thread(target=fake_server, daemon=True).start()

# RSS feed (Google News)
RSS_URLS = [
    "https://news.google.com/rss/search?q=tefeci+OR+tefecilik+when:1d&hl=tr&gl=TR&ceid=TR:tr",
]

# Gönderilen linkler
if os.path.exists("sent_links.txt"):
    with open("sent_links.txt", "r") as f:
        sent_links = set(line.strip() for line in f)
else:
    sent_links = set()

def save_links():
    with open("sent_links.txt", "w") as f:
        for link in sent_links:
            f.write(link + "\n")

# Google RSS link normalize
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

# Haber resmi bulma
def extract_image(entry):
    try:
        # RSS içindeki medya
        if hasattr(entry, 'media_content') and entry.media_content:
            return entry.media_content[0]['url']
        if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
            return entry.media_thumbnail[0]['url']

        # Summary'den al
        m = re.search(r'<img[^>]+src="([^"]+)"', getattr(entry, 'summary', ''))
        if m:
            return m.group(1)

        # Haber sayfasından og:image çek
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

# Telegram'a mesaj gönderme
def send_news(entry):
    link = normalize_link(entry.link)
    title = entry.title
    summary = getattr(entry, 'summary', '').replace("<br>", "").replace("<br/>", "")

    image_url = extract_image(entry)

    message_text = f'📢 <a href="{link}">{title}</a>\n\n{summary}'

    try:
        if image_url:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto",
                data={
                    "chat_id": CHAT_ID,
                    "caption": message_text,
                    "parse_mode": "HTML",
                    "photo": image_url,
                }
            )
        else:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                data={
                    "chat_id": CHAT_ID,
                    "text": message_text,
                    "parse_mode": "HTML"
                }
            )
    except Exception as e:
        print("Telegram gönderme hatası:", e)

# İlk açılışta eski haberleri göndermesin diye
first_run = True

# Haber kontrolü
def check_news():
    global first_run

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

            # 24 saatten eski haberleri alma
            published_time = getattr(entry, 'published_parsed', None)
            if published_time:
                published_dt = datetime.fromtimestamp(time.mktime(published_time), tz=timezone.utc)
                if datetime.now(timezone.utc) - published_dt > timedelta(days=1):
                    continue

            if not first_run:
                send_news(entry)

            sent_links.add(link)
            save_links()

    first_run = False

print("Bot çalışıyor...")

# Telegram'a test mesajı
try:
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": "🤖 Bot yeniden başlatıldı ve çalışıyor!"}
    )
except:
    pass

# Döngü
while True:
    try:
        check_news()
    except Exception as e:
        print("Hata:", e)
    time.sleep(180)
