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
import time
from typing import Optional

from minimi_trust.eval.deletion_loader import DeletionScenario
from minimi_trust.eval.loader import Scenario

# --------------------------------------------------------------------------
# Baseline 1 - naive overwrite (last-write-wins, no conflict detection)
# --------------------------------------------------------------------------

def naive_overwrite_resolver(scenario: Scenario) -> tuple[bool, Optional[str]]:
    """Presumed default of a flat vector store: whichever fact was
    ingested last simply overwrites, with no timestamp or ambiguity check."""
    return False, scenario.facts[-1].object


# --------------------------------------------------------------------------
# Baseline 3 - pure deterministic, timestamp-only
# --------------------------------------------------------------------------

def pure_deterministic_resolver(scenario: Scenario) -> tuple[bool, Optional[str]]:
    """Newest observed_at always wins. No semantic candidate matching,
    no ambiguity detection - same-timestamp conflicts still get a forced
    (possibly wrong) guess, which is exactly the weakness this baseline
    is meant to expose."""
    newest = max(scenario.facts, key=lambda f: f.observed_at)
    return False, newest.object


# --------------------------------------------------------------------------
# Baseline 2 - pure LLM-mediated resolution (via OpenRouter)
# --------------------------------------------------------------------------

_LLM_SYSTEM_PROMPT = """You are given a set of timestamped candidate facts about the same subject and predicate, drawn from an ambient memory system. Decide which one is currently true, if any single one clearly is.

Respond with ONLY a JSON object, no other text, in this exact shape:
{"winning_object": "<the object string of the fact that is currently true, or null>", "unresolved": <true if genuinely ambiguous, false otherwise>}
"""


def _format_facts_for_llm(scenario: Scenario) -> str:
    lines = []
    for f in scenario.facts:
        lines.append(
            f"- object={f.object!r} observed_at={f.observed_at.isoformat()} "
            f"source={f.source_document_id} confidence={f.confidence}"
        )
    return (
        f"Subject: {scenario.query.subject}\n"
        f"Predicate: {scenario.query.predicate}\n"
        f"Candidates:\n" + "\n".join(lines)
    )


def make_pure_llm_resolver(model: Optional[str] = None):
    """
    Factory so run_baselines.py can construct this resolver lazily and
    catch a missing OPENROUTER_API_KEY without failing at module import
    time. Talks to OpenRouter's OpenAI-compatible endpoint directly via
    `requests` - no vendor SDK needed.
    """
    import requests

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set")

    model_name = model or os.environ.get("MINIMI_LLM_MODEL", "openrouter/free")

    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": os.environ.get("OPENROUTER_SITE_URL", "https://github.com/minimi-trust-layer"),
            "X-Title": os.environ.get("OPENROUTER_APP_NAME", "minimi-trust-layer-eval"),
        }
    )

    def _call(scenario: Scenario, retry: bool = True) -> dict:
        resp = session.post(
            "https://openrouter.ai/api/v1/chat/completions",
            json={
                "model": model_name,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": _LLM_SYSTEM_PROMPT},
                    {"role": "user", "content": _format_facts_for_llm(scenario)},
                ],
            },
            timeout=30,
        )
        if resp.status_code == 429 and retry:
            time.sleep(3)
            return _call(scenario, retry=False)
        resp.raise_for_status()
        return resp.json()

    def pure_llm_resolver(scenario: Scenario) -> tuple[bool, Optional[str]]:
        try:
            data = _call(scenario)
            text = data["choices"][0]["message"]["content"].strip()
        except Exception:
            return True, None

        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return True, None

        return bool(parsed.get("unresolved", False)), parsed.get("winning_object")

    return pure_llm_resolver


# --------------------------------------------------------------------------
# Baseline 4 - naive delete (unconditional success, no cascade check)
# --------------------------------------------------------------------------

def naive_delete_predict(scenario: DeletionScenario) -> str:
    """Removes the primary record and reports success unconditionally -
    no cascade trace, no residual check. This is the direct analog of
    what MemLeak found real production systems do."""
    return "verified_deleted"
