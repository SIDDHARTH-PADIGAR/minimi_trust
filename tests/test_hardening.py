"""
M7 — hardening regression tests, mapped directly to §7's failure list.

Conflicting/stale/duplicate/ambiguous facts, deletion failures, and
correlated-memory residuals already have regression tests from M2-M5
(tests/test_conflict_detector.py, tests/test_deletion_engine.py) — not
duplicated here. This file covers the failure categories that had no
test at all until now: malformed MCP requests, an unavailable LLM
(at the actual MCP layer, not just the unit-tested arbitrator),
store failure, and concurrent updates.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import datetime, timezone

import pytest
from fastmcp import Client

from minimi_trust.mcp_server.server import build_server_with_store
from minimi_trust.schemas import Fact
from minimi_trust.store.fact_store import FactStore


def _payload(result) -> dict:
    if result.data is not None:
        return result.data
    return json.loads(result.content[0].text)


# -- malformed MCP requests -----------------------------------------------

@pytest.mark.asyncio
async def test_malformed_request_missing_required_arg_is_rejected_cleanly(server):
    async with Client(server) as client:
        with pytest.raises(Exception) as exc_info:
            await client.call_tool("resolve_conflict", {"subject": "x"})  # missing predicate
        message = str(exc_info.value).lower()
        assert "predicate" in message or "required" in message or "validation" in message


@pytest.mark.asyncio
async def test_malformed_request_wrong_type_is_rejected_cleanly(server):
    async with Client(server) as client:
        with pytest.raises(Exception):
            await client.call_tool("explain_retrieval", {"query": "wifi", "top_k": "not_a_number"})


# -- unavailable LLM, at the actual MCP layer -------------------------------

@pytest.mark.asyncio
async def test_resolve_conflict_degrades_gracefully_when_llm_unavailable(monkeypatch, server):
    def _boom(*args, **kwargs):
        raise RuntimeError("simulated: LLM unavailable")

    monkeypatch.setattr("minimi_trust.conflict.llm_arbitrator.call_openrouter_chat", _boom)

    async with Client(server) as client:
        result = await client.call_tool(
            "resolve_conflict", {"subject": "office_relocation_date", "predicate": "is"}
        )
        payload = _payload(result)
        # LLM unavailable -> falls back to M3's own result, tool call
        # still succeeds cleanly rather than erroring out.
        assert payload["unresolved"] is True
        assert payload["escalated_to_llm"] is True


# -- store failure -----------------------------------------------------------

def test_unwritable_db_path_raises_clean_error(tmp_path):
    bad_path = tmp_path / "no_such_directory" / "nested" / "store.db"  # parent never created
    with pytest.raises(sqlite3.OperationalError):
        FactStore(str(bad_path))


# -- concurrent updates -------------------------------------------------------

@pytest.mark.asyncio
async def test_concurrent_resolve_conflict_calls_do_not_double_resolve():
    store = FactStore(":memory:")
    ts_old = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)
    ts_new = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
    store.add_fact(Fact(
        subject="concurrency_test_subject", predicate="is", object="old_value",
        source_document_id="src_a", observed_at=ts_old, extracted_at=ts_old, confidence=0.9,
    ))
    store.add_fact(Fact(
        subject="concurrency_test_subject", predicate="is", object="new_value",
        source_document_id="src_b", observed_at=ts_new, extracted_at=ts_new, confidence=0.9,
    ))

    mcp, store = build_server_with_store(store=store)

    async with Client(mcp) as client:
        results = await asyncio.gather(
            client.call_tool("resolve_conflict", {"subject": "concurrency_test_subject", "predicate": "is"}),
            client.call_tool("resolve_conflict", {"subject": "concurrency_test_subject", "predicate": "is"}),
        )

    for result in results:
        payload = _payload(result)
        assert payload["winning_object"] == "new_value"

    # The operation_lock should have serialized the two calls: the second
    # one to actually run finds only one ACTIVE fact left (no contention)
    # and never re-consolidates — exactly one supersession event, not two.
    supersession_events = store.get_events("supersession")
    assert len(supersession_events) == 1