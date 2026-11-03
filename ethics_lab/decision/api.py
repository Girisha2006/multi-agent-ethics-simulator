"""HTTP routes for the Decision Lab. Everything here is deterministic and needs no API key."""
from functools import lru_cache

from fastapi import APIRouter, HTTPException

from . import agents, dilemmas, evaluation, human

router = APIRouter(prefix="/api/decision", tags=["decision"])


def summary(d):
    return {"id": d["id"], "title": d["title"], "base": d["base"], "feature": d["feature"], "side": d.get("side"), "change": d["change"],
            "risk_framed": bool(d.get("risk_framed")) or any(d[s]["probability"] != 1 for s in ("stay", "swerve"))}


def view(d):
    outputs = agents.decide(d)
    lanes = {side: {**d[side], "text": dilemmas.describe_lane(d[side])} for side in ("stay", "swerve")}
    result = {**summary(d), "description": d["description"], "lanes": lanes, "outputs": [], "unanimous": None}
    base = dilemmas.get(d["base"]) if d["base"] else None
    base_outputs = {o["agent"]: o for o in agents.decide(base)} if base else {}
    spared = set()
    for out in outputs:
        row = {**out, "spared_group": agents.spared_group(d, out["choice"]), "audit": evaluation.audit(d, out["agent"], out, out)}
        if base:
            before = base_outputs[out["agent"]]
            row["base"] = {"choice": before["choice"], "tie": before["tie"], "spared_group": agents.spared_group(base, before["choice"]),
                           "changed": row["spared_group"] != agents.spared_group(base, before["choice"]),
                           "expected": "sensitive" if d["feature"] in evaluation.agent_def(out["agent"])["uses"] else "invariant"}
        spared.add(row["spared_group"])
        result["outputs"].append(row)
    result["unanimous"] = len(spared) == 1
    return result


@lru_cache(maxsize=1)
def cached_report():
    return evaluation.report()


@router.get("/catalog")
def catalog():
    return {"version": dilemmas.VERSION, "agents": agents.AGENTS, "parameters": agents.PARAMETERS, "features": dilemmas.FEATURES,
            "dilemmas": [summary(d) for d in dilemmas.catalog()],
            "human": {"source": human.SOURCE, "preferences": [{k: p[k] for k in ("feature", "spare", "over", "strength")} for p in human.PREFERENCES]}}


@router.get("/dilemmas/{dilemma_id}")
def dilemma(dilemma_id: str):
    d = dilemmas.get(dilemma_id)
    if not d:
        raise HTTPException(404, "Unknown dilemma.")
    return view(d)


@router.get("/report")
def report():
    return cached_report()
