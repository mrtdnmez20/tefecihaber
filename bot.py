import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import requests
import time
import feedparser
import os
import re
from datetime import datetime, timezone, timedelta

# -----------------------------
# Telegram bilgileri environment variable üzerinden alınır
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
KEYWORDS = ["tefeci", "tefecilik", "pos tefe"]
# -----------------------------

if not TELEGRAM_BOT_TOKEN or not CHAT_ID:
    raise ValueError("Lütfen TELEGRAM_BOT_TOKEN ve CHAT_ID environment variable olarak tanımlayın!")

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

# Resim çıkarma fonksiyonu
def extract_image(entry):
    if hasattr(entry, 'media_content') and entry.media_content:
        return entry.media_content[0]['url']
    elif hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
        return entry.media_thumbnail[0]['url']
    else:
        imgs = re.findall(r'<img[^>]+src="([^"]+)"', getattr(entry, 'summary', ''))
        if imgs:
            return imgs[0]
    return None

def send_news(entry):
    link = entry.link
    title = entry.title
    summary = getattr(entry, 'summary', '')
    image_url = extract_image(entry)

    message_text = f"📢 {title}\n\n{summary}\n\n🔗 {link}"

    try:
        if image_url:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
            data = {"chat_id": CHAT_ID, "photo": image_url, "caption": message_text}
            r = requests.post(url, data=data)
            if not r.ok:
                print("Fotoğraf gönderilemedi, text ile gönderiliyor...")
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                              data={"chat_id": CHAT_ID, "text": message_text})
        else:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            data = {"chat_id": CHAT_ID, "text": message_text}
            r = requests.post(url, data=data)
            if not r.ok:
                print("Mesaj gönderilemedi:", r.text)
    except Exception as e:
        print("Telegram gönderme hatası:", e)

def check_news():
    global first_run
    for RSS_URL in RSS_URLS:
        try:
            feed = feedparser.parse(RSS_URL)
        except Exception as e:
            print("RSS parse hatası:", e)
            continue

        for entry in feed.entries:
            link = entry.link
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

print("Bot çalışıyor...")

while True:
    try:
        check_news()
    except Exception as e:
        print("Hata:", e)
    time.sleep(180)
