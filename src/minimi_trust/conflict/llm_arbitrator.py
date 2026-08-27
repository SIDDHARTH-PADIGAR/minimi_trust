"""
Targeted LLM Arbitration (M4).

Runs the M3 SemanticConflictDetector first; only escalates to the LLM
when M3 reports unresolved=True AND there is at least one real active
fact to reason over — the trivial "no facts found" case has nothing an
LLM could add and is never escalated. Escalation is deliberately narrow
per §8's LLM-arbitration-creep guard: the escalation rate is tracked and
reported as its own metric, never folded silently into accuracy.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

from minimi_trust.conflict.semantic_detector import SemanticConflictDetector, SemanticConflictResolution
from minimi_trust.llm.openrouter_client import call_openrouter_chat
from minimi_trust.llm.prompts import CONFLICT_ARBITRATION_SYSTEM_PROMPT, format_facts_for_arbitration
from minimi_trust.schemas import FactStatus, ResolutionMethod
from minimi_trust.store.fact_store import FactStore


@dataclass
class ArbitratedResolution:
    base: SemanticConflictResolution
    escalated: bool
    winning_object: Optional[str]
    unresolved: bool
    resolution_method: ResolutionMethod
    llm_raw_response: Optional[str] = None


class TargetedLLMArbitrator:
    def __init__(self, store: FactStore, model: Optional[str] = None):
        self.store = store
        self.model = model
        self.detector = SemanticConflictDetector(store)

    def resolve_conflict(self, subject: str, predicate: str) -> ArbitratedResolution:
        base = self.detector.resolve_conflict(subject, predicate)
        active = [f for f in base.version_history if f.status == FactStatus.ACTIVE]

        if not base.unresolved or not active:
            return ArbitratedResolution(
                base=base, escalated=False,
                winning_object=base.winning_fact.object if base.winning_fact else None,
                unresolved=base.unresolved, resolution_method=base.resolution_method,
            )

        prompt_content = format_facts_for_arbitration(subject, predicate, active)
        try:
            raw = call_openrouter_chat(CONFLICT_ARBITRATION_SYSTEM_PROMPT, prompt_content, model=self.model)
            text = raw.strip()
            if text.startswith("```"):
                text = text.strip("`")
                if text.lower().startswith("json"):
                    text = text[4:].strip()
            parsed = json.loads(text)
            llm_unresolved = bool(parsed.get("unresolved", False))
            llm_winner = parsed.get("winning_object")
        except Exception:
            # LLM unavailable or malformed — fall back to M3's honest
            # unresolved result rather than crash or force a guess.
            # Still counted as escalated: the attempt was genuinely made.
            return ArbitratedResolution(
                base=base, escalated=True,
                winning_object=base.winning_fact.object if base.winning_fact else None,
                unresolved=base.unresolved, resolution_method=base.resolution_method,
                llm_raw_response=None,
            )

        return ArbitratedResolution(
            base=base, escalated=True, winning_object=llm_winner, unresolved=llm_unresolved,
            resolution_method=ResolutionMethod.UNRESOLVED if llm_unresolved else ResolutionMethod.LLM_ARBITRATED,
            llm_raw_response=raw,
        )