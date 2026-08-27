"""
M4 unit tests for TargetedLLMArbitrator — the LLM call is monkeypatched
so these run without OPENROUTER_API_KEY or network access. Only the
escalation logic (when to call, how to use the result, how to fail
safe) is under test here.
"""

import json
from datetime import datetime, timezone

from minimi_trust.conflict import llm_arbitrator as llm_arbitrator_module
from minimi_trust.conflict.llm_arbitrator import TargetedLLMArbitrator
from minimi_trust.schemas import Fact, ResolutionMethod
from minimi_trust.store.fact_store import FactStore


def _fact(subject, predicate, object_, observed_at, raw_text=None, confidence=0.9):
    return Fact(
        subject=subject, predicate=predicate, object=object_,
        source_document_id="src_test", observed_at=observed_at, extracted_at=observed_at,
        confidence=confidence, raw_text=raw_text,
    )


def test_not_escalated_when_m3_already_resolves(monkeypatch):
    def _should_not_be_called(*args, **kwargs):
        raise AssertionError("LLM should not be called when M3 already resolves confidently")

    monkeypatch.setattr(llm_arbitrator_module, "call_openrouter_chat", _should_not_be_called)

    with FactStore(":memory:") as store:
        store.add_fact(_fact("x", "is", "y", datetime(2026, 1, 1, tzinfo=timezone.utc)))
        result = TargetedLLMArbitrator(store).resolve_conflict("x", "is")
        assert not result.escalated
        assert not result.unresolved
        assert result.winning_object == "y"


def test_not_escalated_when_nothing_to_reason_over(monkeypatch):
    def _should_not_be_called(*args, **kwargs):
        raise AssertionError("LLM should not be called when there are no active facts")

    monkeypatch.setattr(llm_arbitrator_module, "call_openrouter_chat", _should_not_be_called)

    with FactStore(":memory:") as store:
        result = TargetedLLMArbitrator(store).resolve_conflict("nonexistent", "is")
        assert not result.escalated
        assert result.unresolved


def test_escalated_on_genuine_same_timestamp_tie(monkeypatch):
    ts = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def _fake_call(system_prompt, user_content, model=None):
        return json.dumps({"winning_object": "official_value", "unresolved": False})

    monkeypatch.setattr(llm_arbitrator_module, "call_openrouter_chat", _fake_call)

    with FactStore(":memory:") as store:
        store.add_fact(_fact("x", "is", "official_value", ts, raw_text="per the official memo"))
        store.add_fact(_fact("x", "is", "rumor_value", ts, raw_text="heard through the grapevine"))
        result = TargetedLLMArbitrator(store).resolve_conflict("x", "is")
        assert result.escalated
        assert not result.unresolved
        assert result.winning_object == "official_value"
        assert result.resolution_method == ResolutionMethod.LLM_ARBITRATED


def test_llm_failure_falls_back_to_m3_result_not_a_crash(monkeypatch):
    ts = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def _fake_call(system_prompt, user_content, model=None):
        raise RuntimeError("simulated network failure")

    monkeypatch.setattr(llm_arbitrator_module, "call_openrouter_chat", _fake_call)

    with FactStore(":memory:") as store:
        store.add_fact(_fact("x", "is", "a", ts))
        store.add_fact(_fact("x", "is", "b", ts))
        result = TargetedLLMArbitrator(store).resolve_conflict("x", "is")
        assert result.escalated
        assert result.unresolved