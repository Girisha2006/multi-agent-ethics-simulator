"""Persist independent model attempts separately from the reference disclosure journal."""
import hashlib
import json
import time
from uuid import uuid4

from . import openrouter, store


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def state_key(run):
    return digest({"version": run["version"], "scenario": run["scenario"], "observed": run["observed"], "finished": run["finished"]})


def ensure_table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS model_attempts (
        id TEXT PRIMARY KEY, run_id TEXT NOT NULL, cache_key TEXT NOT NULL,
        started REAL NOT NULL, body TEXT NOT NULL)""")
    db.execute("CREATE INDEX IF NOT EXISTS attempts_by_run ON model_attempts(run_id, started)")
    db.execute("CREATE INDEX IF NOT EXISTS attempts_by_cache ON model_attempts(cache_key, started)")


def history(run_id):
    with store.connect() as db:
        ensure_table(db)
        rows = db.execute("SELECT started, body FROM model_attempts WHERE run_id = ? ORDER BY started", (run_id,)).fetchall()
        records = []
        for started, body in rows:
            record = json.loads(body)
            if record["status"] == "running" and time.time() - started > 120:
                record.update(status="error", error={"code": "interrupted", "message": "This attempt was interrupted before its result was saved.", "retry_after": None})
                db.execute("UPDATE model_attempts SET body = ? WHERE id = ?", (json.dumps(record), record["id"]))
            records.append(record)
    return records


def start_attempt(run, model_id, framework_id, repeat=False):
    context = openrouter.evidence_input(run, framework_id)
    key = digest({"run_id": run["id"], "context": context, "model": model_id, "prompt_version": openrouter.PROMPT_VERSION,
                  "state_key": state_key(run)})
    with store.connect() as db:
        ensure_table(db)
        db.execute("BEGIN IMMEDIATE")
        previous = db.execute("SELECT started, body FROM model_attempts WHERE cache_key = ? ORDER BY started DESC LIMIT 1", (key,)).fetchone()
        if previous:
            last = json.loads(previous[1])
            if last["status"] == "running" and time.time() - previous[0] > 120:
                last.update(status="error", error={"code": "interrupted", "message": "This attempt was interrupted before its result was saved.", "retry_after": None})
                db.execute("UPDATE model_attempts SET body = ? WHERE id = ?", (json.dumps(last), last["id"]))
            if not repeat or last["status"] == "running":
                return last, True
        record = {"id": str(uuid4()), "run_id": run["id"], "state_key": state_key(run), "model_id": model_id,
                  "framework_id": framework_id, "prompt_version": openrouter.PROMPT_VERSION, "engine_version": run["version"],
                  "created_at": openrouter.now(), "step": len(run["events"]), "observed": dict(run["observed"]),
                  "round_finished": run["finished"], "input": context, "status": "running"}
        db.execute("INSERT INTO model_attempts VALUES (?, ?, ?, ?, ?)", (record["id"], run["id"], key, time.time(), json.dumps(record)))
    return record, False


def execute(run, model_id, framework_id, repeat=False, allow_paid_jev=False):
    record, reused = start_attempt(run, model_id, framework_id, repeat)
    if reused:
        return {"record": record, "reused": True}
    started = time.perf_counter()
    try:
        result = openrouter.invoke(model_id, record["input"], allow_paid_jev)
        record.update(status="ok", result=result, assessment=openrouter.assess(run, framework_id, result["answer"]))
    except openrouter.ProviderFailure as exc:
        record.update(status="error", error=exc.public(), duration_ms=round((time.perf_counter() - started) * 1000))
        if exc.details:
            record["failure_details"] = exc.details
    record["completed_at"] = openrouter.now()
    with store.connect() as db:
        ensure_table(db)
        db.execute("UPDATE model_attempts SET body = ? WHERE id = ?", (json.dumps(record), record["id"]))
    return {"record": record, "reused": False}


def markdown(run, records):
    lines = ["# Before You Decide - independent model comparisons", "",
             f"- Run: {run['id']}", f"- Case: {run['scenario']['title']}",
             "- Models receive the same physical rules and disclosed facts, without reference answers or the hidden world.",
             "- Reference adherence is not moral correctness. Reused results are not independent repetitions.",
             "- Jev returns typed decisions; it does not generate explanations.", ""]
    for record in records:
        lines.extend([f"## {record['model_id']} / {record['framework_id']}", "",
                      f"- Attempt: {record['id']}", f"- Created: {record['created_at']}",
                      f"- Evidence step: {record['step']}; observed: {json.dumps(record['observed'])}",
                      f"- Prompt: {record['prompt_version']}; engine: {record['engine_version']}",
                      f"- Status: {record['status']}"])
        if record["status"] == "ok":
            result, assessment = record["result"], record["assessment"]
            lines.extend([f"- Returned model: {result['returned_model']}; provider: {result['provider']}",
                          f"- Response time: {result['duration_ms']} ms",
                          f"- Usage: {json.dumps(result['usage'])}",
                          f"- Decision: {result['answer']['decision']}",
                          f"- Next question: {result['answer']['next_question'] or 'Stop'}",
                          f"- Reference check: {assessment['verdict']}", "",
                          result["answer"]["explanation"] or "No generated explanation (decision-only model).", ""])
        elif record["status"] == "error":
            lines.extend([f"- Failure: {record['error']['code']} - {record['error']['message']}", ""])
    return "\n".join(lines)
