"""Real browser checks against a temporary instance; no provider calls."""

import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
base = f"http://127.0.0.1:{port}"
root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as directory:
    env = os.environ | {
        "SERVICEPILOT_ENVIRONMENT": "demo",
        "SERVICEPILOT_PROVIDER": "offline",
        "SERVICEPILOT_EMBEDDING_BACKEND": "hashing",
        "SERVICEPILOT_DATA_DIR": directory,
    }
    process = subprocess.Popen(
        [sys.executable, "-m", "servicepilot", "demo", "--port", str(port)], env=env
    )
    try:
        for _attempt in range(100):
            try:
                urllib.request.urlopen(base + "/health", timeout=1).close()
                break
            except (OSError, urllib.error.URLError):
                time.sleep(0.1)
        else:
            raise RuntimeError("Demo server failed to start")
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                executable_path=os.environ.get("SERVICEPILOT_BROWSER_EXECUTABLE") or None
            )
            page = browser.new_page(viewport={"width": 1440, "height": 1080})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(base)
            expect(page.locator("#scope")).to_contain_text("ATLAS")
            page.locator("#query").fill("Problème de connexion Atlas")
            page.locator("#submit").click()
            expect(page.locator("#summary")).to_contain_text("degraded")
            expect(page.locator("#trace li")).to_have_count(3)
            page.locator("#query").fill("Crée un ticket pour mon problème de connexion Atlas")
            page.locator("#submit").click()
            expect(page.locator("#approval")).to_be_visible()
            reports = root / "reports"
            reports.mkdir(exist_ok=True)
            page.screenshot(path=str(reports / "desktop.png"), full_page=True)
            page.locator("#approve").click()
            expect(page.locator("#ticket-result")).to_contain_text("SP-")
            page.locator("#identity").select_option("demo-bob-token")
            expect(page.locator("#scope")).to_contain_text("ORION")
            expect(page.locator("#history button")).to_have_count(0)
            page.set_viewport_size({"width": 390, "height": 844})
            page.locator("#query").fill("Quelle procédure pour réinitialiser mon VPN ?")
            page.locator("#submit").click()
            expect(page.locator("#summary")).to_contain_text("VPN")
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            page.screenshot(path=str(reports / "mobile.png"), full_page=True)
            assert not errors, errors
            browser.close()
        print("Browser smoke: diagnostic, approval, identity isolation and mobile layout passed")
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
