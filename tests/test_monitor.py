import unittest
from monitor import classify

class Tests(unittest.TestCase):
    def test_amazon_captcha_200(self):
        status, _ = classify(200, "https://www.amazon.in/dp/B093QF35KZ", "Amazon.in", "", "Enter the characters you see", "", False)
        self.assertEqual(status, "BLOCKED")

    def test_page_without_heading_never_in_stock(self):
        status, _ = classify(200, "https://www.amazon.in/dp/B093QF35KZ", "Amazon.in", "", "In Stock now", "In stock", True)
        self.assertEqual(status, "UNKNOWN")

    def test_out_stock(self):
        status, _ = classify(200, "https://www.amazon.in/dp/B093QF35KZ", "PSN - Amazon.in", "Sony PlayStation eGift card", "", "Currently unavailable", False)
        self.assertEqual(status, "OUT_OF_STOCK")

    def test_in_stock(self):
        status, _ = classify(200, "https://www.amazon.in/dp/B093QF35KZ", "PSN - Amazon.in", "Sony PlayStation eGift card", "", "In Stock", True)
        self.assertEqual(status, "IN_STOCK")

    def test_buy_button_only_is_possible(self):
        status, _ = classify(200, "https://www.amazon.in/dp/B093QF35KZ", "PSN - Amazon.in", "Sony PlayStation eGift card", "", "", True)
        self.assertEqual(status, "POSSIBLE")

    def test_http_503(self):
        status, _ = classify(503, "https://www.amazon.in/dp/B093QF35KZ", "Amazon", "Sony PlayStation eGift card", "", "In Stock", True)
        self.assertEqual(status, "BLOCKED")

if __name__ == "__main__":
    unittest.main()
