#!/usr/bin/env python3
"""Conservative Amazon.in monitoring with durable at-most-once Gmail alerts."""
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
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

PRODUCTS = {
    "B07K6RYVHR": "Rs.1000 Sony PlayStation Store Gift Card (Email Delivery in 1 hour- Digital Voucher Code)",
    "B093QF35KZ": "Rs.2000 Sony PlayStation Store Gift Card (Email Delivery in 1 hour- Digital Voucher Code)",
    "B0C1H473H8": "Playstation | E-Gift Card | Instant Delivery | Valid for in-game purchases",
}
ORIGINAL_URLS = {
    "B07K6RYVHR": "https://www.amazon.in/Rs-1000-Sony-PlayStation-Delivery-Digital/dp/B07K6RYVHR",
    "B093QF35KZ": "https://www.amazon.in/Rs-2000-Sony-PlayStation-Network-Delivery/dp/B093QF35KZ",
    "B0C1H473H8": "https://www.amazon.in/Playstation-Gift-Redeemable-Flat-Cashback/dp/B0C1H473H8",
}
ISSUE_TITLE = "[psn-stock-bot-state] Otomatik durum kaydi"
STATE_MARK = "PSN_STOCK_BOT_STATE_V2"
CONFIRMED = {"IN_STOCK", "OUT_OF_STOCK"}
CAPTCHA_PATTERNS = (
    "enter the characters you see", "type the characters you see", "robot check",
    "validatecaptcha", "make sure you're not a robot", "verify you are human",
    "verify that you're not a robot", "click the button below to continue shopping",
)
OUT_PATTERNS = (
    "currently unavailable", "temporarily out of stock", "out of stock", "sold out",
    "not currently available", "currently not available", "not in stock", "no longer available",
    "we don't know when or if this item will be back in stock",
)
IN_PATTERN = re.compile(
    r"^\s*(?:in stock|available now|only\s+\d+\s+left in stock(?:\s*[-–—,]\s*order soon)?)[.!]?\s*$",
    re.I | re.M,
)
AVAILABILITY_SELECTORS = (
    "#availability", "#availabilityInsideBuyBox_feature_div", "#outOfStock",
    "#availability_feature_div", "#gc-availability", "#gcAvailability",
)
PURCHASE_SELECTORS = (
    "#buy-now-button", "#add-to-cart-button", "#gc-buy-box-atc",
    "#gc-buy-box-buynow", "#gc-buy-box-buy-now", "input[name='submit.add-to-cart']",
    "input[name='submit.gc-buy-now']",
)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def product_url(asin):
    return f"https://www.amazon.in/dp/{asin}"


def safe_url(url):
    """Remove query strings, fragments and userinfo before persisting URLs."""
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.hostname or "", parsed.path, "", ""))


def identify(asin, url, heading, page_asins):
    parsed = urlsplit(url)
    url_asin = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})(?:/|$)", parsed.path)
    name = heading.lower()
    return bool(
        parsed.scheme == "https" and parsed.hostname in {"www.amazon.in", "amazon.in"}
        and url_asin and url_asin.group(1) == asin and set(page_asins) == {asin}
        and re.search(r"\b(?:playstation|psn)\b", name)
        and re.search(r"\b(?:gift|voucher|wallet)\b", name)
    )


def classify(asin, facts):
    challenge = bool(facts.get("challenge_element")) or any(
        marker in facts.get(field, "").lower()
        for marker in CAPTCHA_PATTERNS for field in ("body", "title", "url")
    )
    if challenge:
        return "BLOCKED", "Amazon verification/CAPTCHA page", False, True
    http = facts.get("http", 0)
    if http in {403, 429, 503}:
        return "BLOCKED", f"HTTP {http}: access denied or service unavailable", False, False
    identified = identify(asin, facts.get("url", ""), facts.get("heading", ""), facts.get("page_asins", []))
    if http != 200 or not identified:
        return "UNKNOWN", "HTTP failure or exact product identity not verified", identified, False
    availability = " ".join(facts.get("availability", [])).lower()
    out = any(term in availability for term in OUT_PATTERNS)
    in_stock = any(IN_PATTERN.search(chunk) for chunk in facts.get("availability", []))
    purchase = bool(facts.get("purchase_enabled"))
    if out and (in_stock or purchase):
        return "UNKNOWN", "Conflicting availability and purchase signals", True, False
    if out:
        return "OUT_OF_STOCK", "Explicit product availability says unavailable", True, False
    if in_stock and purchase:
        return "IN_STOCK", "Explicit availability and visible enabled purchase control", True, False
    return "UNKNOWN", "No unambiguous availability plus purchase confirmation", True, False


