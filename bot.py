# ==============================
#   TELEGRAM HABER BOTU (FULL)
# ==============================

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# ------------------------------
# Render için fake web server
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
# Ana bot kısımları
# ------------------------------
import requests
import time
import feedparser
import os
from datetime import datetime, timezone, timedelta

# -----------------------------------
# TELEGRAM Bilgileri
# -----------------------------------
TELEGRAM_BOT_TOKEN = "8184765049:AAGS-X9Qa829_kV7hiWFistjN3G3QdJs1SY"
CHAT_ID = 5250165372

# Aranacak kelimeler
KEYWORDS = ["tefeci", "tefecilik", "pos tefeciliği", "faizle para"]

# -----------------------------------
# RSS kaynakları (Google News + ek RSS)
# -----------------------------------
RSS_URLS = [
    "https://news.google.com/rss/search?q=tefeci+OR+tefecilik+when:1d&hl=tr&gl=TR&ceid=TR:tr",
]

# -----------------------------------
# Gönderilmiş linkleri saklama
# -----------------------------------
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

# -----------------------------------
# Telegram gönderim fonksiyonu (link başlığa gömülü)
# -----------------------------------
def send_news(entry):
    title = entry.title
    link = entry.link  # Google News linki
    summary = getattr(entry, "summary", "📝 Bu haber için özet bulunamadı.")

    # Linki başlığa gömerek gizle
    message_text = f'📢 <a href="{link}">{title}</a>\n\n{summary}\n\n<i>Kaynak: Google News</i>'

    # Fotoğraf kontrol
    image_url = None
    media = getattr(entry, "media_content", None)
    if media and isinstance(media, list) and len(media) > 0:
        image_url = media[0].get("url")

    if image_url:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        data = {"chat_id": CHAT_ID, "photo": image_url, "caption": message_text, "parse_mode": "HTML"}
        requests.post(url, data=data)
    else:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": message_text, "parse_mode": "HTML"}
        requests.post(url, data=data)

# -----------------------------------
# Haber kontrol fonksiyonu
# -----------------------------------
def check_news():
    for RSS_URL in RSS_URLS:
        feed = feedparser.parse(RSS_URL)

        for entry in feed.entries:
            link = entry.link

            # Daha önce gönderilmiş mi?
            if link in sent_links:
                continue

            # Haber tarihi kontrolü — 24 saatten eskiyse alma
            published = getattr(entry, "published_parsed", None)
            if published:
                time_dt = datetime.fromtimestamp(time.mktime(published), tz=timezone.utc)
                if datetime.now(timezone.utc) - time_dt > timedelta(days=1):
                    continue

            # Keyword filtre
            content = (entry.title + " " + getattr(entry, "summary", "")).lower()
            if not any(k in content for k in KEYWORDS):
                continue

            # Haber şartlara uyuyorsa gönder
            send_news(entry)

            # Link kaydedilsin
            sent_links.add(link)
            save_links()


# -----------------------------------
# Başlangıç mesajı at
# -----------------------------------
requests.post(
    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
    data={"chat_id": CHAT_ID, "text": "🟢 Bot başlatıldı! Haberler kontrol ediliyor..."},
)

print("Bot çalışıyor...")

# -----------------------------------
# Sürekli haber kontrol döngüsü
# -----------------------------------
while True:
    try:
        check_news()
    except Exception as e:
        print("Hata:", e)
    time.sleep(180)  # 3 dakikada bir kontrol
