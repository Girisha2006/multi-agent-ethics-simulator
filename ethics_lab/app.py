from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from copy import deepcopy
from uuid import uuid4
import secrets

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from . import engine, store, comparisons, openrouter
from .decision import api as decision_api, llm_api as decision_llm_api
from .scenarios import ACTIONS, FACTS, FRAMEWORKS, SCENARIOS, VERSION, fact_cards, fact_value, get_scenario, fact_ids, facts_for, spent_credits

app = FastAPI(title="Before You Decide", version=VERSION)
STATIC = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=STATIC), name="static")
app.include_router(decision_api.router)
app.include_router(decision_llm_api.router)


class NewRun(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario_id: str


class Reveal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fact_id: str = Field(min_length=1, max_length=40)


class ModelComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model_id: str = Field(min_length=1, max_length=150)
    framework_id: Literal["utility", "duty", "fairness"]
    evidence_step: int = Field(ge=0, le=4)
    repeat: bool = False
    allow_paid_jev: bool = False


def now():
    return datetime.now(timezone.utc).isoformat()


def load_run(run_id):
    run = store.get(run_id)
    if not run:
        raise HTTPException(404, "This run was not found. Start a new investigation.")
    return run


def public_run(run):
    if run["version"] != VERSION:
        raise HTTPException(409, "This run uses a different rule version. Its journal is preserved; start a new run with the current engine.")
    scenario = run.get("scenario", get_scenario(run["scenario_id"]))
    observed = run["observed"]
    remaining = 0 if run["finished"] else 2 - spent_credits(scenario, observed)
    response = {"id": run["id"], "created_at": run["created_at"], "version": run["version"], "mode": "reference",
                "scenario": scenario, "observed": observed, "finished": run["finished"], "remaining": remaining,
                "spent": spent_credits(scenario, observed), "budget": 2, "facts": fact_cards(scenario, observed), "events": run["events"],
                "agents": engine.agents(scenario, observed, remaining), "analysis": engine.analyze(scenario, observed)}
    if run["finished"]:
        response["debrief"] = {"facts": fact_cards(scenario, run["actual"]),
                               "agents": engine.agents(scenario, run["actual"], 0),
                               "analysis": engine.analyze(scenario, run["actual"])}
    return response


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/decision")
def decision_page():
    return FileResponse(STATIC / "decision.html")


@app.get("/api/catalog")
def catalog():
    return {"scenarios": SCENARIOS, "frameworks": FRAMEWORKS, "actions": ACTIONS, "version": VERSION}


@app.post("/api/runs", status_code=201)
def create_run(body: NewRun):
    if not get_scenario(body.scenario_id):
        raise HTTPException(404, "Unknown scenario.")
    run = {"id": str(uuid4()), "scenario_id": body.scenario_id, "scenario": get_scenario(body.scenario_id), "created_at": now(), "version": VERSION,
           "actual": {key: bool(secrets.randbits(1)) for key in fact_ids(get_scenario(body.scenario_id))}, "observed": {}, "events": [], "finished": False}
    store.save_new(run)
    return public_run(run)


@app.get("/api/runs/{run_id}")
def read_run(run_id: str):
    return public_run(load_run(run_id))


@app.post("/api/runs/{run_id}/reveal")
def reveal(run_id: str, body: Reveal):
    def operation(run):
        if run["version"] != VERSION:
            raise HTTPException(409, "This run belongs to a different rule version. Start a new run.")
        scenario = run.get("scenario", get_scenario(run["scenario_id"]))
        fact = next((f for f in facts_for(scenario) if f["id"] == body.fact_id), None)
        if not fact:
            raise HTTPException(422, "This fact does not belong to this case.")
        remaining = 2 - spent_credits(scenario, run["observed"])
        if run["finished"] or fact["cost"] > remaining:
            raise HTTPException(409, "This fact exceeds the remaining credits, or the round is closed.")
        if body.fact_id in run["observed"]:
            raise HTTPException(409, "This fact has already been revealed.")
        agents_before = engine.agents(scenario, run["observed"], remaining)
        suggestions = {agent["id"]: agent["next_question"] for agent in agents_before}
        plans = {agent["id"]: agent["optimal_plan"] for agent in agents_before}
        value = run["actual"][body.fact_id]
        run["observed"][body.fact_id] = value
        run["events"].append({"type": "reveal", "at": now(), "fact_id": body.fact_id, "value": value,
                              "cost": fact["cost"], "recommendations_before": suggestions, "optimal_recommendations_before": plans,
                              "actions_after": {a["id"]: a["robust_actions"] for a in engine.agents(scenario, run["observed"], 0)}})
    run = store.update(run_id, operation)
    if not run:
        raise HTTPException(404, "Run not found.")
    return public_run(run)


@app.get("/api/runs/{run_id}/replay")
def replay(run_id: str):
    recorded = load_run(run_id)
    public_run(recorded)  # Enforce the same version guard as the live view.
    snapshot = deepcopy(recorded)
    snapshot.update(observed={}, events=[], finished=False)
    frames = [{"label": "Before any disclosure", "kind": "start", "state": deepcopy(public_run(snapshot))}]
    for event in recorded["events"]:
        snapshot["events"].append(deepcopy(event))
        if event["type"] == "reveal":
            snapshot["observed"][event["fact_id"]] = event["value"]
            label = fact_value(snapshot["scenario"], event["fact_id"], event["value"])
        else:
            snapshot["finished"] = True
            label = "Full-information debrief"
        frames.append({"label": label, "kind": event["type"], "fact_id": event.get("fact_id"),
                       "state": deepcopy(public_run(snapshot))})
    return {"run_id": run_id, "frames": frames}


@app.post("/api/runs/{run_id}/finish")
def finish(run_id: str):
    def operation(run):
        if run["version"] != VERSION:
            raise HTTPException(409, "This run belongs to a different rule version. Start a new run.")
        if not run["finished"]:
            run["finished"] = True
            run["events"].append({"type": "finish", "at": now()})
    run = store.update(run_id, operation)
    if not run:
        raise HTTPException(404, "Run not found.")
    return public_run(run)


@app.get("/api/benchmark")
def benchmark():
    return {"version": VERSION, **engine.benchmark(SCENARIOS)}


@app.get("/api/models")
def model_catalog(refresh: bool = False):
    return openrouter.model_catalog(refresh)


@app.get("/api/openrouter/status")
def model_connection(check_quota: bool = False):
    return openrouter.connection_status(check_quota)


@app.get("/api/runs/{run_id}/comparisons")
def model_history(run_id: str):
    run = load_run(run_id)
    public_run(run)
    return {"state_key": comparisons.state_key(run), "records": comparisons.history(run_id)}


@app.post("/api/runs/{run_id}/comparisons")
def compare_model(run_id: str, body: ModelComparison):
    run = load_run(run_id)
    public_run(run)
    if body.evidence_step != len(run["events"]):
        raise HTTPException(409, "The evidence changed. Refresh the comparison before running models.")
    configured = next((m for m in openrouter.MODELS if m["id"] == body.model_id), None)
    if not openrouter.allowed_model(body.model_id):
        raise HTTPException(422, "Select a configured comparison model.")
    if configured and configured["kind"] == "decision" and not body.allow_paid_jev:
        raise HTTPException(400, "Jev is paid. Select its explicitly labeled paid option before running.")
    return comparisons.execute(run, body.model_id, body.framework_id, body.repeat, body.allow_paid_jev)


@app.get("/api/runs/{run_id}/comparisons/export")
def export_comparisons(run_id: str, format: Literal["md", "json"] = "md"):
    run = load_run(run_id)
    public_run(run)
    records = comparisons.history(run_id)
    if format == "json":
        return {"run_id": run_id, "records": records}
    return PlainTextResponse(comparisons.markdown(run, records), media_type="text/markdown",
                             headers={"Content-Disposition": f'attachment; filename="model-comparisons-{run_id[:8]}.md"'})


@app.get("/api/runs/{run_id}/export")
def export_run(run_id: str, format: Literal["md", "json"] = "md"):
    run = load_run(run_id)
    view = public_run(run)
    if format == "json":
        return view
    scenario = view["scenario"]
    lines = ["# Before You Decide - experiment record", "", f"- Run: `{run['id']}`", f"- Created: {run['created_at']}",
             f"- Reference engine: {VERSION}", "- Prior: independent binary facts, eight equally weighted worlds.",
             "- Shared disclosure budget: 2 credits. Counterfactual counts are not calibrated confidence.",
             f"- Status: {'Debrief opened' if run['finished'] else 'Investigation'}", "",
             f"## {scenario['title']}", "", scenario["description"], "",
             f"Main group: {scenario['main']}; side group: {scenario['side']}; diversion side risk: {scenario['side_risk']:.0%}; brake risk per person: {scenario['brake_risk']:.0%}.",
             f"Possible rescue probabilities: {scenario['low']:.0%} and {scenario['high']:.0%}.",
             scenario.get("model_note", "The hidden causal-role and brake facts determine the duty constraint and brake availability."),
             f"Credits spent: {view['spent']}/2.",
             "", "## Disclosure timeline", ""]
    for event in run["events"]:
        if event["type"] == "reveal":
            lines.append(f"- {event['at']}: {event['fact_id']} - {fact_value(scenario, event['fact_id'], event['value'])} ({event['cost']} credits).")
            for framework in FRAMEWORKS:
                suggestion = event["recommendations_before"][framework["id"]]
                detail = f"{suggestion['fact_id']} ({suggestion['gain']:.3f} bits)" if suggestion else "No further informative question requested"
                lines.append(f"  - {framework['name']} greedy recommendation: {detail}.")
                plan = event["optimal_recommendations_before"][framework["id"]]
                lines.append(f"  - Budget planner: {plan['fact_id'] or 'Stop'}, {plan['resolved_probability']:.0%} chance of resolution, {plan['expected_cost']:.2f} expected credits.")
    if not run["observed"]:
        lines.append("No facts were disclosed during the investigation.")
    lines.extend(["", "## Decisions at the disclosure budget", ""])
    for agent in view["agents"]:
        lines.extend([f"### {agent['name']}", "", agent["rule"], "", agent["reason"], ""])
        lines.extend(f"- {ACTIONS[action]}: supported in {count}/{agent['world_count']} remaining worlds." for action, count in agent["support"].items() if count)
        lines.append("")
    lines.extend(["## Disagreement analysis", "", view["analysis"]["title"], "", view["analysis"]["description"], ""])
    if "debrief" in view:
        lines.extend(["## Full-information debrief (outside the question budget)", ""])
        lines.extend(f"- {fact['title']}: {fact['value']}" for fact in view["debrief"]["facts"])
        lines.append("")
        lines.extend(f"- {agent['name']}: {', '.join(ACTIONS[a] for a in agent['robust_actions'])}" for agent in view["debrief"]["agents"])
    lines.extend(["", "## Limits", "", "This is an authored reference-policy simulation, not an LLM experiment. The policies are simplified operational definitions, not complete philosophical theories. Disagreement is not a measure of moral error. Unrevealed actual values are excluded from unfinished-run exports.", ""])
    return PlainTextResponse("\n".join(lines), media_type="text/markdown", headers={"Content-Disposition": f'attachment; filename="before-you-decide-{run_id[:8]}.md"'})
