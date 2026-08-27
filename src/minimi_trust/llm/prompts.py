"""
Shared prompt construction for both baseline 2 (pure_llm) and M4's
targeted arbitration — both must send the model an identical framing for
a delta between them to mean "escalation policy," not "prompt wording."

Revised after M4 evidence (t2_011): the model has real signals available
(confidence score, hedged vs. authoritative language) but wasn't told to
weigh them, so it defaulted to "unresolved" even on a case with a real
basis to decide. This prompt makes that weighing explicit WITHOUT
removing "unresolved" as a valid answer — a genuine tie (equal
confidence, equal certainty, flat disagreement, e.g. t2_005) should
still come back unresolved. The fix is "use the evidence you have,"
not "never say you're not sure."
"""

from __future__ import annotations

from minimi_trust.schemas import Fact

CONFLICT_ARBITRATION_SYSTEM_PROMPT = """You are given a set of timestamped candidate facts about the same subject and predicate, drawn from an ambient memory system. Decide which one is currently true, if any single one clearly is.

Weigh every signal available to you, not just recency:
- the confidence score attached to each candidate
- whether the source note reads as authoritative/confirmed (e.g. an official memo, a direct firsthand statement) versus tentative/hedged (e.g. "heard," "rumor," "not sure," "might be")
- consistency with any other candidates

Only report unresolved if, after weighing those signals, there is truly no basis to prefer one candidate over another — for example, two equally confident, equally authoritative sources that flatly disagree. Do not report unresolved merely because you are not 100% certain; if the evidence reasonably favors one candidate, report that one as the answer.

Respond with ONLY a JSON object, no other text, in this exact shape:
{"winning_object": "<the object string of the fact that is currently true, or null>", "unresolved": <true if genuinely ambiguous after weighing the above, false otherwise>}
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