"""
Demo data seeding for the MCP server (M6).

This project has no ingestion pipeline (§8 non-goal) — none of the four
§4 tools creates a new fact from raw text — so something has to put
initial facts in the store for a live MCP client to call these tools
against. Seeds ONCE, only if the store is currently empty, so restarting
the server never duplicates or overwrites real data.

Subjects are deliberately topic-distinct with no shared words beyond the
predicate "is" — an earlier version suffixed every subject with "_demo"
(and two also shared "office"), which the TF-IDF semantic matcher
correctly read as genuine topical overlap and merged unrelated facts
into the same conflict resolution. Fact IDs and source_document_id
values still carry a demo_ prefix for readability — those aren't part
of what the matcher compares, so they're safe to keep.

DEMO DATA — SELF-AUTHORED, for MCP server smoke-testing only. Not a
claim about any real system's actual data (§5 labeling convention
extended here for consistency).
"""

from __future__ import annotations

from datetime import datetime, timezone

from minimi_trust.schemas import Fact
from minimi_trust.store.fact_store import FactStore


def seed_demo_data_if_empty(store: FactStore) -> None:
    if store.get_distinct_subject_predicate_pairs():
        return  # already has data — never overwrite

    relocation_ts = datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)
    store.add_fact(Fact(
        id="demo_fact_relocation_official", subject="office_relocation_date", predicate="is",
        object="2026-10-01", source_document_id="demo_doc_hr_official",
        observed_at=relocation_ts, extracted_at=relocation_ts, confidence=0.9,
        raw_text="Per the official HR relocation memo, the new office opens October 1, 2026.",
    ))
    store.add_fact(Fact(
        id="demo_fact_relocation_rumor", subject="office_relocation_date", predicate="is",
        object="2026-10-15", source_document_id="demo_doc_slack_rumor",
        observed_at=relocation_ts, extracted_at=relocation_ts, confidence=0.4,
        raw_text="heard through the grapevine it might be pushed to mid-October, not 100% sure though",
    ))

    salary_ts = datetime(2026, 4, 1, 9, 0, tzinfo=timezone.utc)
    store.add_fact(Fact(
        id="demo_fact_salary_note", subject="salary_note", predicate="is",
        object="confidential_comp_detail", source_document_id="demo_doc_salary_note",
        observed_at=salary_ts, extracted_at=salary_ts, confidence=0.85,
    ))
    store.add_derived_artifact(
        "demo_fact_salary_note", "dependent_fact", "demo_comp_summary_ref",
        "derived summary fact built from this note",
    )
    store.add_derived_artifact(
        "demo_fact_salary_note", "embedding_index", "demo_emb_salary_note", "vector index entry",
    )

    wifi_ts = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
    store.add_fact(Fact(
        id="demo_fact_wifi", subject="wifi_password", predicate="is",
        object="hunter2", source_document_id="demo_doc_note",
        observed_at=wifi_ts, extracted_at=wifi_ts, confidence=0.9,
        raw_text="the office wifi password is hunter2",
    ))