import json
import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


def _generate(prompt: str, *, json_mode: bool = False) -> str:
    """POST a single-turn prompt to the local Ollama server and return its
    text response. Ollama has no rate limits or network variance to retry
    around - if it fails, the server almost certainly isn't running."""
    settings = get_settings()
    payload = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1},  # low: we want consistent extraction, not creative writing
    }
    if json_mode:
        payload["format"] = "json"  # Ollama constrains generation to valid JSON when supported by the model

    try:
        resp = httpx.post(
            f"{settings.ollama_base_url}/api/generate",
            json=payload,
            timeout=settings.ollama_timeout_seconds,
        )
        resp.raise_for_status()
    except httpx.ConnectError as exc:
        raise RuntimeError(
            f"Could not reach Ollama at {settings.ollama_base_url} - is `ollama serve` running?"
        ) from exc

    return resp.json().get("response", "").strip()


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
    prompt = EXPLANATION_PROMPT.format(
        claim_text=claim_text,
        verdict_label=verdict_label,
        trust_score=trust_score,
        supporting_count=supporting_count,
        contradicting_count=contradicting_count,
        evidence_snippets=snippets_text,
    )
    return _generate(prompt)


SEARCH_QUERY_PROMPT = """Given the following factual claim, write the single best short web/encyclopedia \
search query (3-8 words) to find evidence that would confirm or refute it. Prefer specific, well-known \
terminology over vague paraphrasing - e.g. for a claim about vaccines and autism, prefer "MMR vaccine autism \
controversy" over just "vaccines". Return ONLY the query text, with no quotes, labels, or explanation.

Claim: "{claim_text}"
"""


def generate_search_query(claim_text: str) -> str:
    """A search query for claims where entity-extraction alone produces a
    weak one - e.g. "Vaccines cause autism" tags "Vaccines" as a NORP entity
    and "autism" as nothing, so the entity query is just "Vaccines" and never
    finds the actual controversy article."""
    prompt = SEARCH_QUERY_PROMPT.format(claim_text=claim_text)
    text = _generate(prompt)
    return text.strip().strip('"').strip("'")


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
    prompt = EVIDENCE_CLAIM_EXTRACTION_PROMPT.format(claim_text=claim_text, evidence_text=evidence_text)
    return _normalize_evidence_claim(_generate(prompt))


CLAIM_EXTRACTION_PROMPT = """You are a fact-checking assistant. Read the text below and extract every \
discrete, checkable factual claim it makes (statements that could in principle be verified as true or \
false against evidence). Ignore opinions, questions, and rhetorical statements.

Respond with ONLY a JSON object of this exact shape, nothing else:
{{"claims": ["claim one", "claim two"]}}

If there are no checkable claims, respond with {{"claims": []}}.

Text:
\"\"\"
{content}
\"\"\"
"""


def extract_claims(content: str) -> list[str]:
    prompt = CLAIM_EXTRACTION_PROMPT.format(content=content)
    text = _generate(prompt, json_mode=True)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Ollama claim extraction returned invalid JSON: %r", text)
        return []

    # accept either {"claims": [...]} or a bare [...] - json_mode enforces
    # valid JSON but not which shape a 7B model picks for it
    if isinstance(parsed, dict):
        parsed = parsed.get("claims", [])
    if not isinstance(parsed, list):
        logger.warning("Ollama claim extraction returned unexpected shape: %r", parsed)
        return []

    return [str(c).strip() for c in parsed if str(c).strip()]


_VALID_VERDICT_LABELS = {"entailment", "contradiction", "neutral"}

EVIDENCE_VERIFICATION_PROMPT = """You are a fact-checking assistant. You are given a CLAIM and a numbered \
list of EVIDENCE passages found by a search engine. For each passage, decide whether it supports, refutes, \
or is unrelated to the claim's SPECIFIC assertion.

Label each passage with exactly one of:
- "entailment": the passage directly confirms the claim's specific assertion.
- "contradiction": the passage directly refutes the claim's specific assertion, OR explicitly frames it as \
false, a myth, a misconception, a hoax, or debunked - even if the passage's wording otherwise overlaps with \
the claim.
- "neutral": the passage does not address the claim's specific assertion. This includes passages that are \
topically unrelated, passages that discuss a related but different specific fact (a different person, date, \
place, or named theory than the one the claim names), and headlines phrased as unanswered questions.

Important: a passage that merely shares topic or keywords with the claim, without confirming or denying the \
claim's specific detail, is "neutral" - not "contradiction". Only use "contradiction" when the passage takes \
a clear position against the claim's specific assertion.

CLAIM: "{claim_text}"

EVIDENCE:
{evidence_block}

Respond with ONLY a JSON object of this exact shape, nothing else:
{{"verdicts": [{{"label": "entailment|contradiction|neutral", "confidence": 0.0-1.0, "relevance": 0.0-1.0}}]}}

The verdicts array must have exactly {n} entries, in the same order as the evidence passages above. \
"confidence" is how sure you are of the label. "relevance" is how relevant the passage is to the claim \
overall (0 = completely unrelated, 1 = directly on-topic), independent of which label you chose.
"""


def verify_evidence_batch(claim_text: str, evidence_texts: list[str]) -> list[dict]:
    """One Ollama call judging every evidence passage for a claim at once -
    a combined stand-in for stages 5-7 (semantic matching, reranking, NLI
    verification). Batching per claim rather than per evidence item is
    load-bearing: Ollama runs ~7-8s/call on this machine (see
    Settings.llm_backend's comment), so one call per evidence item would
    make a multi-source claim slower than the rest of the pipeline combined.

    Returns one {"label", "confidence", "relevance"} dict per input text, in
    the same order, defaulting to a "neutral"/0.0 verdict for any entry the
    model dropped or malformed rather than raising - a 7B model's JSON
    occasionally comes back short or with an off-list label.
    """
    if not evidence_texts:
        return []

    evidence_block = "\n".join(f"{i}. {text}" for i, text in enumerate(evidence_texts, start=1))
    prompt = EVIDENCE_VERIFICATION_PROMPT.format(
        claim_text=claim_text, evidence_block=evidence_block, n=len(evidence_texts)
    )
    text = _generate(prompt, json_mode=True)

    try:
        parsed = json.loads(text)
        verdicts = parsed.get("verdicts", []) if isinstance(parsed, dict) else parsed
        if not isinstance(verdicts, list):
            verdicts = []
    except json.JSONDecodeError:
        logger.warning("Ollama evidence verification returned invalid JSON: %r", text)
        verdicts = []

    results = []
    for i in range(len(evidence_texts)):
        entry = verdicts[i] if i < len(verdicts) and isinstance(verdicts[i], dict) else {}
        label = entry.get("label")
        if label not in _VALID_VERDICT_LABELS:
            if label is not None:
                logger.warning("Ollama returned invalid verdict label %r at index %d", label, i)
            label, entry = "neutral", {}
        try:
            confidence = float(entry.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        try:
            relevance = float(entry.get("relevance", 0.0))
        except (TypeError, ValueError):
            relevance = 0.0
        results.append({"label": label, "confidence": confidence, "relevance": relevance})
    return results
