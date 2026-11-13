name: PSN Amazon Stock Monitor

on:
  workflow_dispatch:
    inputs:
      mode:
        description: "Once diagnose, sonra test (email), monitor normal calisma"
        required: true
        default: diagnose
        type: choice
        options:
          - diagnose
          - test
          - monitor
  schedule:
    - cron: '7,17,27,37,47,57 * * * *'

permissions:
  contents: read
  issues: write

concurrency:
  group: psn-stock-monitor
  cancel-in-progress: false

jobs:
  watch:
    if: ${{ github.event_name != 'schedule' || vars.BOT_ENABLED == 'true' }}
    runs-on: ubuntu-latest
    timeout-minutes: 8
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Python dependencies
        run: python -m pip install -r requirements.txt
      - name: Chromium installation
        run: python -m playwright install --with-deps chromium
      - name: Check Amazon and send alerts
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          SMTP_USER: ${{ secrets.SMTP_USER }}
          SMTP_APP_PASSWORD: ${{ secrets.SMTP_APP_PASSWORD }}
          ALERT_EMAIL: ${{ secrets.ALERT_EMAIL }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
          CHECK_MODE: ${{ github.event_name == 'schedule' && 'monitor' || inputs.mode }}
        run: python monitor.py --mode "${CHECK_MODE:-diagnose}"

      - name: Amazon screenshots (diagnose only)
        if: ${{ github.event_name == 'workflow_dispatch' && inputs.mode == 'diagnose' }}
        run: |
          mkdir -p debug
          python - <<'PY'
          from pathlib import Path
          from playwright.sync_api import sync_playwright

          asins = ["B07K6RYVHR", "B093QF35KZ", "B0C1H473H8"]
          with sync_playwright() as playwright:
              browser = playwright.chromium.launch(headless=True)
              try:
                  for asin in asins:
                      page = browser.new_page(locale="en-IN", timezone_id="Asia/Kolkata", viewport={"width": 1440, "height": 900})
                      try:
                          response = page.goto(f"https://www.amazon.in/dp/{asin}", wait_until="domcontentloaded", timeout=35000)
                          page.wait_for_timeout(1500)
                          page.screenshot(path=f"debug/{asin}.png", full_page=False)
                          info = f"ASIN: {asin}\nHTTP: {response.status if response else 'no response'}\nURL: {page.url}\nTitle: {page.title()}\n"
                          Path(f"debug/{asin}.txt").write_text(info, encoding="utf-8")
                          print(info)
                      except Exception as exc:
                          Path(f"debug/{asin}.txt").write_text(str(exc), encoding="utf-8")
                          print(asin, type(exc).__name__, str(exc)[:200])
                      finally:
                          page.close()
              finally:
                  browser.close()
          PY

      - name: Upload screenshots
        if: ${{ always() && github.event_name == 'workflow_dispatch' && inputs.mode == 'diagnose' }}
        uses: actions/upload-artifact@v4
        with:
          name: amazon-debug-screenshots
          path: debug/
          if-no-files-found: warn
          retention-days: 1
