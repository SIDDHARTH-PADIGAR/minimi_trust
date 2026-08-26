# Track 1 source — MemoryAgentBench

Not vendored in this repo. Pull the raw benchmark locally (gitignored) with:

    git clone https://github.com/HUST-AI-HYZ/MemoryAgentBench data/track1_memoryagentbench/_raw

Reformatting the FactConsolidation split into this project's `Scenario`
shape (see `src/minimi_trust/eval/loader.py`) is scoped as an M0
follow-up — not done in this commit. Nothing in this project claims
Track 1 coverage until that reformat script exists and has been run.