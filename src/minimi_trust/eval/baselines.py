"""
M1 — baseline implementations (§6).

Cheap-to-implement comparison points that exist so every later milestone
has something real to measure a delta against. None of these are "the
system" — they're the naive/weak approaches the real hybrid pipeline
(M2+) is built to beat, or to honestly fail to beat, and report either way.
"""

from __future__ import annotations

import json
import os
from typing import Optional

from minimi_trust.eval.deletion_loader import DeletionScenario
from minimi_trust.eval.loader import Scenario
from minimi_trust.llm.openrouter_client import call_openrouter_chat
from minimi_trust.llm.prompts import CONFLICT_ARBITRATION_SYSTEM_PROMPT, format_facts_for_arbitration

# --------------------------------------------------------------------------
# Baseline 1 — naive overwrite (last-write-wins, no conflict detection)
# --------------------------------------------------------------------------

def naive_overwrite_resolver(scenario: Scenario) -> tuple[bool, Optional[str]]:
    """Presumed default of a flat vector store: exact subject+predicate
    lookup, whichever matching fact was ingested last simply overwrites,
    with no timestamp or ambiguity check."""
    matching = [
        f for f in scenario.facts
        if f.subject == scenario.query.subject and f.predicate == scenario.query.predicate
    ]
    if not matching:
        return True, None
    return False, matching[-1].object


# --------------------------------------------------------------------------
# Baseline 3 — pure deterministic, timestamp-only
# --------------------------------------------------------------------------

def pure_deterministic_resolver(scenario: Scenario) -> tuple[bool, Optional[str]]:
    """Newest observed_at among exact subject+predicate matches always
    wins. No semantic candidate matching, no ambiguity detection."""
    matching = [
        f for f in scenario.facts
        if f.subject == scenario.query.subject and f.predicate == scenario.query.predicate
    ]
    if not matching:
        return True, None
    newest = max(matching, key=lambda f: f.observed_at)
    return False, newest.object


# --------------------------------------------------------------------------
# Baseline 2 — pure LLM-mediated resolution (via OpenRouter)
# --------------------------------------------------------------------------

def make_pure_llm_resolver(model: Optional[str] = None):
    """
    Ask the LLM directly which fact is currently true, no deterministic
    scaffolding — §6 baseline 2. Uses the same OpenRouter client and
    prompt as M4's targeted arbitration (llm/openrouter_client.py,
    llm/prompts.py), so the two are a fair comparison of WHEN the LLM is
    consulted, not HOW.

    Two changes from the original M1 version, both disclosed rather than
    silently made:
    1. The prompt now includes each fact's raw_text where present — that
       text is part of a fact's actual content, not deterministic
       scaffolding, so including it is a fairer test, but a re-run will
       not exactly reproduce the M1 number.
    2. Facts are now filtered to the query's exact subject+predicate
       before being sent — the same filtering bug fixed for the other
       two baselines at M3 was present here too but missed at the time.
    """
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise RuntimeError("OPENROUTER_API_KEY not set")

    def pure_llm_resolver(scenario: Scenario) -> tuple[bool, Optional[str]]:
        matching = [
            f for f in scenario.facts
            if f.subject == scenario.query.subject and f.predicate == scenario.query.predicate
        ]
        if not matching:
            return True, None

        prompt_content = format_facts_for_arbitration(scenario.query.subject, scenario.query.predicate, matching)
        try:
            raw = call_openrouter_chat(CONFLICT_ARBITRATION_SYSTEM_PROMPT, prompt_content, model=model)
            text = raw.strip()
            if text.startswith("```"):
                text = text.strip("`")
                if text.lower().startswith("json"):
                    text = text[4:].strip()
            parsed = json.loads(text)
        except Exception:
            return True, None

        return bool(parsed.get("unresolved", False)), parsed.get("winning_object")

    return pure_llm_resolver


# --------------------------------------------------------------------------
# Baseline 4 — naive delete (unconditional success, no cascade check)
# --------------------------------------------------------------------------

def naive_delete_predict(scenario: DeletionScenario) -> str:
    """Removes the primary record and reports success unconditionally —
    no cascade trace, no residual check. This is the direct analog of
    what MemLeak found real production systems do."""
    return "verified_deleted"