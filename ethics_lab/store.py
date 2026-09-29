"""Small local run journal with atomic edits and replayable events."""

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path


def database_path():
    return Path(os.environ.get("ETHICS_DB", str(Path(__file__).resolve().parent.parent / "data" / "runs.sqlite3")))


@contextmanager
def connect():
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path, timeout=10) as db:
        db.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, body TEXT NOT NULL)")
        yield db


def save_new(run):
    with connect() as db:
        db.execute("INSERT INTO runs VALUES (?, ?)", (run["id"], json.dumps(run)))


def get(run_id):
    with connect() as db:
        row = db.execute("SELECT body FROM runs WHERE id = ?", (run_id,)).fetchone()
    return json.loads(row[0]) if row else None


def update(run_id, operation):
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT body FROM runs WHERE id = ?", (run_id,)).fetchone()
        if not row:
            return None
        run = json.loads(row[0])
        operation(run)
        db.execute("UPDATE runs SET body = ? WHERE id = ?", (json.dumps(run), run_id))
    return run
