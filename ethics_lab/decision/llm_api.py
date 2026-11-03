"""HTTP routes for the optional language-model agents. The deterministic lab works without any of this."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import llm

router = APIRouter(prefix="/api/decision/llm", tags=["decision-llm"])


class RunBody(BaseModel):
    dilemma_id: str
    repeat: bool = False


@router.get("/status")
def status():
    return llm.status()


@router.post("/run")
def run(body: RunBody):
    result = llm.run(body.dilemma_id, body.repeat)
    if result is None:
        raise HTTPException(404, "Unknown dilemma.")
    return result


@router.get("/results")
def results(dilemma_id: str):
    found = llm.results(dilemma_id)
    if found is None:
        raise HTTPException(404, "Unknown dilemma.")
    return {"results": found}
