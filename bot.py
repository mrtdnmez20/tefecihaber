import requests
import time
import feedparser
import os

# -----------------------------
# Telegram bilgilerini buraya yaz
TELEGRAM_BOT_TOKEN = "8184765049:AAGS-X9Qa829_kV7hiWFistjN3G3QdJs1SY"
CHAT_ID = 5250165372
KEYWORDS = ["tefeci", "tefecilik"]
# -----------------------------

# Son 24 saatlik Google News RSS
RSS_URLS = [
    "https://news.google.com/rss/search?q=tefeci+OR+tefecilik+when:1d&hl=tr&gl=TR&ceid=TR:tr",
]

# Daha önce gönderilen linkleri saklamak için dosya
if os.path.exists("sent_links.txt"):
    with open("sent_links.txt", "r") as f:
        sent_links = set(line.strip() for line in f)
else:
    sent_links = set()

def save_links():
    with open("sent_links.txt", "w") as f:
        for link in sent_links:
            f.write(link + "\n")

def send_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": text}
    requests.post(url, data=data)

def check_news():
    for RSS_URL in RSS_URLS:
        feed = feedparser.parse(RSS_URL)
        for entry in feed.entries:
            link = entry.link
            if link in sent_links:
                continue
            content = (entry.title + " " + getattr(entry, 'summary', '')).lower()
            if any(k in content for k in KEYWORDS):
                message = f"📢 Yeni Haber:\n\n{entry.title}\n\n🔗 {link}"
                send_message(message)
                sent_links.add(link)
                save_links()  # dosyaya kaydet

print("Bot çalışıyor...")

while True:
    try:
        check_news()
    except Exception as e:
        print("Hata:", e)
    time.sleep(600)  # her 3 dakikada bir kontrol
