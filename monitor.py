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
    "B07K6RYVHR": "Amazon India Sony PlayStation Rs. 1000 Gift Card (B07K6RYVHR)",
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
