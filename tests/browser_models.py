"""Deterministic UI checks with clearly labeled fixture model outputs; consumes no inference quota."""
from playwright.sync_api import expect


def check_models(page, artifacts):
    fixture_models = [
        {"id": "qwen/qwen3.8-27b:free", "name": "Qwen3.8 27B", "kind": "llm", "verified_free": True, "note": "UI test fixture"},
        {"id": "nvidia/nemotron-3.5-lightning:free", "name": "Nemotron 3.5 Lightning", "kind": "llm", "verified_free": True, "note": "UI test fixture"},
        {"id": "google/gemma-4-26b-a4b-it:free", "name": "Gemma 4 26B A4B", "kind": "llm", "verified_free": True, "note": "UI test fixture"},
        {"id": "typesafe/jev-1.13", "name": "TypeSafe Jev 1.13", "kind": "decision", "verified_free": False, "note": "Paid option"},
    ]
    records = []
    calls = []
    current_key = ["fixture-initial"]

    def catalog(route):
        route.fulfill(json={"configured": True, "models": fixture_models, "limits_note": "Fixture quota",
                            "unavailable_families": [{"name": "OpenAI", "message": "No verified free endpoint"},
                                                     {"name": "Google Gemini", "message": "No verified free endpoint"}]})

    def status(route):
        route.fulfill(json={"configured": True, "error": None, "quota": {"remaining": 50, "limit": 50}})

    def comparison(route):
        if route.request.method == "GET":
            route.fulfill(json={"state_key": current_key[0], "records": records})
            return
        body = route.request.post_data_json
        calls.append(body)
        record = {"id": f"fixture-{len(calls)}", "model_id": body["model_id"], "framework_id": body["framework_id"],
                  "state_key": current_key[0], "step": body["evidence_step"], "created_at": "2026-09-27T12:00:00Z",
                  "prompt_version": "UI-FIXTURE", "input": {"observed": {}, "fixture": True}}
        if body["model_id"].startswith("nvidia") and not body["repeat"]:
            record.update(status="error", error={"code": "http_429", "message": "Fixture: provider at capacity.", "retry_after": 30})
        else:
            record.update(status="ok", result={
                "answer": {"decision": "conditional", "next_question": "relay_a",
                           "explanation": "UI fixture: <img src=x onerror=alert(1)> should remain plain text."},
                "duration_ms": 1234, "usage": {"prompt_tokens": 500, "completion_tokens": 90, "cost": 0},
                "requested_model": body["model_id"], "returned_model": body["model_id"], "provider": "TEST FIXTURE"},
                assessment={"decision_matches": True, "verdict": "Matches reference decision",
                            "question_valid": True, "reference_next_question": "relay_a"})
        records.append(record)
        route.fulfill(json={"record": record, "reused": False})

    page.route("**/api/models*", catalog)
    page.route("**/api/openrouter/status*", status)
    page.route("**/api/runs/*/comparisons", comparison)
    page.set_viewport_size({"width": 1440, "height": 1000})
    page.locator("#replay-exit").click()
    page.locator('[data-scenario="relays"]').click()
    page.locator("#models-tab").click()
    expect(page.locator("#models-panel")).to_be_visible()
    page.locator("#model-refresh").click()
    expect(page.locator("#model-options input")).to_have_count(4)
    page.locator('#model-options input').first.check()
    page.locator('#model-options input').nth(1).check()
    page.locator('#model-options input').nth(2).uncheck()
    expect(page.locator('#model-options input[value="typesafe/jev-1.13"]')).not_to_be_checked()
    expect(page.locator("#model-call-count")).to_contain_text("2 selected models")
    page.locator("#model-run").click()
    expect(page.locator("#model-results .model-result")).to_have_count(2)
    expect(page.locator("#model-results .model-failed")).to_have_count(1)
    expect(page.locator("#model-results img")).to_have_count(0)
    expect(page.locator("#model-results")).to_contain_text("<img src=x")
    assert len(calls) == 2
    assert all(not call["allow_paid_jev"] for call in calls)
    page.locator("#model-repeat").check()
    page.locator("#model-run").click()
    expect(page.locator("#model-results .model-failed")).to_have_count(0)
    expect(page.locator("#model-history-count")).to_have_text("2")
    assert len(calls) == 4
    page.screenshot(path=str(artifacts / "model-ui-fixtures-desktop.png"), full_page=True)
    page.locator("#model-framework").select_option("duty")
    expect(page.locator("#model-results .model-result")).to_have_count(0)
    page.locator("#model-framework").select_option("utility")
    expect(page.locator("#model-results .model-result")).to_have_count(2)

    # New evidence invalidates the visible comparison; replay cannot reveal future outputs.
    current_key[0] = "fixture-after-disclosure"
    page.locator("#investigation-tab").click()
    page.locator('#fact-cards [data-fact="relay_a"]').click()
    page.locator("#models-tab").click()
    expect(page.locator("#model-results .model-result")).to_have_count(0)
    page.locator("#investigation-tab").click()
    page.locator("#replay-start").click()
    page.locator("#models-tab").click()
    expect(page.locator("#model-run")).to_be_disabled()
    expect(page.locator("#model-results")).to_contain_text("Return to the live run")
    expect(page.locator("#model-history")).not_to_be_visible()
    page.locator("#investigation-tab").click()
    page.locator("#replay-exit").click()
    page.locator("#models-tab").click()
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Model comparison overflows mobile viewport"
    page.screenshot(path=str(artifacts / "model-ui-fixtures-mobile.png"), full_page=True)
    page.unroute("**/api/models*", catalog)
    page.unroute("**/api/openrouter/status*", status)
    page.unroute("**/api/runs/*/comparisons", comparison)
    page.reload()
    expect(page.locator("#scenario-title")).to_have_text("Two halves of an answer")
    print("Model UI fixtures passed: selection, failures, repeats, provenance, escaped output, stale evidence, replay isolation and mobile layout.", flush=True)