def inspect_page(page):
    """Read rendered product fields; never treat recommendations/prices as stock."""
    facts = page.evaluate("""({availabilitySelectors, purchaseSelectors}) => {
      const visible = e => !!e && !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length)
        && getComputedStyle(e).visibility !== 'hidden';
      const heading = [...document.querySelectorAll('#productTitle, h1#title, #gc-title, h1')]
        .find(e => visible(e) && e.innerText.trim());
      const asins = [...document.querySelectorAll('input#ASIN, input[name="ASIN"], #gc-asin')]
        .map(e => (e.value || e.textContent || '').trim()).filter(Boolean);
      const controls = purchaseSelectors.flatMap(s => [...document.querySelectorAll(s)]).filter(visible);
      const enabled = e => !e.disabled && e.getAttribute('aria-disabled') !== 'true'
        && !e.closest('[aria-disabled="true"], .a-button-disabled')
        && getComputedStyle(e).pointerEvents !== 'none';
      return {
        title: document.title, heading: heading?.innerText.trim() || '',
        body: document.body?.innerText || '', page_asins: [...new Set(asins)],
        availability: availabilitySelectors.flatMap(s => [...document.querySelectorAll(s)])
          .filter(visible).map(e => e.innerText.trim()).filter(Boolean),
        purchase_enabled: controls.some(enabled),
        purchase_controls: controls.map(e => ({id:e.id, enabled:!!enabled(e)})),
        challenge_element: !!document.querySelector('form[action*="validateCaptcha"], #captchacharacters, input[name="cvf_captcha_input"]'),
        gift_card_form: !!document.querySelector('#gc-buy-box, #gc-amount, #gc-customization-form, #gc-order-form-asin, #gc-order-form-type')
      };
    }""", {"availabilitySelectors": AVAILABILITY_SELECTORS, "purchaseSelectors": PURCHASE_SELECTORS})
    facts["url"] = page.url
    return facts


def browser_check(asin, browser, target, output_dir, label):
    context = browser.new_context(locale="en-IN", timezone_id="Asia/Kolkata", viewport={"width": 1365, "height": 1000})
    page = context.new_page()
    page.set_default_timeout(5000)
    facts = {"http": 0, "url": target, "title": "", "heading": "", "availability": [], "page_asins": []}
    error = None
    try:
        response = page.goto(target, wait_until="domcontentloaded", timeout=35000)
        facts["http"] = response.status if response else 0
        try:
            page.locator("#productTitle, #captchacharacters, #gc-title, #availability").first.wait_for(timeout=5000)
        except Exception:
            pass
        page.wait_for_timeout(1500)
        facts.update(inspect_page(page))
    except Exception as exc:
        error = type(exc).__name__  # Exception payloads can contain sensitive URLs.
        facts["url"] = page.url
        try:
            facts.update(inspect_page(page))
        except Exception:
            pass
    status, reason, identified, captcha = classify(asin, facts)
    if error:
        status, reason = "UNKNOWN", f"Navigation/inspection failed: {error}"
    result = {k: v for k, v in facts.items() if k != "body"}
    result.update(asin=asin, requested_url=safe_url(target), url=safe_url(facts["url"]),
                  status=status, reason=reason, identified=identified, captcha=captcha,
                  detected_at=now(), body_length=len(facts.get("body", "")), error=error)
    try:
        screenshot = output_dir / f"{asin}-{label}.png"
        page.screenshot(path=str(screenshot), full_page=False, timeout=8000,
                        mask=[page.locator("#nav-tools, #glow-ingress-block, input, textarea")])
        result["screenshot"] = screenshot.name
    except Exception as exc:
        result["screenshot_error"] = type(exc).__name__
    finally:
        context.close()
    return result


