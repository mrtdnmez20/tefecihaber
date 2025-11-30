import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import requests
import time
import feedparser
import os
import re
import json
from datetime import datetime, timezone, timedelta

# ------------------------------
# Render için fake server
# ------------------------------
def fake_server():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot running")
    server = HTTPServer(("", 10000), Handler)
    server.serve_forever()

threading.Thread(target=fake_server, daemon=True).start()

# ------------------------------
# Telegram ayarları
# ------------------------------
TELEGRAM_BOT_TOKEN = "8184765049:AAGS-X9Qa829_kV7hiWFistjN3G3QdJs1SY"
CHAT_ID = 5250165372
KEYWORDS = ["tefeci", "tefecilik", "pos tefeciliği", "faizle para"]

# RSS Kaynağı
RSS_URLS = [
    "https://news.google.com/rss/search?q=tefeci+OR+tefecilik+when:1d&hl=tr&gl=TR&ceid=TR:tr",
]

# Gönderilen linkler
SENT_FILE = "sent_links.txt"
if os.path.exists(SENT_FILE):
    with open(SENT_FILE, "r", encoding="utf-8") as f:
        sent_links = set(l.strip() for l in f)
else:
    sent_links = set()

def save_links():
    with open(SENT_FILE, "w", encoding="utf-8") as f:
        for l in sent_links:
            f.write(l + "\n")

# HTML temizleme
def clean_html(text):
    clean = re.sub('<.*?>', '', text)
    return clean.strip()

# Google News linklerini normal site linkine dönüştür
def normalize_google_link(link):
    try:
        resp = requests.get(link, timeout=5, allow_redirects=True)
        if resp.ok:
            return resp.url
        return link
    except:
        return link

# Telegram gönderim
def send_news(entry):
    title = clean_html(entry.title)
    summary = clean_html(getattr(entry, "summary", ""))
    link = normalize_google_link(entry.link)

    message_text = f"📢 {title}\n\n{summary}"

    # Telegram JSON formatında olmak zorunda
    keyboard = {
        "inline_keyboard": [
            [{"text": "Haber Linki", "url": link}]
        ]
    }

    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": CHAT_ID,
                "text": message_text,
                "reply_markup": keyboard,
                "disable_web_page_preview": False
            }
        )
        print("Gönderildi:", r.text)
    except Exception as e:
        print("Telegram gönderme hatası:", e)

# Haber kontrol
def check_news():
    for RSS_URL in RSS_URLS:
        feed = feedparser.parse(RSS_URL)
        for entry in feed.entries:

            link = entry.link
            if link in sent_links:
                continue

            # Tarih kontrolü
            published = getattr(entry, "published_parsed", None)
            if published:
                published_dt = datetime.fromtimestamp(time.mktime(published), tz=timezone.utc)
                if datetime.now(timezone.utc) - published_dt > timedelta(days=1):
                    continue

            # Keyword filtre
            content = (entry.title + " " + getattr(entry, "summary", "")).lower()
            if not any(k in content for k in KEYWORDS):
                continue

            send_news(entry)
            sent_links.add(link)
            save_links()

# Başlangıç mesajı
try:
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": "🟢 Bot başlatıldı! Haberler kontrol ediliyor..."}
    )
except:
    pass

print("Bot çalışıyor...")

while True:
    try:
        check_news()
    except Exception as e:
        print("Hata:", e)
    time.sleep(180)
