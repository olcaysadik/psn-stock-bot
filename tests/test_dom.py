"""Offline rendered-HTML tests. Set RUN_BROWSER_TESTS=true after installing Chromium."""
import os
import unittest
from playwright.sync_api import sync_playwright
import monitor as m

ASIN = "B07K6RYVHR"


@unittest.skipUnless(os.getenv("RUN_BROWSER_TESTS") == "true", "Chromium fixture tests enabled separately")
class RenderedPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def check(self, html):
        page = self.browser.new_page()
        try:
            page.route("**/*", lambda route: route.fulfill(status=200, content_type="text/html", body=html))
            page.goto(m.product_url(ASIN))
            facts = m.inspect_page(page)
            facts["http"] = 200
            return m.classify(ASIN, facts)[0]
        finally:
            page.close()

    def html(self, stock="In stock", button='<input id="add-to-cart-button" type="submit" value="Add to cart">'):
        return f'<h1 id="productTitle">Sony PlayStation Gift Card</h1><input id="ASIN" type="hidden" value="{ASIN}"><div id="availability">{stock}</div>{button}'

    def test_enabled_physical_voucher_control(self):
        self.assertEqual(self.check(self.html()), "IN_STOCK")

    def test_gift_card_form_control(self):
        self.assertEqual(self.check(self.html(button='<div id="gc-buy-box"><button id="gc-buy-box-atc">Buy</button></div>')), "IN_STOCK")
        self.assertEqual(self.check(self.html(button='<input name="submit.gc-buy-now" type="submit" value="Buy now">')), "IN_STOCK")
        self.assertEqual(self.check(self.html(button='<input name="submit.gc-buy-now" type="hidden" value="1">')), "UNKNOWN")

    def test_hidden_disabled_and_aria_disabled_controls(self):
        for attr in ('disabled', 'style="display:none"', 'aria-disabled="true"'):
            with self.subTest(attr=attr):
                self.assertEqual(self.check(self.html(button=f'<button id="buy-now-button" {attr}>Buy now</button>')), "UNKNOWN")
        self.assertEqual(self.check(self.html(button='<span class="a-button-disabled"><button id="buy-now-button">Buy</button></span>')), "UNKNOWN")

    def test_hidden_stock_message_does_not_confirm_stock(self):
        self.assertEqual(self.check(self.html().replace('id="availability"', 'id="availability" style="display:none"')), "UNKNOWN")

    def test_actual_unavailable_markup(self):
        self.assertEqual(self.check(self.html("Currently unavailable", "")), "OUT_OF_STOCK")

    def test_captcha_and_generic_fallback(self):
        self.assertEqual(self.check('<title>Amazon.in</title><form action="/errors/validateCaptcha"><input id="captchacharacters"></form>'), "BLOCKED")
        self.assertEqual(self.check('<title>Amazon.in</title><p>Continue shopping</p>'), "UNKNOWN")
