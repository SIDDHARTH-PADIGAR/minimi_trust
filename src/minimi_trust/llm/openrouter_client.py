"""
Shared OpenRouter client used by both baseline 2 (pure_llm) and M4's
targeted arbitration, so both call the LLM identically — the only
difference between them is WHEN the call happens, not HOW.
"""

from __future__ import annotations

import os
import time
from typing import Optional

DEFAULT_MODEL_ENV_VAR = "MINIMI_LLM_MODEL"
DEFAULT_MODEL = "openrouter/free"


def call_openrouter_chat(system_prompt: str, user_content: str, model: Optional[str] = None) -> str:
    """Returns the raw text content of the model's reply. Raises on any
    failure (missing key, network error, exhausted retry) — callers
    decide how to fail safe; this function does not swallow errors."""
    import requests

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set")

    model_name = model or os.environ.get(DEFAULT_MODEL_ENV_VAR, DEFAULT_MODEL)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": os.environ.get("OPENROUTER_SITE_URL", "https://github.com/minimi-trust-layer"),
        "X-Title": os.environ.get("OPENROUTER_APP_NAME", "minimi-trust-layer-eval"),
    }
    payload = {
        "model": model_name,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    }

    def _post(retry: bool = True) -> dict:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers, json=payload, timeout=30,
        )
        if resp.status_code == 429 and retry:
            time.sleep(3)
            return _post(retry=False)
        resp.raise_for_status()
        return resp.json()

    data = _post()
    return data["choices"][0]["message"]["content"]