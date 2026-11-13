#!/usr/bin/env python3
"""Amazon.in PSN gift-card watcher with conservative parsing and persistent GitHub Issue state.

Does not solve or bypass CAPTCHAs. Never treats a challenge page as an in-stock product.
"""
import argparse
import json
import os
import re
import smtplib
import ssl
import sys
import time
from datetime import datetime, timezone
from email.message import EmailMessage
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PRODUCTS = {
    "B093QF35KZ": "Amazon India PSN Gift Card (B093QF35KZ)",
    "B0C1H473H8": "Amazon India PSN Gift Card (B0C1H473H8)",
}
ISSUE_TITLE = "[psn-stock-bot-state] Otomatik durum kaydi"
CAPTCHA_PATTERNS = (
    "enter the characters you see",
    "type the characters you see",
    "robot check",
    "validatecaptcha",
    "sorry, we just need to make sure you're not a robot",
)
OUT_PATTERNS = (
    "currently unavailable", "temporarily out of stock", "out of stock",
    "we don't know when or if this item will be back in stock",
    "not currently available", "currently not available", "sold out",
)
IN_PATTERN = re.compile(r"\bin stock\b|\bavailable now\b|only \d+ left in stock", re.I)
STATE_MARK = "PSN_STOCK_BOT_STATE_V1"


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def classify(status_code, url, title, heading, body, availability, buy_button):
    """Classify as BLOCKED, OUT_OF_STOCK, IN_STOCK, POSSIBLE or UNKNOWN.

    Only information from an identified product page can produce a stock result.
    """
    low_title = (title or "").lower()
    low_body = (body or "").lower()
    low_avail = (availability or "").lower()
    low_heading = (heading or "").lower()
    if status_code in (403, 429, 503):
        return "BLOCKED", f"HTTP {status_code}"
    if status_code != 200:
        return "UNKNOWN", f"HTTP {status_code}"
    if ("robot check" in low_title or "captcha" in low_title or
            any(term in low_body[:1400] for term in CAPTCHA_PATTERNS)):
        return "BLOCKED", "CAPTCHA / robot verification"
    # Never infer availability from an Amazon landing page or a generic redirect.
    if not heading or not any(word in low_heading for word in ("playstation", "psn", "sony")):
        return "UNKNOWN", "PSN urun basligi dogrulanamadi"
    if "amazon.in" not in url.lower():
        return "UNKNOWN", "Amazon.in disina yonlendirildi"
    if any(term in low_avail for term in OUT_PATTERNS):
        return "OUT_OF_STOCK", "Urunun availability alaninda stok yok"
    if any(term in low_avail for term in ("in stock", "available now")) and not any(term in low_avail for term in OUT_PATTERNS):
        return "IN_STOCK", "Availability alaninda stok var"
    if IN_PATTERN.search(low_avail):
        return "IN_STOCK", "Availability alaninda stok var"
    # Product-wide text can contain unrelated recommendations. Limit the search to
    # the leading portion of the page and only use it for out-of-stock exclusions.
    if any(term in low_body[:5000] for term in OUT_PATTERNS):
        return "OUT_OF_STOCK", "Urun sayfasinda stok yok ifadesi"
    if buy_button:
        return "POSSIBLE", "Satin alma butonu gorunur; stok kesin degil"
    return "UNKNOWN", "Stok bilgisi belirsiz"


def browser_check(asin, browser):
    page = browser.new_page(locale="en-IN", timezone_id="Asia/Kolkata")
    page.set_default_timeout(10000)
    target = f"https://www.amazon.in/dp/{asin}"
    try:
        response = page.goto(target, wait_until="domcontentloaded", timeout=35000)
        page.wait_for_timeout(1100)
        http = response.status if response else 0
        title = page.title()
        try:
            body = page.locator("body").inner_text(timeout=7000)[:16000]
        except Exception:
            body = ""
        heading = ""
        for selector in ("#productTitle", "#title span", "h1#title", "h1.a-size-large"):
            loc = page.locator(selector).first
            if loc.count():
                try:
                    heading = loc.inner_text(timeout=2500).strip()
                except Exception:
                    continue
                if heading:
                    break
        available_chunks = []
        for selector in ("#availability", "#availabilityInsideBuyBox_feature_div",
                         "#outOfStock", "#availability_feature_div"):
            loc = page.locator(selector).first
            if loc.count():
                try:
                    available_chunks.append(loc.inner_text(timeout=2000))
                except Exception:
                    pass
        buy_button = False
        for selector in ("#buy-now-button", "#add-to-cart-button", "input[name='submit.add-to-cart']"):
            loc = page.locator(selector).first
            if loc.count():
                try:
                    if loc.is_visible():
                        buy_button = True
                        break
                except Exception:
                    pass
        status, reason = classify(http, page.url, title, heading, body, " | ".join(available_chunks), buy_button)
        return {"status": status, "reason": reason, "http": http,
                "title": title[:110], "heading": heading[:110], "page_url": page.url}
    except Exception as exc:
        return {"status": "UNKNOWN", "reason": type(exc).__name__ + ": " + str(exc)[:130],
                "http": 0, "title": "", "heading": "", "page_url": target}
    finally:
        page.close()


def github_api(method, endpoint, data=None):
    token = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
    repo = os.getenv("GITHUB_REPOSITORY")
    if not token or not repo:
        raise RuntimeError("GitHub state API icin GITHUB_TOKEN / GITHUB_REPOSITORY yok")
    payload = json.dumps(data).encode("utf-8") if data is not None else None
    req = Request(f"https://api.github.com/repos/{repo}/{endpoint}", data=payload, method=method,
                  headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                           "Content-Type": "application/json", "User-Agent": "psn-stock-bot"})
    with urlopen(req, timeout=20) as res:
        return json.load(res)


