"""Second-pass resolution of ambiguous ("neutral") NLI verdicts.

Stage 7's raw-sentence NLI pass, plus its accumulated heuristics (hedge
markers, question detection, the relevance floor, asymmetric thresholds),
handles most cases well but is fundamentally pattern-matching against known
failure shapes - it can't generalize to a differently-worded ambiguous
document the way genuine language understanding could.

For documents stage 7 could not confidently classify (label="neutral") but
stage 6 judged genuinely relevant (cross_encoder_score above the same
relevance floor stage 7 uses), this asks the configured LLM to normalize
that document's text into one clean, unhedged sentence stating what it
actually asserts, then runs a fresh NLI check against just that sentence.

Deliberately not "ask an LLM if the claim is true": the LLM only produces a
normalized sentence, never a label - a dedicated NLI model still makes the
entailment/contradiction call, exactly as stage 7 does. Never raises: any
failure (LLM error, timeout, unusable output) for a given document simply
leaves that document's original verdict untouched.
"""

import asyncio
import logging

import numpy as np

from app.clients import get_llm_client
from app.config import get_settings
from app.ml.model_registry import get_nli_labels, get_nli_model, get_sbert_model
from app.pipeline.stage7_nli_verification import (
    CONTRADICTION_TRUST_THRESHOLD,
    ENTAILMENT_TRUST_THRESHOLD,
    MIN_RELEVANCE_FOR_VERDICT,
    _is_hedged,
    _softmax,
)
from app.schemas.nli import NLIVerdict

logger = logging.getLogger(__name__)

# An extracted sentence this close to the claim itself is almost certainly
# the LLM echoing the claim back rather than reporting what the evidence
# says - trivially "entails" regardless of what the evidence actually
# states, so it's treated the same as a failed extraction.
SELF_ECHO_SIMILARITY_THRESHOLD = 0.95


def _eligible_verdicts(verdicts: list[NLIVerdict], max_docs: int) -> list[NLIVerdict]:
    ambiguous = [
        v for v in verdicts if v.label == "neutral" and v.evidence.cross_encoder_score >= MIN_RELEVANCE_FOR_VERDICT
    ]
    ambiguous.sort(key=lambda v: v.evidence.cross_encoder_score, reverse=True)
    return ambiguous[:max_docs]


def _evidence_text(verdict: NLIVerdict) -> str:
    evidence = verdict.evidence
    text = f"{evidence.title}. {evidence.representative_paragraph or evidence.snippet}"
    return text[: get_settings().evidence_claim_resolution_max_chars]


async def _extract_one(claim_text: str, verdict: NLIVerdict, timeout: float) -> str:
    evidence = verdict.evidence
    evidence_text = _evidence_text(verdict)
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(get_llm_client().extract_evidence_claim, claim_text, evidence_text),
            timeout=timeout,
        )
    except Exception as exc:  # noqa: BLE001 - a failed/slow extraction must not fail the claim
        logger.warning("Evidence-claim extraction failed for %r: %s", evidence.url, exc)
        return ""


def _is_self_echo(model, claim_text: str, sentence: str) -> bool:
    embeddings = model.encode([claim_text, sentence], normalize_embeddings=True)
    similarity = float(embeddings[0] @ embeddings[1])
    return similarity >= SELF_ECHO_SIMILARITY_THRESHOLD


async def resolve_ambiguous_verdicts(
    claim_text: str, verdicts: list[NLIVerdict], nli_variant: str | None = None
) -> list[NLIVerdict]:
    if not verdicts:
        return verdicts

    settings = get_settings()
    targeted = _eligible_verdicts(verdicts, settings.evidence_claim_resolution_max_docs)
    if not targeted:
        return verdicts

    extracted = await asyncio.gather(
        *(
            _extract_one(claim_text, v, settings.evidence_claim_resolution_timeout_seconds)
            for v in targeted
        )
    )

    sbert = get_sbert_model()
    candidates: list[tuple[NLIVerdict, str]] = []
    for verdict, sentence in zip(targeted, extracted):
        if not sentence:
            continue
        if _is_self_echo(sbert, claim_text, sentence):
            logger.warning("Evidence-claim extraction for %r echoed the claim; discarding", verdict.evidence.url)
            continue
        candidates.append((verdict, sentence))

    if not candidates:
        return verdicts

    model = get_nli_model(nli_variant)
    labels = get_nli_labels(nli_variant)
    entailment_idx = labels.index("entailment")
    contradiction_idx = labels.index("contradiction")

    pairs = [(sentence, claim_text) for _, sentence in candidates]
    logits = await asyncio.to_thread(model.predict, pairs)
    probs = _softmax(np.asarray(logits))

    resolved_by_url = {}
    for (verdict, sentence), prob_row in zip(candidates, probs):
        entailment = float(prob_row[entailment_idx])
        contradiction = float(prob_row[contradiction_idx])

        # same redirect stage 7 applies to raw sentences: a hedge marker
        # means the sentence is describing a myth/misconception, not
        # asserting it, so a reading of "entailment" actually means the
        # source refutes the claim
        if entailment >= ENTAILMENT_TRUST_THRESHOLD and _is_hedged(sentence) and not _is_hedged(claim_text):
            contradiction = max(contradiction, entailment)
            entailment = 0.0

        # the source frames the topic as misinformation/myth but the LLM's
        # one-sentence rewrite dropped that framing - confirmed live: a
        # paragraph about "misinformation suggesting that COVID-19 might
        # alter DNA" came back as "mRNA vaccines introduce genetic material
        # into cells", which NLI then read as 0.98 support for the myth.
        # Not trusted as support; the first-pass verdict stands.
        if (
            entailment >= ENTAILMENT_TRUST_THRESHOLD
            and _is_hedged(_evidence_text(verdict))
            and not _is_hedged(claim_text)
        ):
            label, confidence, refined = verdict.label, verdict.confidence, False
        elif entailment >= ENTAILMENT_TRUST_THRESHOLD:
            label, confidence, refined = "entailment", entailment, True
        elif contradiction >= CONTRADICTION_TRUST_THRESHOLD:
            label, confidence, refined = "contradiction", contradiction, True
        else:
            label, confidence, refined = verdict.label, verdict.confidence, False

        resolved_by_url[verdict.evidence.url] = verdict.model_copy(
            update={
                "label": label,
                "confidence": confidence,
                "resolved_evidence_claim": sentence,
                "llm_refined": refined,
            }
        )

    return [resolved_by_url.get(v.evidence.url, v) for v in verdicts]
