import requests
import time
import feedparser

TELEGRAM_BOT_TOKEN = "8184765049:AAGS-X9Qa829_kV7hiWFistjN3G3QdJs1SY"
CHAT_ID = 5250165372
KEYWORDS = ["tefeci", "tefecilik"]

RSS_URLS = [
    "https://news.google.com/rss/search?q=tefeci+OR+tefecilik&hl=tr&gl=TR&ceid=TR:tr",
]

sent_links = set()

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
            content = (entry.title + " " + entry.summary).lower()
            if any(k in content for k in KEYWORDS):
                message = f"📢 Yeni Haber:\n\n{entry.title}\n\n🔗 {link}"
                send_message(message)
                sent_links.add(link)

print("Bot çalışıyor...")

while True:
    try:
        check_news()
    except Exception as e:
        print("Hata:", e)
    time.sleep(180)
