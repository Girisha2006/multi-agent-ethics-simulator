"""Read-only browser verification of a saved real model result; makes no inference calls."""
import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright, expect

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("run_id")
args = parser.parse_args()
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=False, **({} if Path(playwright.chromium.executable_path).exists() else {"channel": "msedge"}))
    page = browser.new_page(viewport={"width": 1440, "height": 1100})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto("http://127.0.0.1:8000")
    expect(page.locator("#scenario-title")).to_have_text("The uncertain junction")
    page.evaluate("(id) => localStorage.setItem('byd-run', id)", args.run_id)
    page.reload()
    expect(page.locator("#scenario-title")).to_have_text("Two halves of an answer")
    page.locator("#models-tab").click()
    expect(page.locator('#model-options input[value="nvidia/nemotron-3-super-120b-a12b:free"]')).to_be_checked(timeout=20000)
    expect(page.locator("#model-options input:checked")).to_have_count(1)
    expect(page.locator("#model-results")).to_contain_text("Hold yields 5 expected deaths.")
    expect(page.locator("#model-results")).to_contain_text("15.89 s total")
    expect(page.locator("#model-results")).to_contain_text("$0.000000")
    assert not errors, errors
    page.evaluate("window.scrollTo(0, 0)")
    page.screenshot(path="artifacts/model-live-result.png", full_page=True)
    print("Saved live result verified in the headed UI; default is Nemotron 3 Super only. No inference calls made.", flush=True)
    browser.close()
