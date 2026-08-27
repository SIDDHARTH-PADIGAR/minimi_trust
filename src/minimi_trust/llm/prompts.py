"""
Shared prompt construction for both baseline 2 (pure_llm) and M4's
targeted arbitration — both must send the model an identical framing for
a delta between them to mean "escalation policy," not "prompt wording."
"""

from __future__ import annotations

from minimi_trust.schemas import Fact

CONFLICT_ARBITRATION_SYSTEM_PROMPT = """You are given a set of timestamped candidate facts about the same subject and predicate, drawn from an ambient memory system. Decide which one is currently true, if any single one clearly is.

Respond with ONLY a JSON object, no other text, in this exact shape:
{"winning_object": "<the object string of the fact that is currently true, or null>", "unresolved": <true if genuinely ambiguous, false otherwise>}
"""


def format_facts_for_arbitration(subject: str, predicate: str, facts: list[Fact]) -> str:
    lines = []
    for f in facts:
        line = (
            f"- object={f.object!r} observed_at={f.observed_at.isoformat()} "
            f"source={f.source_document_id} confidence={f.confidence}"
        )
        if f.raw_text:
            line += f" note={f.raw_text!r}"
        lines.append(line)
    return f"Subject: {subject}\nPredicate: {predicate}\nCandidates:\n" + "\n".join(lines)