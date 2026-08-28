# Minimi Trust Layer

An MCP-native memory trust/correction system: conflict resolution, supersession, and verified deletion for ambient/agentic memory stores.

## The problem

Ambient memory systems fail at two specific, evidenced points:

1. They don't reliably detect or resolve when a newly-captured fact contradicts an older one — and when they do resolve it, they tend to silently overwrite rather than preserve the superseded fact with a record of why it changed.
2. When asked to forget something, they delete the primary record but leave it recoverable through correlated or derived representations, and report success anyway.

This project builds a small, standalone system that does both correctly, proves it with real measurement, and exposes the result through MCP.

**Not a Minimi replacement, not a general RAG app, not a memory dashboard.** No UI. Single-user, single-node, local-first. Nothing here depends on Minimi's private code or schema — this system is evaluated only against its own datasets.

## Architecture

```mermaid
flowchart TD
    A[Raw Text] -->|Extracted text| B[Extraction Service<br/>Out of scope]

    B --> C

    subgraph C[CONTROL / MUTATION PLANE]
        C1[Fact Store<br/>Append-only<br/>Event-sourced SQLite]
        C2[Conflict Detector<br/>Deterministic match first<br/>LLM only on flagged ambiguity]
        C3[Supersession Engine<br/>Marks current / superseded<br/>Never deletes rows]
        C4[Deletion + Verification Engine<br/>Cascade trace<br/>Residual-recovery check]

        C1 --> C2
        C2 --> C3
        C3 --> C4
    end

    C -->|Read-only snapshot| D

    subgraph D[RECALL PLANE]
        D1[Retrieval Index<br/>TF-IDF search over active facts]
        D2[Explain Layer<br/>Provenance<br/>Confidence<br/>Staleness<br/>Conflict flags]

        D1 --> D2
    end

    D --> E

    subgraph E[MCP SERVER]
        E1[propose_correction]
        E2[resolve_conflict]
        E3[verify_deletion]
        E4[explain_retrieval]
    end
```


**Governing principle:** two planes, one direction of dependency. The recall plane may *read* the control plane's current state; it never writes to it. All mutation happens only in the control plane, only through the four MCP tools, and every mutation is logged to an append-only event log.

## MCP tools

| Tool | What it does | Mutates? |
|---|---|---|
| `resolve_conflict(subject, predicate)` | Deterministic timestamp logic (M2) → semantic candidate matching (M3) → targeted LLM arbitration only if still ambiguous (M4). Returns the winning fact, full version history, resolution method, and `unresolved: true` rather than a forced guess. | Writes a supersession record only when a real resolution occurs. |
| `propose_correction(target_fact_id, proposed_object, rationale)` | Creates a pending correction proposal. | Writes only the proposal record — never touches the target fact. |
| `verify_deletion(target_fact_id)` | Redacts the primary record, traces derived artifacts this system actually tracks, reports a measured residual-recoverability score. `deletion_incomplete` and `residual_risk_found` are valid outcomes, not bugs. | Redacts the target fact; neutralizes trackable derived artifacts. |
| `explain_retrieval(query, top_k=5)` | TF-IDF search over active facts, annotated with provenance, confidence, staleness, and unresolved-conflict flags. | Never mutates. |

### MCP usage example

Calling `resolve_conflict` against the seeded demo data (an official HR memo vs. an admitted rumor, same timestamp):

```json
// request
{"subject": "office_relocation_date", "predicate": "is"}

// actual observed response
{
  "subject": "office_relocation_date",
  "predicate": "is",
  "unresolved": true,
  "winning_object": null,
  "resolution_method": "unresolved",
  "escalated_to_llm": true,
  "version_history": [ /* both facts, neither marked superseded */ ]
}
```

