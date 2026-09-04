import json
import logging

from google import genai

from app.config import get_settings

logger = logging.getLogger(__name__)

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        settings = get_settings()
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


CLAIM_EXTRACTION_PROMPT = """You are a fact-checking assistant. Read the text below and extract every \
discrete, checkable factual claim it makes (statements that could in principle be verified as true or \
false against evidence). Ignore opinions, questions, and rhetorical statements.

Return ONLY a JSON array of strings, one per claim, in the order they appear. If there are no checkable \
claims, return [].

Text:
\"\"\"
{content}
\"\"\"
"""

EXPLANATION_PROMPT = """You are a fact-checking assistant writing a short, neutral explanation of a \
verification result for an end user.

Claim: "{claim_text}"
Verdict: {verdict_label} (trust score: {trust_score}/100)
Supporting evidence count: {supporting_count}
Contradicting evidence count: {contradicting_count}
Top evidence snippets:
{evidence_snippets}

Write a concise (2-4 sentence) explanation of why the claim received this verdict, referencing the \
evidence. Do not invent facts beyond what's given above.
"""


def extract_claims(content: str) -> list[str]:
    settings = get_settings()
    client = _get_client()
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=CLAIM_EXTRACTION_PROMPT.format(content=content),
    )
    text = (response.text or "").strip()
    claims = _parse_claims_json(text)
    if claims is None:
        logger.warning("Gemini claim extraction returned unparseable output: %r", text)
        return []
    return [str(c).strip() for c in claims if str(c).strip()]


def _parse_claims_json(text: str) -> list | None:
    """Best-effort parse of a JSON array out of an LLM response. Models
    sometimes ignore "return ONLY JSON" and wrap the array in a code fence
    or a sentence of commentary, so fall back to extracting the first
    top-level [...] span before giving up."""
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = candidate.strip("`")
        if candidate.startswith("json"):
            candidate = candidate[4:]
        candidate = candidate.strip()

    for attempt in (candidate, text):
        try:
            parsed = json.loads(attempt)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, list):
            return parsed

    start, end = text.find("["), text.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
        if isinstance(parsed, list):
            return parsed
    return None


def generate_explanation(
    *,
    claim_text: str,
    verdict_label: str,
    trust_score: int,
    supporting_count: int,
    contradicting_count: int,
    evidence_snippets: list[str],
) -> str:
    settings = get_settings()
    client = _get_client()
    snippets_text = "\n".join(f"- {s}" for s in evidence_snippets) or "- (no evidence found)"
    prompt = EXPLANATION_PROMPT.format(
        claim_text=claim_text,
        verdict_label=verdict_label,
        trust_score=trust_score,
        supporting_count=supporting_count,
        contradicting_count=contradicting_count,
        evidence_snippets=snippets_text,
    )
    response = client.models.generate_content(model=settings.gemini_model, contents=prompt)
    return (response.text or "").strip()