def collect(mode, output_dir):
    from playwright.sync_api import sync_playwright
    attempts = {asin: [] for asin in PRODUCTS}
    results = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            # Two rounds in independent contexts compare short and original URLs.
            for round_number in range(2 if mode == "diagnose" else 1):
                for asin in PRODUCTS:
                    targets = [product_url(asin), ORIGINAL_URLS[asin]] if mode == "diagnose" else [product_url(asin)]
                    for variant, target in enumerate(targets):
                        label = f"r{round_number + 1}-v{variant + 1}"
                        try:
                            result = browser_check(asin, browser, target, output_dir, label)
                        except Exception as exc:
                            result = {"asin": asin, "status": "UNKNOWN", "reason": type(exc).__name__,
                                      "http": 0, "url": safe_url(target), "identified": False,
                                      "captcha": False, "detected_at": now()}
                        attempts[asin].append(result)
                        print(json.dumps(result, ensure_ascii=True), flush=True)
                    if mode == "monitor" and attempts[asin][-1]["status"] == "UNKNOWN":
                        time.sleep(2)  # One bounded transient retry; no CAPTCHA retries.
                        try:
                            retry = browser_check(asin, browser, product_url(asin), output_dir, "retry")
                            attempts[asin].append(retry)
                            print(json.dumps(retry, ensure_ascii=True), flush=True)
                        except Exception:
                            pass
            for asin, checks in attempts.items():
                latest = dict(checks[-1])
                if mode == "diagnose" and (any(c["status"] not in CONFIRMED for c in checks)
                                           or len({c["status"] for c in checks}) != 1):
                    latest["status"] = "BLOCKED" if any(c["status"] == "BLOCKED" for c in checks) else "UNKNOWN"
                    latest["reason"] = "Repeated short/original URL checks did not yield consistent confirmed stock"
                    latest["identified"] = all(c["identified"] for c in checks)
                    latest["captcha"] = any(c["captcha"] for c in checks)
                results[asin] = latest
        finally:
            browser.close()
    report = {"generated_at": now(), "mode": mode, "results": results, "attempts": attempts,
              "all_products_confirmed": all(r["status"] in CONFIRMED for r in results.values())}
    (output_dir / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    summary = ["# Amazon India diagnostic results", "", "| ASIN | Status | HTTP | Product verified | CAPTCHA |", "|---|---|---|---|---|"]
    for asin, result in results.items():
        summary.append(f"| {asin} | {result['status']} | {result['http']} | {result['identified']} | {result['captcha']} |")
    summary += ["", "Real access requires consistent confirmed results for every product.",
                "diagnose sends no email and changes no stock history. Screenshots use fresh anonymous contexts."]
    markdown = "\n".join(summary) + "\n"
    (output_dir / "summary.md").write_text(markdown, encoding="utf-8")
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as file:
            file.write(markdown)
    return results, report["all_products_confirmed"]


def github_api(method, endpoint, data=None):
    token = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
    repo = os.getenv("GITHUB_REPOSITORY", "")
    if not token or not re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
        raise RuntimeError("GitHub state requires GITHUB_TOKEN and GITHUB_REPOSITORY")
    payload = json.dumps(data).encode() if data is not None else None
    req = Request(f"https://api.github.com/repos/{repo}/{endpoint}", data=payload, method=method,
                  headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                           "Content-Type": "application/json", "User-Agent": "psn-stock-bot",
                           "X-GitHub-Api-Version": "2022-11-28"})
    for attempt in range(3):
        try:
            with urlopen(req, timeout=20) as response:
                return json.load(response)
        except (HTTPError, URLError, TimeoutError) as exc:
            if method != "GET" or attempt == 2 or (isinstance(exc, HTTPError) and exc.code not in {429, 500, 502, 503, 504}):
                raise RuntimeError(f"GitHub state {method} failed ({type(exc).__name__}); notifications stopped") from None
            time.sleep(2 ** attempt)


def validate_state(state):
    if not isinstance(state, dict) or state.get("version") != 2 or not isinstance(state.get("products"), dict):
        raise RuntimeError("Invalid persistent state; refusing to reset notification history")
    for entry in state["products"].values():
        if (not isinstance(entry, dict) or entry.get("last_confirmed") not in CONFIRMED | {"UNKNOWN"}
                or entry.get("notification") not in {"armed", "reserved", "sent", "uncertain"}
                or type(entry.get("failures")) is not int or entry["failures"] < 0):
            raise RuntimeError("Invalid product state; refusing notifications")
    return state


class IssueStore:
    """Durable issue state, serialized by the workflow's fixed concurrency group."""
    def __init__(self):
        self.number = None

    def load(self):
        matches = []
        owner = os.environ["GITHUB_REPOSITORY"].split("/")[0].lower()
        page = 1
        while True:
            issues = github_api("GET", f"issues?state=all&per_page=100&page={page}")
            matches.extend(i for i in issues if i.get("title") == ISSUE_TITLE and "pull_request" not in i)
            if len(issues) < 100:
                break
            page += 1
        if len(matches) > 1:
            raise RuntimeError("Multiple state issues; refusing to guess")
        if not matches:
            state = {"version": 2, "products": {}}
            response = github_api("POST", "issues", {"title": ISSUE_TITLE, "body": self.encode(state)})
            if response.get("body") != self.encode(state):
                raise RuntimeError("Initial persistent state write not confirmed")
            self.number = response["number"]
            return state
        issue = matches[0]
        if issue.get("user", {}).get("login", "").lower() not in {owner, "github-actions[bot]"}:
            raise RuntimeError("State issue has an untrusted author")
        self.number = issue["number"]
        raw = issue.get("body") or ""
        if not raw.startswith(STATE_MARK + "\n"):
            raise RuntimeError("Unknown/legacy state format; audited migration required")
        return validate_state(json.loads(raw.split("\n", 1)[1]))

    @staticmethod
    def encode(state):
        return STATE_MARK + "\n" + json.dumps(validate_state(state), indent=2, ensure_ascii=False)

    def save(self, state):
        body = self.encode(state)
        response = github_api("PATCH", f"issues/{self.number}", {"body": body})
        if response.get("body") != body:
            raise RuntimeError("Persistent state write not confirmed; no email allowed")


