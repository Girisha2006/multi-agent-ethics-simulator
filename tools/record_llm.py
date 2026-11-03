"""Record real language-model runs for offline replay. Needs OPENROUTER_API_KEY; stops when the daily quota is used up.

Usage: python tools/record_llm.py [dilemma_id ...]   (default: the 8 base dilemmas)
"""
from pathlib import Path
import json
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ethics_lab import openrouter
from ethics_lab.decision import dilemmas, llm


def main(ids):
    if not openrouter.api_key():
        sys.exit("OPENROUTER_API_KEY is not set; recordings must come from real live runs.")
    path = llm.recordings_path()
    saved = llm.recordings()
    have = {r.get("cache_key") for r in saved}
    added, skipped, failed, requests = 0, 0, 0, 0
    for dilemma_id in ids or [b["id"] for b in dilemmas.BASES]:
        d = dilemmas.get(dilemma_id)
        if not d:
            print(f"{dilemma_id}: unknown dilemma")
            failed += 1
            continue
        key = llm.cache_key(d)
        if key in have:
            print(f"{dilemma_id}: already recorded, skipped")
            skipped += 1
            continue
        result = llm.run(dilemma_id, repeat=True)
        requests += result["requests_used"]
        if (result["error"] or {}).get("code") == "minute_limit":
            wait = min(result["error"]["retry_after"] or 60, 60)
            print(f"{dilemma_id}: minute limit, waiting {wait}s once")
            time.sleep(wait)
            result = llm.run(dilemma_id, repeat=True)
            requests += result["requests_used"]
        if result["status"] == "ok" and result["source"] == "live":
            saved.append({**result, "cache_key": key})
            have.add(key)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(saved, indent=2), encoding="utf-8")
            added += 1
            print(f"{dilemma_id}: recorded from {result['model_id']}")
            continue
        failed += 1
        code = (result["error"] or {}).get("code", result["source"])
        print(f"{dilemma_id}: not recorded ({code})")
        if code in ("quota_exhausted", "minute_limit", "missing_key"):
            print("Stopping: quota or key unavailable.")
            break
    print(f"Summary: {added} recorded, {skipped} skipped, {failed} failed, {requests} requests; file {path}")


if __name__ == "__main__":
    main(sys.argv[1:])
