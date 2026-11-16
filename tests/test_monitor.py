import copy
import json
import os
import sys
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import yaml
import monitor as m

ASIN = "B07K6RYVHR"


def facts(**overrides):
    data = {"http": 200, "url": m.product_url(ASIN), "title": "PlayStation - Amazon.in",
            "heading": "Rs.1000 Sony PlayStation Store Gift Card", "page_asins": [ASIN],
            "body": "", "availability": ["In stock"], "purchase_enabled": True}
    data.update(overrides)
    return data


def result(status="IN_STOCK"):
    return {"status": status, "detected_at": "2026-11-13T18:00:00+00:00", "heading": "Actual PlayStation Gift Card title"}


class ClassificationTests(unittest.TestCase):
    def status(self, **overrides):
        return m.classify(ASIN, facts(**overrides))[0]

    def test_confirmed_stock_requires_identity_availability_and_enabled_control(self):
        self.assertEqual(self.status(), "IN_STOCK")
        self.assertEqual(self.status(purchase_enabled=False), "UNKNOWN")
        self.assertEqual(self.status(availability=[]), "UNKNOWN")

    def test_explicit_out_of_stock(self):
        for text in m.OUT_PATTERNS:
            with self.subTest(text=text):
                self.assertEqual(self.status(availability=[text], purchase_enabled=False), "OUT_OF_STOCK")

    def test_contradictory_signals(self):
        self.assertEqual(self.status(availability=["Currently unavailable"]), "UNKNOWN")
        self.assertEqual(self.status(availability=["In stock", "Currently unavailable"], purchase_enabled=False), "UNKNOWN")

    def test_captcha_http_200_and_late_body_marker(self):
        for marker in m.CAPTCHA_PATTERNS:
            with self.subTest(marker=marker):
                self.assertEqual(self.status(body="X" * 6000 + marker), "BLOCKED")
        self.assertEqual(self.status(challenge_element=True), "BLOCKED")

    def test_http_errors(self):
        for code in (403, 429, 503):
            self.assertEqual(self.status(http=code), "BLOCKED")
        for code in (0, 404, 500):
            self.assertEqual(self.status(http=code), "UNKNOWN")

    def test_continue_shopping_is_blocked_not_a_visual_captcha(self):
        classified = m.classify(ASIN, facts(body="Click the button below to continue shopping"))
        self.assertEqual(classified[0], "BLOCKED")
        self.assertFalse(classified[3])

    def test_fallback_page_and_wrong_title(self):
        for heading in ("", "Sony television", "PlayStation console", "Amazon.in"):
            self.assertEqual(self.status(heading=heading), "UNKNOWN")

    def test_exact_asin_verification(self):
        for asins in ([], ["B093QF35KZ"], [ASIN, "B093QF35KZ"]):
            self.assertEqual(self.status(page_asins=asins), "UNKNOWN")
        self.assertEqual(self.status(url=m.product_url("B093QF35KZ")), "UNKNOWN")

    def test_host_and_redirect_validation(self):
        for url in ("https://amazon.in.evil.example/dp/" + ASIN,
                    "https://evil.example/amazon.in/dp/" + ASIN,
                    "https://www.amazon.in/", "https://www.amazon.in/ap/signin",
                    "http://www.amazon.in/dp/" + ASIN):
            self.assertEqual(self.status(url=url), "UNKNOWN")

    def test_prices_recommendations_and_buttons_alone_are_not_stock(self):
        self.assertEqual(self.status(availability=[], body="In stock, Rs.1000, Buy Now"), "UNKNOWN")
        self.assertEqual(self.status(availability=["In stock"], body="Other product currently unavailable"), "IN_STOCK")
        self.assertEqual(self.status(availability=[], body="Other product out of stock", purchase_enabled=False), "UNKNOWN")

    def test_negated_and_future_stock_are_not_positive(self):
        for text in ("Not available now", "May be back in stock soon", "Will be in stock next week",
                     "In stock from 17 November", "Available now for pre-order"):
            with self.subTest(text=text):
                self.assertEqual(self.status(availability=[text]), "UNKNOWN")
        self.assertEqual(self.status(availability=["Only 2 left in stock"]), "IN_STOCK")

    def test_original_and_short_url_identity(self):
        for asin in m.PRODUCTS:
            for url in (m.product_url(asin), m.ORIGINAL_URLS[asin]):
                self.assertTrue(m.identify(asin, url, "PlayStation e-Gift Card", [asin]))

    def test_url_sanitization(self):
        self.assertEqual(m.safe_url("https://user:password@www.amazon.in/dp/ABC?token=secret#private"),
                         "https://www.amazon.in/dp/ABC")


