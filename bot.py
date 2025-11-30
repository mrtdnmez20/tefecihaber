import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import requests
import time
import feedparser
import os
import re
from datetime import datetime, timezone, timedelta

# ------------------------------
# Render uyumasın diye server (PORT kullanılmalı)
# ------------------------------
def keep_alive_server():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot running")

    port = int(os.getenv("PORT", 8080))  # Render PORT verir
    print(f"Keep-alive server running on port {port}")
    server = HTTPServer(("", port), Handler)
    server.serve_forever()

threading.Thread(target=keep_alive_server, daemon=True).start()


# ------------------------------
# Telegram ayarları
# ------------------------------
TELEGRAM_BOT_TOKEN = "8184765049:AAGS-X9Qa829_kV7hiWFistjN3G3QdJs1SY"
CHAT_ID = 5250165372
KEYWORDS = ["tefeci", "tefecilik", "pos tefeciliği", "faizle para", "pos tefecisi"]

RSS_URLS = [
    "https://news.google.com/rss/search?q=tefeci+OR+tefecilik+when:1d&hl=tr&gl=TR&ceid=TR:tr",
]

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

# Google News linklerini gerçek siteye dönüştür
def normalize_google_link(link):
    try:
        resp = requests.get(link, timeout=5, allow_redirects=True)
        return resp.url if resp.ok else link
    except:
        return link

# Telegram gönderim
def send_news(entry):
    title = clean_html(entry.title)
    summary = clean_html(getattr(entry, "summary", ""))
    link = normalize_google_link(entry.link)

    message_text = f"📢 {title}\n\n{summary}"

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
            }
        )
        print("Gönderildi:", r.text)
    except Exception as e:
        print("Telegram gönderme hatası:", e)

# Haber tarayıcı
def check_news():
    for RSS_URL in RSS_URLS:
        feed = feedparser.parse(RSS_URL)
        for entry in feed.entries:

            link = entry.link
            if link in sent_links:
                continue

            # Tarih kontrol
            published = getattr(entry, "published_parsed", None)
            if published:
                published_dt = datetime.fromtimestamp(time.mktime(published), tz=timezone.utc)
                if datetime.now(timezone.utc) - published_dt > timedelta(days=1):
                    continue

            # Kelime filtreleme
            content = (entry.title + " " + getattr(entry, "summary", "")).lower()
            if not any(k in content for k in KEYWORDS):
                continue

            send_news(entry)
            sent_links.add(link)
            save_links()

# ------------------------------
# Haber tarama döngüsü - Ayrı thread
# ------------------------------
def news_loop():
    print("News loop aktif...")
    while True:
        try:
            check_news()
        except Exception as e:
            print("Hata:", e)
        time.sleep(180)  # 3 dakika

threading.Thread(target=news_loop, daemon=True).start()

# ------------------------------
# İlk mesaj
# ------------------------------
requests.post(
    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
    json={"chat_id": CHAT_ID, "text": "🟢 Bot aktif! Haberler izleniyor..."}
)

print("Bot tamamen çalışıyor!")

# Sonsuza kadar açık kalsın
while True:
    time.sleep(999999)
