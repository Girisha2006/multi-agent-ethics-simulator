"""End-to-end browser check against a running local server; saves QA screenshots."""
import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright, expect
from browser_models import check_models

ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS = ROOT / "artifacts"
ARTIFACTS.mkdir(exist_ok=True)
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--headed", action="store_true", help="Show the browser while running the checks.")
parser.add_argument("--keep-open", action="store_true", help="Leave the headed browser open after the checks until its window is closed.")
args = parser.parse_args()
if args.keep_open and not args.headed:
    parser.error("--keep-open requires --headed")

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=not args.headed, slow_mo=250 if args.headed else 0, **({} if Path(playwright.chromium.executable_path).exists() else {"channel": "msedge"}))
    page = browser.new_page(viewport={"width": 1440, "height": 1100}, device_scale_factor=1)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto("http://127.0.0.1:8000")
    expect(page.locator("#scenario-title")).to_have_text("The uncertain junction")
    expect(page.locator(".agent-card")).to_have_count(3)
    expect(page.locator("#budget-used")).to_have_text("0")
    page.screenshot(path=str(ARTIFACTS / "dashboard-desktop.png"), full_page=True)

    # An agent's actual suggested question reveals one shared fact.
    page.locator("#agent-cards button[data-fact]").first.click()
    expect(page.locator("#budget-used")).to_have_text("1")
    expect(page.locator("#fact-cards .revealed")).to_have_count(1)
    page.locator("#fact-cards button:not(:disabled)").first.click()
    expect(page.locator("#budget-used")).to_have_text("2")
    expect(page.locator("#fact-cards button:not(:disabled)")).to_have_count(0)
    page.locator("#world-details summary").click()
    expect(page.locator("#world-table tbody tr")).to_have_count(2)

    # Refresh restores the run and its spent budget.
    page.reload()
    expect(page.locator("#budget-used")).to_have_text("2")
    page.locator("#finish-button").click()
    expect(page.locator("#debrief")).to_be_visible()
    expect(page.locator("#finish-button")).to_be_disabled()
    expect(page.locator("#budget-used")).to_have_text("2")
    page.screenshot(path=str(ARTIFACTS / "dashboard-debrief.png"), full_page=True)
    with page.expect_download() as download_info:
        page.locator("#export-button").click()
    download = download_info.value
    download.save_as(str(ARTIFACTS / "sample-run.md"))
    assert "Full-information debrief" in (ARTIFACTS / "sample-run.md").read_text(encoding="utf-8")

    page.locator("#benchmark-tab").click()
    page.locator("#benchmark-run").click()
    expect(page.locator(".benchmark-card")).to_have_count(3)
    page.screenshot(path=str(ARTIFACTS / "dashboard-benchmark.png"), full_page=True)
    page.locator("#method-button").click()
    expect(page.locator("#method-dialog")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator("#method-dialog")).not_to_be_visible()

    # Three presentation areas have working demonstrations.
    expect(page.locator(".contribution-grid article")).to_have_count(3)
    page.locator('[data-demo="costly"]').click()
    expect(page.locator("#scenario-title")).to_have_text("The expensive report")
    expect(page.locator('#fact-cards [data-fact="reliability"]')).to_contain_text("2 credits")
    page.locator('#fact-cards [data-fact="reliability"]').click()
    expect(page.locator("#budget-used")).to_have_text("2")
    expect(page.locator("#fact-cards .revealed")).to_have_count(1)
    expect(page.locator("#fact-cards button:not(:disabled)")).to_have_count(0)

    page.locator('[data-demo="relays"]').click()
    expect(page.locator("#scenario-title")).to_have_text("Two halves of an answer")
    expect(page.locator('.agent-card.utility [data-fact="relay_a"]')).to_be_visible()
    page.locator("#strategy-greedy").click()
    expect(page.locator(".agent-card.utility .agent-question")).to_contain_text("Strategy stops here")
    expect(page.locator(".agent-card.utility button[data-fact]")).to_have_count(0)
    page.locator("#strategy-optimal").click()
    page.locator(".agent-card.utility .plan-branches summary").click()
    expect(page.locator(".agent-card.utility .plan-branches")).to_contain_text("Relay B setting")
    page.locator('#fact-cards [data-fact="relay_a"]').click()
    expect(page.locator(".world-tile.possible")).to_have_count(4)
    expect(page.locator(".agent-card.utility .status-pill")).to_have_text("Conditional")
    page.locator('#fact-cards [data-fact="relay_b"]').click()
    expect(page.locator(".world-tile.possible")).to_have_count(2)
    expect(page.locator(".agent-card.utility .status-pill")).to_have_text("Resolved")
    page.screenshot(path=str(ARTIFACTS / "dashboard-relays.png"), full_page=True)

    # Replay is read-only and restores the actual live state when exited.
    current_id = page.evaluate("localStorage.getItem('byd-run')")
    saved = page.request.get(f"http://127.0.0.1:8000/api/runs/{current_id}").json()
    page.locator("#replay-start").click()
    expect(page.locator("#replay-status")).to_contain_text("step 0 of 2")
    expect(page.locator(".world-tile.possible")).to_have_count(8)
    expect(page.locator("#budget-used")).to_have_text("0")
    expect(page.locator("#fact-cards button:not(:disabled)")).to_have_count(0)
    expect(page.locator("#finish-button")).to_be_disabled()
    expect(page.locator("#reset-button")).to_be_disabled()
    page.locator("#replay-next").click()
    expect(page.locator(".world-tile.possible")).to_have_count(4)
    page.screenshot(path=str(ARTIFACTS / "dashboard-replay.png"), full_page=True)
    page.locator("#replay-prev").click()
    page.locator("#replay-play").click()
    expect(page.locator("#replay-play")).to_have_text("Pause")
    page.locator("#replay-play").click()
    expect(page.locator("#replay-play")).to_have_text("Play")
    page.locator("#replay-play").click()
    expect(page.locator("#replay-status")).to_contain_text("step 2 of 2", timeout=10000)
    expect(page.locator("#replay-play")).to_have_text("Play")
    page.locator("#replay-position").focus()
    page.keyboard.press("Home")
    expect(page.locator("#replay-status")).to_contain_text("step 0 of 2")
    assert page.request.get(f"http://127.0.0.1:8000/api/runs/{current_id}").json() == saved
    page.locator("#replay-exit").click()
    expect(page.locator("#budget-used")).to_have_text("2")
    expect(page.locator("#finish-button")).to_be_enabled()
    page.locator("#finish-button").click()
    page.locator("#replay-start").click()
    expect(page.locator("#debrief")).not_to_be_visible()
    page.locator("#replay-position").focus()
    page.keyboard.press("End")
    expect(page.locator("#debrief")).to_be_visible()
    page.locator("#replay-exit").click()

    page.locator('[data-scenario="settled"]').click()
    expect(page.locator(".agent-card .status-pill.resolved")).to_have_count(3)
    expect(page.locator("#agent-cards button[data-fact]")).to_have_count(0)
    expect(page.locator("#budget-used")).to_have_text("0")
    page.locator("#benchmark-tab").click()
    expect(page.locator('#case-results [data-case="relays"]')).to_have_count(3)
    expect(page.locator('#case-results [data-case="relays"]').first).to_contain_text("100.0%")

    page.locator('[data-scenario="bridge"]').click()
    expect(page.locator("#scenario-title")).to_have_text("The bridge crossing")
    expect(page.locator("#budget-used")).to_have_text("0")
    page.set_viewport_size({"width": 390, "height": 844})
    page.screenshot(path=str(ARTIFACTS / "dashboard-mobile.png"), full_page=True)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Mobile horizontal overflow"
    page.locator("#fact-cards button:not(:disabled)").first.click()
    expect(page.locator("#budget-used")).to_have_text("1")
    page.emulate_media(reduced_motion="reduce")
    page.locator('[data-scenario="relays"]').click()
    page.locator('#fact-cards [data-fact="relay_a"]').click()
    page.locator("#replay-start").click()
    page.locator("#replay-next").click()
    assert page.locator(".just-eliminated").first.evaluate("el => getComputedStyle(el).animationName") == "none"
    page.locator("#world-details summary").click()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Mobile replay overflow"
    page.screenshot(path=str(ARTIFACTS / "dashboard-replay-mobile.png"), full_page=True)
    check_models(page, ARTIFACTS)
    assert not errors, errors
    print("Browser smoke passed: baseline flows, novelty demos, costly evidence, relay planning, stopping, replay, autoplay, export, comparison, mobile and reduced motion.", flush=True)
    if args.keep_open:
        page.set_viewport_size({"width": 1440, "height": 1000})
        page.locator('[data-scenario="junction"]').click()
        expect(page.locator("#budget-used")).to_have_text("0")
        page.keyboard.press("Control+Home")
        print("Headed browser ready. A fresh investigation is open; close the browser window when finished.", flush=True)
        try:
            page.wait_for_event("close", timeout=0)
        except Exception:
            if browser.is_connected():
                raise
    if browser.is_connected():
        browser.close()
