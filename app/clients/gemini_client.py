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

Each claim must be self-contained and understandable on its own: replace pronouns and vague references \
("it", "he", "the company", "this year") with the specific name, place or date they refer to in the text.

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


SEARCH_QUERY_PROMPT = """Given the following factual claim, write the single best short web/encyclopedia \
search query (3-8 words) to find evidence that would confirm or refute it. Prefer specific, well-known \
terminology over vague paraphrasing - e.g. for a claim about vaccines and autism, prefer "MMR vaccine autism \
controversy" over just "vaccines". Name the topic itself; don't pad the query with words like "evidence", \
"confirmation", "fact check", "true" or "myth". Return ONLY the query text, with no quotes, labels, or explanation.

Claim: "{claim_text}"
"""


def generate_search_query(claim_text: str) -> str:
    """A search query for claims where entity-extraction alone produces a
    weak one - e.g. "Vaccines cause autism" tags "Vaccines" as a NORP entity
    and "autism" as nothing, so the entity query is just "Vaccines" and never
    finds the actual controversy article."""
    settings = get_settings()
    client = _get_client()
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=SEARCH_QUERY_PROMPT.format(claim_text=claim_text),
    )
    return (response.text or "").strip().strip('"').strip("'")


EVIDENCE_CLAIM_EXTRACTION_PROMPT = """You are a fact-checking assistant. You are given a CLAIM and an \
EVIDENCE passage found by a search engine. Write exactly one clean, direct, declarative sentence stating \
what the evidence actually asserts about the claim's topic - not a summary of the passage, not a restatement \
of the claim, and not a question.

Rules:
- If the evidence frames something as a myth, misconception, hoax, or debunked belief, state the true fact \
directly (e.g. "Einstein was in fact a strong mathematics student; the story that he failed math is a myth" \
- NOT "the claim that Einstein failed math is a myth" and NOT a repetition of the myth itself).
- If the evidence is phrased as a question that is never actually answered in the passage, or does not \
address the claim's topic at all, respond with exactly: UNDETERMINED
- Address the claim's SPECIFIC assertion. If the evidence takes a position on it, state that position \
(e.g. for the claim "mRNA vaccines alter human DNA", write "mRNA vaccines do not alter human DNA" - NOT a \
related true fact such as "mRNA vaccines deliver genetic instructions to cells", which sidesteps the claim). \
Only if the evidence never addresses the specific assertion, state its closest relevant fact.
- Never end your sentence with a question mark.
- Do not just restate the claim in different words - state what the EVIDENCE says, which may support, \
refute, or say nothing about the claim.

CLAIM: "{claim_text}"

EVIDENCE: "{evidence_text}"

Respond with ONLY the one sentence (or UNDETERMINED), nothing else.
"""

_EVIDENCE_CLAIM_SENTINELS = {"UNDETERMINED", "N/A", "NONE", "UNKNOWN"}


def _normalize_evidence_claim(text: str) -> str:
    """"" (the "could not resolve" signal, matching extract_claims's "[]"
    convention) when the raw response doesn't commit to an answer, doesn't
    address the claim's topic, or is otherwise unusable."""
    cleaned = (text or "").strip().strip('"').strip("'")
    if not cleaned or cleaned.upper() in _EVIDENCE_CLAIM_SENTINELS or "?" in cleaned:
        return ""
    return cleaned


def extract_evidence_claim(claim_text: str, evidence_text: str) -> str:
    """Normalizes one evidence document into a single clean, unhedged
    sentence stating what it asserts about the claim's topic, for stage 7b
    to run a fresh, less-ambiguous NLI check against."""
    settings = get_settings()
    client = _get_client()
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=EVIDENCE_CLAIM_EXTRACTION_PROMPT.format(claim_text=claim_text, evidence_text=evidence_text),
    )
    return _normalize_evidence_claim(response.text or "")


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
