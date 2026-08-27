"""
Fact Store — append-only, event-sourced (§2 Control/Mutation Plane, §3).

Facts are never deleted or overwritten in place: superseding a fact means
flipping the old row's status, not removing it. Every mutation is also
written to the event_log table, which is the provenance backbone
`explain_retrieval` reads from in a later milestone — not a separate
audit bolt-on.

SQLite per §8: no heavier infrastructure until a milestone's measurement
actually shows this is insufficient.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from minimi_trust.schemas import Fact, FactStatus, ResolutionMethod

_SCHEMA = """
CREATE TABLE IF NOT EXISTS facts (
    id TEXT PRIMARY KEY,
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object TEXT NOT NULL,
    raw_text TEXT,
    source_document_id TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    extracted_at TEXT NOT NULL,
    confidence REAL NOT NULL,
    status TEXT NOT NULL,
    supersedes_id TEXT,
    resolution_method TEXT NOT NULL,
    embedding_ref TEXT
);

CREATE INDEX IF NOT EXISTS idx_facts_subject_predicate
    ON facts (subject, predicate);

CREATE TABLE IF NOT EXISTS event_log (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    payload TEXT NOT NULL
);
"""


class FactStore:
    def __init__(self, db_path: str | Path = ":memory:"):
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "FactStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- writes --------------------------------------------------------

    def add_fact(self, fact: Fact) -> Fact:
        self._conn.execute(
            """INSERT INTO facts
               (id, subject, predicate, object, raw_text, source_document_id,
                observed_at, extracted_at, confidence, status, supersedes_id,
                resolution_method, embedding_ref)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                fact.id, fact.subject, fact.predicate, fact.object, fact.raw_text,
                fact.source_document_id, fact.observed_at.isoformat(),
                fact.extracted_at.isoformat(), fact.confidence, fact.status.value,
                fact.supersedes_id, fact.resolution_method.value, fact.embedding_ref,
            ),
        )
        self._conn.commit()
        self._log_event("fact_added", {"fact_id": fact.id, "subject": fact.subject, "predicate": fact.predicate})
        return fact

    def set_status(self, fact_id: str, status: FactStatus) -> None:
        self._conn.execute("UPDATE facts SET status = ? WHERE id = ?", (status.value, fact_id))
        self._conn.commit()

    def set_supersedes(self, fact_id: str, supersedes_id: str) -> None:
        self._conn.execute("UPDATE facts SET supersedes_id = ? WHERE id = ?", (supersedes_id, fact_id))
        self._conn.commit()

    def set_resolution_method(self, fact_id: str, method: ResolutionMethod) -> None:
        self._conn.execute("UPDATE facts SET resolution_method = ? WHERE id = ?", (method.value, fact_id))
        self._conn.commit()

    def log_supersession_event(
        self, subject: str, predicate: str, winning_fact_id: str,
        superseded_fact_ids: list[str], method: str, reason: str,
    ) -> None:
        self._log_event(
            "supersession",
            {
                "subject": subject,
                "predicate": predicate,
                "winning_fact_id": winning_fact_id,
                "superseded_fact_ids": superseded_fact_ids,
                "method": method,
                "reason": reason,
            },
        )

    def _log_event(self, event_type: str, payload: dict) -> None:
        self._conn.execute(
            "INSERT INTO event_log (event_type, occurred_at, payload) VALUES (?, ?, ?)",
            (event_type, datetime.utcnow().isoformat(), json.dumps(payload)),
        )
        self._conn.commit()

    # -- reads -----------------------------------------------------------

    def get_facts(self, subject: str, predicate: str) -> list[Fact]:
        rows = self._conn.execute(
            "SELECT * FROM facts WHERE subject = ? AND predicate = ? ORDER BY observed_at ASC",
            (subject, predicate),
        ).fetchall()
        return [_row_to_fact(r) for r in rows]

    def get_distinct_subject_predicate_pairs(self) -> list[tuple[str, str]]:
        rows = self._conn.execute("SELECT DISTINCT subject, predicate FROM facts").fetchall()
        return [(r["subject"], r["predicate"]) for r in rows]

    def get_events(self, event_type: Optional[str] = None) -> list[dict]:
        if event_type:
            rows = self._conn.execute(
                "SELECT * FROM event_log WHERE event_type = ? ORDER BY event_id ASC", (event_type,)
            ).fetchall()
        else:
            rows = self._conn.execute("SELECT * FROM event_log ORDER BY event_id ASC").fetchall()
        return [
            {
                "event_id": r["event_id"], "event_type": r["event_type"],
                "occurred_at": r["occurred_at"], "payload": json.loads(r["payload"]),
            }
            for r in rows
        ]


def _row_to_fact(row: sqlite3.Row) -> Fact:
    return Fact(
        id=row["id"], subject=row["subject"], predicate=row["predicate"], object=row["object"],
        raw_text=row["raw_text"], source_document_id=row["source_document_id"],
        observed_at=row["observed_at"], extracted_at=row["extracted_at"], confidence=row["confidence"],
        status=FactStatus(row["status"]), supersedes_id=row["supersedes_id"],
        resolution_method=ResolutionMethod(row["resolution_method"]), embedding_ref=row["embedding_ref"],
    )