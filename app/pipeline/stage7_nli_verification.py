import re

import numpy as np

from app.ml.model_registry import NLI_LABELS, get_nli_model, get_sentencizer
from app.schemas.nli import NLIVerdict
from app.schemas.ranking import RerankedEvidence

MAX_SENTENCES_PER_DOC = 6


def _softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - logits.max(axis=1, keepdims=True)
    exp = np.exp(shifted)
    return exp / exp.sum(axis=1, keepdims=True)


_TERMINAL_PUNCTUATION = (".", "!", "?", '."', '!"', '?"')

# Phrases that mark a passage as describing a claim rather than asserting it
# (myths, misconceptions, urban legends, hoaxes). NLI models routinely read
# "the evidence contains the same words as the claim" as entailment even when
# the evidence is explicitly debunking it - e.g. an encyclopedia article
# titled "The Moon is made of green cheese" that opens with "a fanciful
# belief that..." gets scored as confirming the claim instead of refuting it.
# Checked against the whole document (title + snippet), not just the
# sentence that wins the entailment/contradiction vote: a short title like
# "The Moon is made of green cheese" is near-identical to the claim and wins
# on decisiveness alone, while the hedge marker sits in the next sentence of
# the snippet. When a hedge marker appears anywhere in the document, any
# "entailment" call from it is corrected to "contradiction" (the source is
# documenting the claim as false, which is what a source describing
# something as a myth/misconception is actually saying).
_HEDGE_MARKERS = (
    "fanciful belief",
    "false belief",
    "misconception",
    "myth",
    "folklore",
    "urban legend",
    "hoax",
    "debunked",
    "commonly misinterpreted",
    "mistakenly believed",
    "erroneously believed",
    "widely believed but false",
    "not actually true",
    "is not true",
    "in reality",
    "disproven",
    "disproved",
    "discredited",
    "refuted",
    "pseudoscien",  # pseudoscience / pseudoscientific
    "conspiracy theory",
    "no scientific evidence",
    "scientifically inaccurate",
    "archaic",
    "superseded by",
    "anti-scientific",
    "not based on scientific",
    "proponents claim",
    "believers claim",
    "unfounded",
    "widely rejected",
)


def _is_hedged(sentence: str) -> bool:
    lowered = sentence.lower()
    return any(marker in lowered for marker in _HEDGE_MARKERS)


# cross-encoder/nli-deberta-v3-base has a strong, empirically-verified bias
# toward labeling topically-unrelated sentence pairs as "contradiction"
# rather than "neutral" (confirmed on 6/6 manually-checked unrelated pairs
# during testing, e.g. "Cats are popular household pets." vs "The Eiffel
# Tower was built in 1889." -> "contradiction" at 99.6% confidence). Evidence
# that the reranker (stage 6, a different, purpose-built relevance model)
# scored as not actually relevant to the claim is therefore not trustworthy
# as either supporting or contradicting evidence - it's overridden to
# "neutral" rather than trusting the NLI label on unrelated text.
MIN_RELEVANCE_FOR_VERDICT = 0.0

# A confident entailment anywhere in a document is treated as support; a
# contradiction has to clear a higher bar because this model reaches for
# "contradiction" whenever a premise simply fails to mention the claim.
ENTAILMENT_TRUST_THRESHOLD = 0.5
CONTRADICTION_TRUST_THRESHOLD = 0.8


# Reference-list debris that search results drag in ("Archived from the
# original on March 4, 2016. Retrieved 6 March 2016.") carries no factual
# content about the claim but still gets a confident NLI label.
_CITATION_NOISE = re.compile(
    r"archived from the original|retrieved \d|\bisbn\b|\bdoi:|\bpp\.\s*\d|"
    r"^\s*(references|external links|see also|further reading)\b",
    re.IGNORECASE,
)

MIN_SENTENCE_CHARS = 25


def _is_usable_sentence(sentence: str) -> bool:
    if len(sentence) < MIN_SENTENCE_CHARS:
        return False
    return not _CITATION_NOISE.search(sentence)