class StateTests(unittest.TestCase):
    def setUp(self):
        self.state = {"version": 2, "products": {}}
        self.durable = copy.deepcopy(self.state)
        self.emails = []

    def save(self, state):
        self.durable = json.loads(json.dumps(state))

    def send(self, subject, body):
        self.assertEqual(self.durable["products"][ASIN]["notification"], "reserved")
        self.emails.append((subject, body))

    def run_status(self, status):
        m.process_results({ASIN: result(status)}, self.state, self.save, self.send)

    def test_duplicates_suppressed_across_fresh_runner_and_uncertain_results(self):
        self.run_status("IN_STOCK")
        self.state = copy.deepcopy(self.durable)
        for status in ("UNKNOWN", "BLOCKED", "IN_STOCK", "IN_STOCK"):
            self.run_status(status)
        self.assertEqual(len(self.emails), 1)
        self.assertEqual(self.state["products"][ASIN]["last_confirmed"], "IN_STOCK")

    def test_restock_alert_after_confirmed_out_of_stock(self):
        for status in ("IN_STOCK", "UNKNOWN", "OUT_OF_STOCK", "BLOCKED", "IN_STOCK", "IN_STOCK"):
            self.run_status(status)
        self.assertEqual(len(self.emails), 2)

    def test_initial_out_of_stock_sends_nothing(self):
        self.run_status("OUT_OF_STOCK")
        self.assertEqual(self.emails, [])

    def test_failures_preserve_confirmed_history(self):
        for status in ("OUT_OF_STOCK", "UNKNOWN", "BLOCKED"):
            self.run_status(status)
        entry = self.state["products"][ASIN]
        self.assertEqual(entry["failures"], 2)
        self.assertEqual(entry["last_confirmed"], "OUT_OF_STOCK")

    def test_state_failure_prevents_email(self):
        with self.assertRaises(RuntimeError):
            m.process_results({ASIN: result()}, self.state, Mock(side_effect=RuntimeError()), self.send)
        self.assertEqual(self.emails, [])

    def test_crash_after_delivery_before_ack_does_not_duplicate(self):
        def save_with_crash(state):
            if state["products"][ASIN]["notification"] == "sent":
                raise RuntimeError("runner lost")
            self.save(state)
        with self.assertRaises(RuntimeError):
            m.process_results({ASIN: result()}, self.state, save_with_crash, self.send)
        self.state = copy.deepcopy(self.durable)
        self.run_status("IN_STOCK")
        self.assertEqual(len(self.emails), 1)

    def test_smtp_ambiguity_suppresses_retry_but_other_products_continue(self):
        other = "B093QF35KZ"
        sender = Mock(side_effect=[TimeoutError("SMTP timeout"), None])
        errors = m.process_results({ASIN: result(), other: result()}, self.state, self.save, sender)
        self.assertEqual(errors, [ASIN])
        self.assertEqual(self.state["products"][other]["notification"], "sent")
        self.assertEqual(self.state["products"][ASIN]["notification"], "uncertain")
        self.run_status("IN_STOCK")
        self.assertEqual(self.emails, [])

    def test_email_contains_exact_detected_title_asin_url_and_time(self):
        self.run_status("IN_STOCK")
        subject, body = self.emails[0]
        self.assertEqual(subject, "PSN GIFT CARD AVAILABLE - " + ASIN)
        for value in (ASIN, result()["heading"], m.product_url(ASIN), "IN_STOCK", result()["detected_at"]):
            self.assertIn(value, body)

    @patch.dict(os.environ, {"GITHUB_REPOSITORY": "owner/psn-stock-bot"})
    def test_issue_store_roundtrip_across_instances(self):
        issue = {"number": 17, "title": m.ISSUE_TITLE, "body": m.IssueStore.encode(self.state),
                 "user": {"login": "github-actions[bot]"}}
        def api(method, endpoint, data=None):
            if method == "GET":
                return [copy.deepcopy(issue)]
            issue.update(data)
            return copy.deepcopy(issue)
        with patch.object(m, "github_api", side_effect=api):
            first = m.IssueStore()
            state = first.load()
            m.process_results({ASIN: result()}, state, first.save, Mock())
            second = m.IssueStore()
            state = second.load()
            sender = Mock()
            m.process_results({ASIN: result()}, state, second.save, sender)
            sender.assert_not_called()

    @patch.dict(os.environ, {"GITHUB_REPOSITORY": "owner/psn-stock-bot"})
    def test_corrupt_or_legacy_history_is_not_reset(self):
        for body in ("broken", "PSN_STOCK_BOT_STATE_V1\n{}", m.STATE_MARK + '\n{"version":2,"products":[]}'):
            issue = {"number": 17, "title": m.ISSUE_TITLE, "body": body, "user": {"login": "owner"}}
            with patch.object(m, "github_api", return_value=[issue]):
                with self.assertRaises(RuntimeError):
                    m.IssueStore().load()

    @patch.dict(os.environ, {"GITHUB_REPOSITORY": "owner/psn-stock-bot"})
    def test_paginated_issue_lookup_and_duplicate_rejection(self):
        first = [{"title": "Other issue"}] * 100
        state_issue = {"number": 3, "title": m.ISSUE_TITLE, "body": m.IssueStore.encode(self.state), "user": {"login": "owner"}}
        with patch.object(m, "github_api", side_effect=[first, [state_issue]]) as api:
            self.assertEqual(m.IssueStore().load(), self.state)
            self.assertIn("page=2", api.call_args.args[1])
        with patch.object(m, "github_api", return_value=[state_issue, state_issue]):
            with self.assertRaises(RuntimeError):
                m.IssueStore().load()

    def test_unconfirmed_state_write_raises(self):
        store = m.IssueStore()
        store.number = 17
        with patch.object(m, "github_api", return_value={"body": "wrong"}):
            with self.assertRaises(RuntimeError):
                store.save(self.state)