def get_saved_state():
    if not os.getenv("GITHUB_REPOSITORY"):
        try:
            with open("state.json", "r", encoding="utf-8") as file:
                return json.load(file), None
        except FileNotFoundError:
            return {"products": {}}, None
    issues = github_api("GET", "issues?state=all&per_page=100")
    issue = next((i for i in issues if i.get("title") == ISSUE_TITLE and "pull_request" not in i), None)
    if not issue:
        return {"products": {}}, None
    raw = (issue.get("body") or "").strip()
    if not raw.startswith(STATE_MARK + "\n"):
        raise RuntimeError("Bot durum issue icerigi beklenmedik bicimde: elle degistirmeyin")
    return json.loads(raw.split("\n", 1)[1]), issue["number"]


def save_state(state, issue_number):
    if not os.getenv("GITHUB_REPOSITORY"):
        with open("state.json", "w", encoding="utf-8") as file:
            json.dump(state, file, ensure_ascii=False, indent=2)
        return
    body = STATE_MARK + "\n" + json.dumps(state, ensure_ascii=False, indent=2)
    if issue_number:
        github_api("PATCH", f"issues/{issue_number}", {"body": body})
    else:
        github_api("POST", "issues", {"title": ISSUE_TITLE, "body": body})


def send_gmail(subject, message):
    sender = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_APP_PASSWORD", "").replace(" ", "")
    recipient = os.getenv("ALERT_EMAIL", "").strip()
    if not (sender and password and recipient):
        return False
    mail = EmailMessage()
    mail["From"] = sender
    mail["To"] = recipient
    mail["Subject"] = subject
    mail.set_content(message)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context(), timeout=20) as smtp:
        smtp.login(sender, password)
        smtp.send_message(mail)
    return True


def send_telegram(message):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat:
        return False
    req = Request(f"https://api.telegram.org/bot{token}/sendMessage",
                  data=json.dumps({"chat_id": chat, "text": message,
                                   "disable_web_page_preview": False}).encode("utf-8"),
                  headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(req, timeout=20) as res:
        data = json.load(res)
    if not data.get("ok"):
        raise RuntimeError("Telegram sendMessage failed")
    return True


def notify(subject, message):
    methods = []
    # An enabled notification channel must work; don't silently swallow errors.
    if send_gmail(subject, message):
        methods.append("Gmail")
    if send_telegram(subject + "\n\n" + message):
        methods.append("Telegram")
    if not methods:
        raise RuntimeError("Bildirim yapilandirilmamis: Gmail secrets veya Telegram secrets ekle")
    print("BILDIRIM: " + ", ".join(methods))


def run(mode):
    if mode == "test":
        notify("PSN stok botu test", "Test basarili: mesaj bot tarafindan gonderildi.\n" + now())
        return
    # Import browser tools only when actually running a page check.
    from playwright.sync_api import sync_playwright
    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for asin in PRODUCTS:
                result = browser_check(asin, browser)
                results[asin] = result
                print(f"URUN {asin} / {result['status']} / HTTP {result['http']} / {result['reason']} / {result['title']}")
        finally:
            browser.close()
    if mode == "diagnose":
        print("DIAGNOSE: Sadece rapor verildi. Bildirim gonderilmedi, durum yazilmadi.")
        if not all(r["status"] in ("IN_STOCK", "OUT_OF_STOCK", "POSSIBLE") for r in results.values()):
            print("UYARI: En az bir urunde dogrulanmis sayfa okunamadi. Zamanlayiciyi guvenilir saymayin.")
        return

    state, issue_number = get_saved_state()
    prodstate = state.setdefault("products", {})
    dirty = False
    errors = []
    for asin, result in results.items():
        result_state = result["status"]
        entry = prodstate.setdefault(asin, {"last_known": "UNKNOWN", "failures": 0, "error_alerted": False})
        old = dict(entry)
        url = f"https://www.amazon.in/dp/{asin}"
        if result_state in ("BLOCKED", "UNKNOWN"):
            entry["failures"] = int(entry.get("failures", 0)) + 1
            if entry["failures"] >= 3 and not entry.get("error_alerted"):
                errors.append((asin, result))
        else:
            entry["failures"] = 0
            entry["error_alerted"] = False
            previous = entry.get("last_known", "UNKNOWN")
            if result_state in ("IN_STOCK", "POSSIBLE") and previous not in ("IN_STOCK", "POSSIBLE"):
                subject = ("PSN STOKTA!" if result_state == "IN_STOCK" else "PSN SATIN ALMA SINYALI") + " " + asin
                msg = (f"Urun: {PRODUCTS[asin]}\nDurum: {result_state}\n"
                       f"Amazon: {url}\nZaman (UTC): {now()}\n\n"
                       "Not: Alim islemini Amazon sitesinde kendin dogrula. "
                       "'POSSIBLE' kesin stok anlamina gelmez.")
                notify(subject, msg)
            entry["last_known"] = result_state
        if entry != old:
            dirty = True
    for asin, result in errors:
        notify("PSN BOT ERISIM SORUNU " + asin,
               f"Urun {asin} son 3+ kontrolde okunamadi.\nSebep: {result['reason']}\n"
               f"Link: https://www.amazon.in/dp/{asin}\nBu stok bildirimi degildir.")
        prodstate[asin]["error_alerted"] = True
        dirty = True
    if dirty or issue_number is None:
        state["updated_at_utc"] = now()
        save_state(state, issue_number)
        print("Durum GitHub issue / yerel state.json icerisinde guncellendi")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("diagnose", "monitor", "test"), default="diagnose")
    args = parser.parse_args()
    run(args.mode)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("HATA: " + str(exc), file=sys.stderr)
        sys.exit(1)
