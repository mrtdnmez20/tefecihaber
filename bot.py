# bot.py
"""
Haber botu - RSS + Google Search hibrit
- Render uyumlu fake server (port binding)
- TOKEN ve CHAT_ID environment variable ile okunur
- Resim varsa sendPhoto, yoksa sendMessage
- Link normalize edilip sent_links.txt ile tekrar engellenir
"""

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import requests
import time
import feedparser
import os
import re
import traceback
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urlunparse
from datetime import datetime, timezone, timedelta

# ========== Konfig (env üzerinden) ==========
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")          # tek kullanıcı chat id (string olarak)
KEYWORDS = os.getenv("KEYWORDS", "tefeci,tefecilik,pos tefe").split(",")
RSS_URLS = [
    "https://news.google.com/rss/search?q=tefeci+OR+tefecilik+when:1d&hl=tr&gl=TR&ceid=TR:tr",
]
GOOGLE_SEARCH_QUERY = os.getenv("GOOGLE_SEARCH_QUERY", "tefeci tefecilik")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL_SECONDS", "180"))
SEARCH_USER_AGENT = os.getenv("SEARCH_USER_AGENT",
                              "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36")
# ============================================

if not TELEGRAM_BOT_TOKEN or not CHAT_ID:
    raise ValueError("Lütfen TELEGRAM_BOT_TOKEN ve CHAT_ID environment variable olarak tanımlayın!")

# Fake server (Render için port binding). HEAD ve GET desteklenir.
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

# sent_links saklama
SENT_FILE = "sent_links.txt"
if os.path.exists(SENT_FILE):
    with open(SENT_FILE, "r", encoding="utf-8") as f:
        sent_links = set(line.strip() for line in f if line.strip())
else:
    sent_links = set()

def save_links():
    try:
        with open(SENT_FILE, "w", encoding="utf-8") as f:
            for link in sorted(sent_links):
                f.write(link + "\n")
    except Exception as e:
        print("sent_links kaydedilemedi:", e)

# URL normalize (query ve fragment çıkar)
def normalize_url(url):
    try:
        parsed = urlparse(url)
        clean = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
        return clean.rstrip("/")
    except Exception:
        return url

# HTML içinden img src'leri al
def extract_imgs_from_html(html):
    imgs = []
    try:
        soup = BeautifulSoup(html, "html.parser")
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
            if src and src.startswith("http"):
                imgs.append(src)
    except Exception:
        pass
    return imgs

# RSS entry için resim bulma (öncelik media_content > media_thumbnail > summary img)
def extract_image_from_entry(entry):
    try:
        if hasattr(entry, "media_content") and entry.media_content:
            mc = entry.media_content
            if isinstance(mc, (list, tuple)) and mc:
                candidate = mc[0].get("url")
                if candidate:
                    return candidate
        if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
            mt = entry.media_thumbnail
            if isinstance(mt, (list, tuple)) and mt:
                candidate = mt[0].get("url")
                if candidate:
                    return candidate
        summary = getattr(entry, "summary", "") or ""
        imgs = extract_imgs_from_html(summary)
        if imgs:
            return imgs[0]
    except Exception:
        pass
    return None

# Google News search scraper (basit)
def fetch_google_news_search(query, limit=12):
    results = []
    try:
        q = requests.utils.requote_uri(query)
        url = f"https://www.google.com/search?q={q}&tbm=nws&hl=tr"
        headers = {"User-Agent": SEARCH_USER_AGENT}
        r = requests.get(url, headers=headers, timeout=15)
        if not r.ok:
            print("Google search hata:", r.status_code)
            return results
        soup = BeautifulSoup(r.text, "html.parser")
        # Haber blokları
        blocks = soup.select("div.dbsr") or soup.select("div[role='article']") or soup.select("g-card")
        for b in blocks:
            try:
                a = b.find("a", href=True)
                if not a:
                    continue
                href = a["href"]
                # başlık
                title_tag = a.find("div") or a.find("h3") or a
                title = title_tag.get_text(strip=True) if title_tag else a.get_text(strip=True)
                # snippet
                snippet_tag = b.find("div", {"class": "Y3v8qd"}) or b.find("div", {"class": "st"}) or b.find("div", {"class":"slp"})
                snippet = snippet_tag.get_text(" ", strip=True) if snippet_tag else ""
                img_tag = b.find("img")
                image = None
                if img_tag:
                    image = img_tag.get("src") or img_tag.get("data-src")
                norm = normalize_url(href)
                results.append({"title": title, "url": href, "norm_url": norm, "snippet": snippet, "image": image})
                if len(results) >= limit:
                    break
            except Exception:
                continue
        # fallback: a etiketlerinden bazı linkler
        if not results:
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "/articles/" in href or "news" in href:
                    title = a.get_text(strip=True)
                    norm = normalize_url(href)
                    results.append({"title": title, "url": href, "norm_url": norm, "snippet": "", "image": None})
                    if len(results) >= limit:
                        break
    except Exception as e:
        print("fetch_google_news_search hata:", e)
    return results

