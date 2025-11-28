import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

def fake_server():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot running")

    server = HTTPServer(("", 10000), Handler)  # Render otomatik PORT veriyor
    server.serve_forever()

threading.Thread(target=fake_server, daemon=True).start()

import requests
import time
import feedparser
import os
import time
from datetime import datetime, timezone, timedelta

# -----------------------------
# Telegram bilgilerini buraya yaz
TELEGRAM_BOT_TOKEN = "8184765049:AAGS-X9Qa829_kV7hiWFistjN3G3QdJs1SY"
CHAT_ID = 5250165372
KEYWORDS = ["tefeci", "tefecilik"]
# -----------------------------

# Google News RSS (son 1 gün)
RSS_URLS = [
    "https://news.google.com/rss/search?q=tefeci+OR+tefecilik+when:1d&hl=tr&gl=TR&ceid=TR:tr",
]

# Daha önce gönderilen linkleri saklamak için dosya
if os.path.exists("sent_links.txt"):
    with open("sent_links.txt", "r") as f:
        sent_links = set(line.strip() for line in f)
else:
    sent_links = set()

# Botun ilk çalışması mı
first_run = True

def save_links():
    with open("sent_links.txt", "w") as f:
        for link in sent_links:
            f.write(link + "\n")

def send_news(entry):
    link = entry.link
    title = entry.title
    summary = getattr(entry, 'summary', '')

    # Resim var mı kontrol et
    image_url = None
    media = getattr(entry, 'media_content', None)
    if media and len(media) > 0:
        image_url = media[0]['url']

    message_text = f"📢 {title}\n\n{summary}\n\n🔗 {link}"

    if image_url:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        data = {"chat_id": CHAT_ID, "photo": image_url, "caption": message_text}
        requests.post(url, data=data)
    else:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": message_text}
        requests.post(url, data=data)

def check_news():
    global first_run
    for RSS_URL in RSS_URLS:
        feed = feedparser.parse(RSS_URL)
        for entry in feed.entries:
            link = entry.link
            if link in sent_links:
                continue

            # Haber tarihini kontrol et
            published_time = getattr(entry, 'published_parsed', None)
            if published_time:
                published_dt = datetime.fromtimestamp(time.mktime(published_time), tz=timezone.utc)
                if datetime.now(timezone.utc) - published_dt > timedelta(days=1):
                    continue  # 24 saatten eski, atla

            content = (entry.title + " " + getattr(entry, 'summary', '')).lower()
            if any(k in content for k in KEYWORDS):
                if not first_run:
                    send_news(entry)
                sent_links.add(link)
                save_links()
    first_run = False

print("Bot çalışıyor...")

while True:
    try:
        check_news()
    except Exception as e:
        print("Hata:", e)
    time.sleep(180)  # her 3 dakikada bir kontrol