def smtp_settings():
    settings = {name: os.getenv(name, "").strip() for name in ("SMTP_USER", "SMTP_APP_PASSWORD", "ALERT_EMAIL")}
    missing = [name for name, value in settings.items() if not value]
    if missing:
        raise RuntimeError("Missing GitHub Actions secrets: " + ", ".join(missing))
    return settings


def send_gmail(subject, message):
    settings = smtp_settings()
    mail = EmailMessage()
    mail["From"], mail["To"], mail["Subject"] = settings["SMTP_USER"], settings["ALERT_EMAIL"], subject
    mail.set_content(message)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context(), timeout=25) as smtp:
        smtp.login(settings["SMTP_USER"], settings["SMTP_APP_PASSWORD"].replace(" ", ""))
        if smtp.send_message(mail):
            raise RuntimeError("SMTP recipient not accepted")


def process_results(results, state, save, send):
    """Reserve durably BEFORE SMTP. Ambiguous delivery never retries automatically."""
    errors = []
    for asin, result in results.items():
        entry = state["products"].setdefault(asin, {"last_confirmed": "UNKNOWN", "notification": "armed", "failures": 0})
        status = result["status"]
        entry["last_observed"] = status
        entry["checked_at"] = result["detected_at"]
        if status not in CONFIRMED:
            entry["failures"] += 1
            save(state)
            continue
        entry["failures"] = 0
        entry["last_confirmed"] = status
        if status == "OUT_OF_STOCK":
            entry["notification"] = "armed"
            save(state)
            continue
        if entry["notification"] != "armed":
            save(state)
            continue
        entry["notification"] = "reserved"
        entry["notification_reserved_at"] = now()
        save(state)  # Failure stops the run before email.
        heading = result.get("heading") or PRODUCTS[asin]
        message = (f"Product: {heading}\nASIN: {asin}\nURL: {product_url(asin)}\n"
                   f"Confirmed availability: IN_STOCK\nDetection timestamp (UTC): {result['detected_at']}\n\n"
                   "Verified on the anonymous Amazon India page. Account/location eligibility may differ.")
        try:
            send(f"PSN GIFT CARD AVAILABLE - {asin}", message)
        except Exception as exc:
            entry["notification"] = "uncertain"
            entry["notification_error"] = type(exc).__name__
            save(state)
            errors.append(asin)
            print(f"EMAIL_UNCERTAIN {asin}: delivery not confirmed; automatic retry suppressed", flush=True)
            continue
        entry["notification"] = "sent"
        entry["notification_sent_at"] = now()
        save(state)
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("diagnose", "monitor", "test"), default="diagnose")
    parser.add_argument("--output-dir", type=Path, default=Path("diagnostics"))
    args = parser.parse_args()
    if args.mode == "test":
        send_gmail("PSN STOCK BOT - Gmail test", "SMTP test only. This is not a stock alert.\nUTC: " + now())
        print("Gmail SMTP accepted the test email; verify receipt in inbox/spam.")
        return 0
    if args.mode == "monitor":
        if os.getenv("BOT_ENABLED") != "true":
            raise RuntimeError("Monitoring disabled. Validate real diagnostics before setting BOT_ENABLED=true")
        if os.getenv("GITHUB_ACTIONS") != "true":
            raise RuntimeError("Monitor mode requires the serialized GitHub Actions workflow")
        smtp_settings()
        store = IssueStore()
        state = store.load()  # Never send after a failed/corrupt history read.
    args.output_dir.mkdir(parents=True, exist_ok=True)
    results, verified = collect(args.mode, args.output_dir)
    if args.mode == "diagnose":
        print("DIAGNOSE: no email sent, no stock history changed.")
        return 0 if verified else 2
    errors = process_results(results, state, store.save, send_gmail)
    return 1 if errors else (0 if verified else 2)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        if isinstance(exc, RuntimeError):
            print(f"ERROR: {exc}", file=sys.stderr)
        else:
            print(f"ERROR: {type(exc).__name__} (details suppressed)", file=sys.stderr)
        sys.exit(1)
