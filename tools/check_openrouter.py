"""Small explicit live probe. Never prints credentials and never calls paid models."""
from pathlib import Path
import json
import sys
import argparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ethics_lab import comparisons, openrouter, store
from ethics_lab.scenarios import VERSION, get_scenario, fact_ids
from uuid import uuid4

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--models", nargs="+")
parser.add_argument("--case", default="relays")
args = parser.parse_args()

scenario = get_scenario(args.case)
assert scenario, "Unknown case"
run = {"id": str(uuid4()), "version": VERSION, "scenario_id": scenario["id"], "scenario": scenario,
       "created_at": openrouter.now(), "observed": {}, "actual": {key: False for key in fact_ids(scenario)},
       "events": [], "finished": False}
store.save_new(run)
print("Live probe run:", run["id"], flush=True)
selected = [m for m in openrouter.MODELS if args.models and m["id"] in args.models] if args.models else openrouter.MODELS[:3]
assert all(m["kind"] == "llm" and m["id"].endswith(":free") for m in selected), "This probe only permits free LLMs."
for model in selected:
    result = comparisons.execute(run, model["id"], "utility")["record"]
    if result["status"] == "ok":
        output = result["result"]
        print(json.dumps({"model": model["id"], "status": "ok", "answer": output["answer"],
                          "duration_ms": output["duration_ms"], "usage": output["usage"],
                          "assessment": result["assessment"]}), flush=True)
    else:
        detail = result.get("failure_details", {})
        print(json.dumps({"model": model["id"], "status": result["status"], "error": result.get("error"),
                          "finish_reason": detail.get("finish_reason"), "usage": detail.get("usage"),
                          "output_characters": len(detail.get("raw_output") or "")}), flush=True)
print(json.dumps(openrouter.connection_status(True)), flush=True)
