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
MAX_ATTEMPTS = 3
# Output cap for the one-line tasks (search query, evidence rewrite). The
# free tier's binding limit is tokens per day, and a reasoning model can
# otherwise spend hundreds of hidden tokens on a one-sentence answer.
SHORT_ANSWER_MAX_TOKENS = 300

# key -> monotonic time until which it's known to be rate-limited for longer
# than a request can wait (Groq's daily token cap). Skipped until then so
# every call doesn't pay a round trip to rediscover the same 429.
_exhausted_until: dict[str, float] = {}


def _api_keys() -> list[str]:
    settings = get_settings()
    return [k for k in (settings.groq_api_key, settings.groq_api_key_fallback) if k]


def _generate(prompt: str, *, json_mode: bool = False, max_tokens: int | None = None) -> str:
    settings = get_settings()
    keys = _api_keys()
    if not keys:
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

    # Keys in order, skipping any known to be exhausted; if every key is,
    # try them all anyway in case a cap has reset early.
    now = time.monotonic()
    usable = [k for k in keys if _exhausted_until.get(k, 0.0) <= now] or keys
    last_response = None
    for key in usable:
        resp = _post_with_retries(payload, key, settings.groq_timeout_seconds)
        if resp.status_code == 429:
            # waited out every short limit and still capped: this key is done
            # for a while, so move on to the next one
            _exhausted_until[key] = time.monotonic() + float(resp.headers.get("retry-after", 60.0))
            logger.warning("Groq key ending …%s is rate-limited; trying the next key if there is one", key[-4:])
            last_response = resp
            continue
        resp.raise_for_status()
        return (resp.json()["choices"][0]["message"]["content"] or "").strip()
    last_response.raise_for_status()
    raise RuntimeError("unreachable")


def _post_with_retries(payload: dict, key: str, timeout: float) -> httpx.Response:
    """Short retries on a rate limit: the binding free-tier limit in practice
    is tokens per minute (8k for gpt-oss-20b), and a multi-claim request fires
    its claims' LLM calls together, so a burst often clears within seconds. A
    longer wait (the daily cap) isn't worth blocking a request - that 429 is
    returned to the caller, which moves on to the fallback key."""
    headers = {"Authorization": f"Bearer {key}"}
    for attempt in range(MAX_ATTEMPTS):
        resp = httpx.post(GROQ_URL, json=payload, headers=headers, timeout=timeout)
        if resp.status_code == 429 and attempt < MAX_ATTEMPTS - 1:
            wait = float(resp.headers.get("retry-after", 1.0))
            if wait <= MAX_RETRY_WAIT_SECONDS:
                time.sleep(wait)
                continue
        return resp
    return resp


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