This is a real, measured result, not an illustrative one — see [Known Limitations](#known-limitations).

## Baselines (§6)

1. **Naive overwrite** — last-write-wins, no conflict detection. The presumed default of a flat vector-store system.
2. **Pure LLM-mediated resolution** — ask the LLM directly, no deterministic scaffolding.
3. **Pure deterministic (timestamp-only)** — newest `observed_at` always wins, no semantic matching, no ambiguity detection.
4. **Naive delete** — remove the row by ID, no cascade trace, report success unconditionally.

## Evaluation results

**Data labeling (§5), enforced throughout:** every scenario in this project's datasets is `SELF-AUTHORED EVALUATION DATA` — hand-built, ground-truth-labeled test cases. No claim is made about Minimi's actual data.

**Track 1 (MemoryAgentBench) was never executed in this build.** Stated here plainly rather than omitted: the raw benchmark was cloned locally (`data/track1_memoryagentbench/_raw`, gitignored) but the reformat into this project's scenario shape was never done. Every result below is Track 2 (self-authored) only.

### Conflict track (11 self-authored scenarios)

| Approach | Accuracy | Notes |
|---|---|---|
| Baseline 1 — naive overwrite | *pending `run_all.py` on current 11-scenario dataset* | Last measured at 8 scenarios (62.5%), before t2_009–011 were added |
| Baseline 3 — pure deterministic (standalone) | *pending `run_all.py`* | Last measured at 8 scenarios (75.0%) |
| Baseline 2 — pure LLM | 2/11 (18.2%) | Confirmed on current dataset |
| M2 — deterministic conflict detection (standalone) | *pending `run_all.py`* | Last measured at 10 scenarios (80.0%) |
| M3 — semantic candidate matching | 9/11 (81.8%) | Confirmed on current dataset |
| M4 — targeted LLM arbitration | 9/11 (81.8%), escalation rate 2/11 (18.2%) | Confirmed on current dataset, delta over M3 = +0.0% (see limitations) |

### Deletion track (6 self-authored scenarios)

| Approach | Accuracy |
|---|---|
| Baseline 4 — naive delete | 2/6 (33.3%) |
| M5 — deletion + cascade verification | 6/6 (100.0%) |

*Table will be finalized with the three pending cells after `run_all.py` is executed (see Reproducibility below) — this file will be updated with that output rather than left stale.*

## Known limitations

Stated explicitly, per this project's own rule that no result appears without being measured and no gap is glossed over:

- **Object-value paraphrase is not detected (`t2_007`).** M3's semantic matching compares *subject/predicate* text, never *object values* — two facts phrased differently that might genuinely conflict ("moved to next Friday" vs. a specific date) are invisible to the whole pipeline unless their keys already match. Confirmed wrong at every milestone from M3 onward. This needs a new mechanism (object-level consistency checking), not a tuning fix.
- **LLM arbitration didn't help on `t2_011` even after a prompt revision.** The case was designed to reward weighing confidence/hedging signals (0.9-confidence official memo vs. 0.4-confidence admitted rumor). The original prompt defaulted to `unresolved`; a revised prompt explicitly instructing the model to weigh those signals produced an *identical* result on re-measurement. This is a real, disclosed limitation of the specific free-tier/auto-routed model used, not investigated further within this project's scope.
- **Deletion verification can only trace what this system itself recorded.** `embedding_index`/`index_entry` artifacts are detected but not purgeable by design — this matches MemLeak's documented finding about real production systems, not a shortcut taken here.
- **Concurrency correctness is scoped to a single process/store instance**, per this project's own single-node assumption (§1). Two separate OS processes sharing one SQLite file is out of scope.
- **Small dataset (11 conflict scenarios, 6 deletion scenarios).** Percentage deltas at this scale are directional evidence that each mechanism does what it's supposed to (verified per-scenario, not just in aggregate) — not a statistically robust claim.

## Reproducibility

```powershell
git clone <this repo>
cd minimi-trust-layer
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev,llm,mcp]"

# Full regression suite
pytest -q

# The single, current, apples-to-apples evaluation run (fills the pending
# table cells above) — requires OPENROUTER_API_KEY for the pure_llm row,
# skips it cleanly if unset
$env:OPENROUTER_API_KEY = "sk-or-v1-..."
python -m minimi_trust.eval.run_all

# Run the MCP server itself (for a live client like Claude Desktop)
python -m minimi_trust.mcp_server.server
```

## Repository structure

```text
src/
└── minimi_trust/
    ├── schemas.py
    │   └── Fact / Source / Proposal / Deletion data models (M0)
    │
    ├── store/
    │   └── fact_store.py
    │       └── Append-only, event-sourced Fact Store
    │           (Thread-safe: M6 / M7)
    │
    ├── conflict/
    │   ├── Deterministic conflict detection (M2)
    │   ├── Semantic conflict detection (M3)
    │   └── LLM arbitration (M4)
    │
    ├── deletion/
    │   └── Deletion + cascade verification engine (M5)
    │
    ├── recall/
    │   ├── TF-IDF retrieval
    │   └── Explain layer (M6)
    │
    ├── mcp_server/
    │   └── Four MCP tools (M6)
    │
    ├── eval/
    │   ├── Baselines
    │   ├── Per-milestone runners
    │   └── Unified run_all.py (M8)
    │
    ├── data/
    │   └── track2_self_authored/
    │       └── Hand-built, labeled evaluation scenarios (§5)
    │
    └── tests/
        ├── Regression suite per milestone
        └── M7 hardening tests
```

## Resume-claim language

Drafted only from what was actually built and measured:

- Built and evaluated an MCP-native deletion-verification engine for AI memory systems that traces derived-artifact residuals and reports a measured recoverability score, improving verified-clean-deletion accuracy from 33.3% to 100% over a naive-delete baseline on a self-authored evaluation set — while explicitly reporting the cases where residual risk remains, rather than a simple `deleted: true`.
- Designed and implemented a deterministic-first, LLM-escalated-only-on-ambiguity conflict-resolution pipeline for ambient memory, exposed through 4 MCP tools, with an escalation rate tracked as an explicit metric to guard against LLM-arbitration creep. *(Headline accuracy delta to be added here once `run_all.py`'s pending cells are filled — this project's own rule against pre-measurement numbers applies to its own resume language too.)*