# Telegram yardımcıları
def telegram_send_text(text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": text}
        r = requests.post(url, data=data, timeout=15)
        if not r.ok:
            print("sendMessage hata:", r.status_code, r.text)
    except Exception as e:
        print("sendMessage exception:", e)

def telegram_send_photo(photo_url, caption):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        data = {"chat_id": CHAT_ID, "photo": photo_url, "caption": caption}
        r = requests.post(url, data=data, timeout=20)
        if not r.ok:
            print("sendPhoto hata:", r.status_code, r.text)
            return False
        return True
    except Exception as e:
        print("sendPhoto exception:", e)
        return False

# Haber gönderme: foto varsa sendPhoto, yoksa sendMessage
def send_news(title, summary, link, image_url=None):
    try:
        text = f"📢 {title}\n\n{summary}\n\n🔗 {link}"
        if image_url:
            ok = telegram_send_photo(image_url, text)
            if not ok:
                print("Fotoğraf gönderilemedi, text gönderiliyor.")
                telegram_send_text(text)
        else:
            telegram_send_text(text)
    except Exception as e:
        print("send_news exception:", e)

# RSS kontrolü
def check_rss(first_run=False):
    try:
        for rss in RSS_URLS:
            feed = feedparser.parse(rss)
            for entry in getattr(feed, "entries", []):
                try:
                    raw_link = getattr(entry, "link", None)
                    if not raw_link:
                        continue
                    norm = normalize_url(raw_link)
                    if norm in sent_links:
                        continue
                    # tarih filtresi
                    published_time = getattr(entry, "published_parsed", None)
                    if published_time:
                        published_dt = datetime.fromtimestamp(time.mktime(published_time), tz=timezone.utc)
                        if datetime.now(timezone.utc) - published_dt > timedelta(days=1):
                            continue
                    # keyword filtresi
                    content = (getattr(entry, "title", "") + " " + getattr(entry, "summary", "")).lower()
                    if not any(k.strip().lower() in content for k in KEYWORDS):
                        continue
                    # resim çıkar
                    image = extract_image_from_entry(entry)
                    # Eğer first_run True ise gönderimi atlamak istersen burayı kontrol et (biz gönderiyoruz)
                    send_news(getattr(entry, "title", "Haber"), getattr(entry, "summary", ""), raw_link, image)
                    sent_links.add(norm)
                except Exception as e:
                    print("RSS entry işlenirken hata:", e)
    except Exception as e:
        print("check_rss hata:", e)

# Search kontrolü
def check_search():
    try:
        items = fetch_google_news_search(GOOGLE_SEARCH_QUERY, limit=15)
        for it in items:
            try:
                norm = normalize_url(it.get("url") or it.get("norm_url") or "")
                if not norm:
                    continue
                if norm in sent_links:
                    continue
                title = it.get("title") or ""
                snippet = it.get("snippet") or ""
                # keyword kontrol
                if not any(k.strip().lower() in (title + " " + snippet).lower() for k in KEYWORDS):
                    continue
                image = it.get("image") or None
                send_news(title or "Haber", snippet, it.get("url", norm), image)
                sent_links.add(norm)
            except Exception as e:
                print("Search item işlenirken hata:", e)
    except Exception as e:
        print("check_search hata:", e)

# Ana döngü
print("Bot çalışıyor... (RSS + Google Search hibrit)")
first_run = True
while True:
    try:
        # RSS sonra Search
        check_rss(first_run=first_run)
        check_search()
        save_links()
    except Exception as e:
        print("Ana döngü hata:", e)
        traceback.print_exc()
    if first_run:
        first_run = False
    time.sleep(CHECK_INTERVAL)
