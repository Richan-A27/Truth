"""Groq backend (OpenAI-compatible chat API). Same public functions and
prompts as ollama_client - only the transport differs."""

import json
import logging
import time

import httpx

from app.clients import ollama_client as _prompts
from app.config import get_settings

logger = logging.getLogger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MAX_RETRY_WAIT_SECONDS = 5.0
# Output cap for the one-line tasks (search query, evidence rewrite). The
# free tier's binding limit is tokens per day, and a reasoning model can
# otherwise spend hundreds of hidden tokens on a one-sentence answer.
SHORT_ANSWER_MAX_TOKENS = 300


def _generate(prompt: str, *, json_mode: bool = False, max_tokens: int | None = None) -> str:
    settings = get_settings()
    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY is not set")
    payload = {
        "model": settings.groq_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
    }
    if settings.groq_model.startswith("openai/gpt-oss"):
        # reasoning model: these are short extraction/narration tasks, so a
        # long hidden chain of thought only adds latency
        payload["reasoning_effort"] = "low"
    if max_tokens:
        payload["max_completion_tokens"] = max_tokens
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    headers = {"Authorization": f"Bearer {settings.groq_api_key}"}

    # one short retry on a rate limit: Groq's limits are per-minute, so a brief
    # wait usually clears them; anything longer is not worth blocking a request
    for attempt in range(2):
        resp = httpx.post(GROQ_URL, json=payload, headers=headers, timeout=settings.groq_timeout_seconds)
        if resp.status_code == 429 and attempt == 0:
            wait = float(resp.headers.get("retry-after", 1.0))
            if wait <= MAX_RETRY_WAIT_SECONDS:
                time.sleep(wait)
                continue
        resp.raise_for_status()
        return (resp.json()["choices"][0]["message"]["content"] or "").strip()
    raise RuntimeError("unreachable")


def generate_explanation(
    *,
    claim_text: str,
    verdict_label: str,
    trust_score: int,
    supporting_count: int,
    contradicting_count: int,
    evidence_snippets: list[str],
) -> str:
    snippets_text = "\n".join(f"- {s}" for s in evidence_snippets) or "- (no evidence found)"
    prompt = _prompts.EXPLANATION_PROMPT.format(
        claim_text=claim_text,
        verdict_label=verdict_label,
        trust_score=trust_score,
        supporting_count=supporting_count,
        contradicting_count=contradicting_count,
        evidence_snippets=snippets_text,
    )
    return _generate(prompt)


def generate_search_query(claim_text: str) -> str:
    text = _generate(_prompts.SEARCH_QUERY_PROMPT.format(claim_text=claim_text), max_tokens=SHORT_ANSWER_MAX_TOKENS)
    return text.strip().strip('"').strip("'")


def extract_evidence_claim(claim_text: str, evidence_text: str) -> str:
    prompt = _prompts.EVIDENCE_CLAIM_EXTRACTION_PROMPT.format(claim_text=claim_text, evidence_text=evidence_text)
    return _prompts._normalize_evidence_claim(_generate(prompt, max_tokens=SHORT_ANSWER_MAX_TOKENS))


def extract_claims(content: str) -> list[str]:
    text = _generate(_prompts.CLAIM_EXTRACTION_PROMPT.format(content=content), json_mode=True)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Groq claim extraction returned invalid JSON: %r", text)
        return []
    if isinstance(parsed, dict):
        parsed = parsed.get("claims", [])
    if not isinstance(parsed, list):
        logger.warning("Groq claim extraction returned unexpected shape: %r", parsed)
        return []
    return [str(c).strip() for c in parsed if str(c).strip()]