def _split_sentences(text: str) -> list[str]:
    """Break a possibly multi-fact evidence passage into individual sentences.

    NLI models are unreliable on passages that pack several unrelated dates/
    facts into one premise (e.g. a Wikipedia paragraph mentioning three
    different events) - scoring sentence-by-sentence and keeping the most
    decisive result avoids that failure mode.

    Search-result snippets (Wikipedia in particular) are frequently truncated
    mid-sentence; a dangling fragment like "On May 14, 2021, China's" is
    noise that tends to get misread as contradicting evidence, so sentences
    without terminal punctuation are dropped when at least one complete
    sentence is available.
    """
    nlp = get_sentencizer()
    doc = nlp(text)
    sentences = [sent.text.strip() for sent in doc.sents if sent.text.strip()]

    usable = [s for s in sentences if _is_usable_sentence(s)]
    sentences = usable or sentences

    complete = [s for s in sentences if s.endswith(_TERMINAL_PUNCTUATION)]
    sentences = complete or sentences
    return sentences[:MAX_SENTENCES_PER_DOC] or [text]


def verify_claim(claim_text: str, documents: list[RerankedEvidence]) -> list[NLIVerdict]:
    if not documents:
        return []

    model = get_nli_model()

    # premise = evidence sentence, hypothesis = claim: "entailment" means the
    # evidence supports the claim. Every sentence of every document is scored
    # in a single batched call for efficiency.
    pairs: list[tuple[str, str]] = []
    owner_doc_index: list[int] = []
    doc_is_hedged = [_is_hedged(f"{doc.title} {doc.snippet}") for doc in documents]
    for doc_index, doc in enumerate(documents):
        for sentence in _split_sentences(f"{doc.title}. {doc.snippet}"):
            pairs.append((sentence, claim_text))
            owner_doc_index.append(doc_index)

    logits = model.predict(pairs)
    probs = _softmax(np.asarray(logits))

    contradiction_idx = NLI_LABELS.index("contradiction")
    entailment_idx = NLI_LABELS.index("entailment")

    # Track the best entailment and the best contradiction separately per
    # document rather than letting one "most decisive" sentence speak for the
    # whole page. A lead paragraph mixes the sentence that answers the claim
    # with several that don't, and the unrelated ones reliably trip the
    # model's contradiction bias - which is how a page stating "Perseverance
    # is a NASA rover that has been exploring Mars since February 18, 2021"
    # (entailment, 0.98 on its own) got recorded as contradicting the claim
    # that Perseverance landed on Mars in February 2021.
    max_entailment = [0.0] * len(documents)
    max_contradiction = [0.0] * len(documents)
    for i, doc_index in enumerate(owner_doc_index):
        prob_row = probs[i]
        max_entailment[doc_index] = max(max_entailment[doc_index], float(prob_row[entailment_idx]))
        max_contradiction[doc_index] = max(max_contradiction[doc_index], float(prob_row[contradiction_idx]))

    verdicts = []
    for doc_index, doc in enumerate(documents):
        entailment, contradiction = max_entailment[doc_index], max_contradiction[doc_index]

        if doc.cross_encoder_score < MIN_RELEVANCE_FOR_VERDICT:
            label, confidence = "neutral", max(entailment, contradiction)
        elif doc_is_hedged[doc_index] and entailment >= ENTAILMENT_TRUST_THRESHOLD:
            # source documents the claim as a myth; that refutes it
            label, confidence = "contradiction", entailment
        elif entailment >= ENTAILMENT_TRUST_THRESHOLD:
            # asymmetric on purpose: measured against unrelated sentence pairs
            # this model emits contradiction at ~0.99 but entailment at
            # ~0.001, so a confident entailment is the trustworthy signal
            label, confidence = "entailment", entailment
        elif contradiction >= CONTRADICTION_TRUST_THRESHOLD:
            label, confidence = "contradiction", contradiction
        else:
            label, confidence = "neutral", max(entailment, contradiction)

        verdicts.append(NLIVerdict(evidence=doc, label=label, confidence=confidence))
    return verdicts