class ConfigurationTests(unittest.TestCase):
    def test_missing_email_credentials_are_explicit(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "SMTP_USER, SMTP_APP_PASSWORD, ALERT_EMAIL"):
                m.smtp_settings()

    def test_monitor_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(sys, "argv", ["monitor.py", "--mode", "monitor"]):
            with self.assertRaisesRegex(RuntimeError, "Monitoring disabled"):
                m.main()

    def test_three_asins_and_workflow_configuration(self):
        self.assertEqual(set(m.PRODUCTS), {"B07K6RYVHR", "B093QF35KZ", "B0C1H473H8"})
        path = Path(__file__).resolve().parents[1] / ".github/workflows/monitor.yml"
        # BaseLoader avoids YAML 1.1 treating the Actions key 'on' as a boolean.
        workflow = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
        self.assertEqual(workflow["on"]["schedule"][0]["cron"], "*/5 * * * *")
        self.assertEqual(workflow["on"]["workflow_dispatch"]["inputs"]["mode"]["options"], ["diagnose", "test", "monitor"])
        self.assertEqual(workflow["concurrency"], {"group": "psn-stock-monitor", "cancel-in-progress": "false"})
        self.assertIn("vars.BOT_ENABLED == 'true'", workflow["jobs"]["validate"]["if"])
        self.assertEqual(workflow["jobs"]["watch"]["needs"], "validate")
        artifact = workflow["jobs"]["watch"]["steps"][-1]
        self.assertIn("always()", artifact["if"])


@patch.dict(os.environ, {"SMTP_USER": "sender@example.com", "ALERT_EMAIL": "recipient@example.com",
                        "SMTP_APP_PASSWORD": "abcd efgh ijkl mnop"}, clear=True)
class GmailTests(unittest.TestCase):
    def setUp(self):
        context = patch.object(m.ssl, "create_default_context", return_value=object())
        context.start()
        self.addCleanup(context.stop)

    def client(self):
        client = Mock()
        client.ehlo.return_value = (250, b"safe greeting")
        client.send_message.return_value = {}
        return client

    def test_password_spaces_are_normalized(self):
        self.assertEqual(m.smtp_settings()["SMTP_APP_PASSWORD"], "abcdefghijklmnop")

    def test_invalid_settings_fail_without_disclosing_values(self):
        for field, value in (("SMTP_USER", "private bad address"), ("SMTP_APP_PASSWORD", "private-wrong-password")):
            with patch.dict(os.environ, {field: value}):
                with self.assertRaises(RuntimeError) as raised:
                    m.smtp_settings()
                self.assertIn(field, str(raised.exception))
                self.assertNotIn(value, str(raised.exception))

    def test_tls_delivery_is_accepted_once(self):
        client = self.client()
        with patch.object(m.smtplib, "SMTP_SSL", return_value=client), patch.object(m.smtplib, "SMTP") as fallback:
            m.send_gmail("Test", "Body")
        client.login.assert_called_once_with("sender@example.com", "abcdefghijklmnop")
        client.send_message.assert_called_once()
        client.close.assert_called_once()
        fallback.assert_not_called()

    def test_connection_failure_can_use_starttls_before_submission(self):
        client = self.client()
        with patch.object(m.smtplib, "SMTP_SSL", side_effect=m.smtplib.SMTPServerDisconnected()), \
                patch.object(m.smtplib, "SMTP", return_value=client):
            m.send_gmail("Test", "Body")
        self.assertEqual(client.ehlo.call_count, 2)
        client.starttls.assert_called_once()
        self.assertLess([c[0] for c in client.method_calls].index("starttls"),
                        [c[0] for c in client.method_calls].index("login"))
        client.send_message.assert_called_once()

    def test_authentication_failure_is_safe_and_not_retried(self):
        client = self.client()
        client.login.side_effect = m.smtplib.SMTPAuthenticationError(535, b"private account details")
        with patch.object(m.smtplib, "SMTP_SSL", return_value=client), patch.object(m.smtplib, "SMTP") as fallback:
            with self.assertRaisesRegex(RuntimeError, "authenticate.*code 535") as raised:
                m.send_gmail("Test", "Body")
        self.assertNotIn("private account details", str(raised.exception))
        fallback.assert_not_called()
        client.send_message.assert_not_called()

    def test_ambiguous_delivery_never_uses_another_transport(self):
        client = self.client()
        client.send_message.side_effect = m.smtplib.SMTPServerDisconnected("private reply")
        with patch.object(m.smtplib, "SMTP_SSL", return_value=client), patch.object(m.smtplib, "SMTP") as fallback:
            with self.assertRaisesRegex(RuntimeError, "SMTP send failed"):
                m.send_gmail("Test", "Body")
        client.send_message.assert_called_once()
        fallback.assert_not_called()
