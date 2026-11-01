"""NLI-based claim verification, and its accumulated corrections for
cross-encoder/nli-deberta-v3-base's measured biases.

Known, unresolved limitation - specific-detail mismatch treated as
contradiction: a sentence that is genuinely topically relevant but names a
different specific instance of what the claim asserts (evidence says
"special relativity" / "quantum theory", claim says "general relativity")
gets scored as confidently contradicting it, not as an unaddressed aspect.
Confirmed live: the real Wikipedia "Albert Einstein" extract scored the true
claim "Einstein developed general relativity" as 10/100 "likely_false" for
exactly this reason. It is not a hedge-marker issue (see test file: the
extract contains no hedge language) and is not fixed by restricting NLI to
the most claim-relevant sentences (TOP_SENTENCES_FOR_NLI below) - the
mismatched-detail sentences are relevant enough (0.50-0.65 SBERT similarity)
to survive that filter and still independently score >99% contradiction.
Same underlying family as the same-name-entity confusion documented in
stage8_trust_scoring.py's _entity_coverage: the model conflates "differs in
a specific detail" with "contradicts." See
tests/test_nli_hedge_detection.py::test_specific_detail_mismatch_is_not_scored_as_contradiction
for the live reproduction (xfail, kept as a regression probe rather than
deleted). Fixing this properly likely needs a better-calibrated NLI model
for fact-verification specifically, not another string-matching heuristic.
"""

import re

import numpy as np

from app.ml.model_registry import get_nli_labels, get_nli_model, get_sbert_model, get_sentencizer
from app.schemas.nli import NLIVerdict
from app.schemas.ranking import RerankedEvidence

MAX_SENTENCES_PER_DOC = 6

# Taking the max contradiction across every sentence in a document means a
# single off-topic sentence can decide the verdict: an Einstein biography
# extract scored a claim about general relativity as 100%-confidence
# contradiction because of an unrelated sentence about him enrolling in
# university - topically nowhere near relativity, but the model's
# unrelated-content bias (see MIN_RELEVANCE_FOR_VERDICT below) fired anyway.
# Restricting NLI to the sentences most semantically similar to the claim
# (via SBERT, already loaded for stage5) keeps genuinely unrelated sentences
# out of the vote entirely, rather than trusting NLI's own confidence to
# notice they're irrelevant - it doesn't reliably notice.
TOP_SENTENCES_FOR_NLI = 3


def _select_relevant_sentences(claim_text: str, sentences: list[str]) -> list[tuple[int, str]]:
    """Returns (original_index, sentence) pairs, not just sentences - the
    index is needed to look up each selected sentence's immediate
    predecessor for _with_preceding_context, and a plain value lookup
    would resolve to the wrong occurrence if the same sentence text
    appears twice in the document."""
    indexed = list(enumerate(sentences))
    if len(sentences) <= TOP_SENTENCES_FOR_NLI:
        return indexed
    model = get_sbert_model()
    claim_embedding = model.encode([claim_text], normalize_embeddings=True)[0]
    sentence_embeddings = model.encode(sentences, normalize_embeddings=True)
    similarities = sentence_embeddings @ claim_embedding
    ranked = sorted(indexed, key=lambda pair: -similarities[pair[0]])
    return ranked[:TOP_SENTENCES_FOR_NLI]


def _select_relevant_sentences_batch(
    claim_text: str, candidates_per_doc: list[list[str]]
) -> list[list[tuple[int, str]]]:
    """Same selection as _select_relevant_sentences, but with a single SBERT
    encode over every document's sentences rather than one call per document."""
    needs_ranking = [i for i, c in enumerate(candidates_per_doc) if len(c) > TOP_SENTENCES_FOR_NLI]
    selected = [list(enumerate(c)) for c in candidates_per_doc]
    if not needs_ranking:
        return selected
    model = get_sbert_model()
    flat = [s for i in needs_ranking for s in candidates_per_doc[i]]
    embeddings = model.encode([claim_text] + flat, normalize_embeddings=True, batch_size=64)
    claim_embedding, sentence_embeddings = embeddings[0], embeddings[1:]
    similarities = sentence_embeddings @ claim_embedding
    offset = 0
    for i in needs_ranking:
        n = len(candidates_per_doc[i])
        sims = similarities[offset : offset + n]
        offset += n
        ranked = sorted(enumerate(candidates_per_doc[i]), key=lambda pair: -sims[pair[0]])
        selected[i] = ranked[:TOP_SENTENCES_FOR_NLI]
    return selected


def _with_preceding_context(sentences: list[str], index: int) -> str:
    """Prepends the immediately preceding sentence, when there is one -
    restores context an anaphoric reference depends on, which plain
    per-sentence scoring throws away. Confirmed live: Wikipedia's "5G"
    article reads "Two main versions of the conspiracy theory exist: The
    first claims that radiation from 5G weakens the immune system...". In
    isolation, "The first claims that..." reads as a confident, unhedged
    assertion (scored entailment at 1.00 against a claim that 5G weakens
    the immune system); with the preceding sentence restored, the
    "conspiracy theory" framing is right there for both the NLI model and
    the existing hedge-marker check to see."""
    if index == 0:
        return sentences[index]
    return f"{sentences[index - 1]} {sentences[index]}"


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
#
# Checked per sentence, not document-wide: a biography's lead section
# routinely debunks some *other* myth about its subject in passing (e.g. the
# "Einstein failed math" legend), and a document-wide check flipped the
# correct sentence about Einstein developing relativity - genuinely
# entailing, no hedge language anywhere near it - into a contradiction
# because the word "misconception" appeared elsewhere in the same extract,
# addressing a claim about something else entirely. Scoping the check to the
# sentence that itself scores as entailment keeps the original fix (the
# hedge marker sits right there in that sentence for the myth cases) without
# that false positive.
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
    "misinformation",
    "no scientific evidence",
    # NLI reads "there is no evidence that COVID-19 vaccination causes X" as
    # entailing "COVID-19 vaccines cause X" (0.98, confirmed live on the
    # "Turbo cancer" article) - it keys on the shared words, not the negation
    "no evidence",
    "not supported by",
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


def _is_unanswered_question(sentence: str) -> bool:
    """A headline phrased as a question ("Was Albert Einstein really a bad
    student who failed math?") doesn't assert either answer - it contains
    the claim's words either way, so NLI can score it as confident
    entailment or contradiction despite the sentence itself committing to
    nothing. Most damaging with headline-only sources (Google News gives us
    no article body, just the title) where there's no surrounding text for
    the actual answer to show up in. Confirmed live: this exact headline
    scored 0.97 entailment against "Einstein failed mathematics as a
    student," dragging three confident contradictions down to "mixed" -
    the article debunks the claim, the headline alone can't say so.

    Checks for "?" anywhere in the sentence rather than requiring it as the
    final character: a Google News headline always carries a "- Source
    Name" suffix (see google_news_client.py), so the sentencizer keeps
    "... failed math? -" as one span with the question mark stranded
    mid-sentence, not at the end.
    """
    return "?" in sentence


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


# Numbers the claim and an evidence sentence share within a rounding
# tolerance. NLI models compare numbers as strings: "299,792 km/s" against a
# claim of "approximately 300,000 kilometers per second" scores as confident
# contradiction, which turned a textbook-true claim into 18/100.
_NUMBER = re.compile(r"(?<![\w.])\d{1,3}(?:,\d{3})+(?:\.\d+)?(?![\w])|(?<![\w.,])\d+(?:\.\d+)?(?![\w,])")
_APPROXIMATE = re.compile(r"\b(approximately|approx\.?|about|around|roughly|nearly|almost|some|close to|~)\b", re.IGNORECASE)
# a hedged number ("approximately 300,000") is a rounding of the true value;
# a bare one ("206 bones") is still allowed ordinary rounding slack
APPROXIMATE_NUMBER_TOLERANCE = 0.05
EXACT_NUMBER_TOLERANCE = 0.01


def _numbers(text: str) -> list[float]:
    return [float(m.replace(",", "")) for m in _NUMBER.findall(text)]


def _is_year(value: float) -> bool:
    return value.is_integer() and 1000 <= value <= 2100


def _numbers_agree(claim_text: str, sentence: str) -> bool:
    """True when every number in the claim has a close match in the sentence.

    Years must match exactly - 2% of 1889 is ±38 years, and "built in 1887"
    against a claim of 1889 is a real disagreement, not rounding. A claim
    whose only numbers are years never qualifies: date-only agreement is
    common in evidence that contradicts the claim on something else ("built
    in 1889 in Paris" vs a claim of "built in 1889 in Berlin"), whereas the
    rounding problem this exists for is about measured quantities."""
    claim_numbers = _numbers(claim_text)
    if not any(not _is_year(n) for n in claim_numbers):
        return False
    sentence_numbers = _numbers(sentence)
    tolerance = APPROXIMATE_NUMBER_TOLERANCE if _APPROXIMATE.search(claim_text) else EXACT_NUMBER_TOLERANCE
    for claimed in claim_numbers:
        if _is_year(claimed):
            if claimed not in sentence_numbers:
                return False
        elif not any(
            not _is_year(found) and abs(found - claimed) <= tolerance * abs(claimed) for found in sentence_numbers
        ):
            return False
    return True


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


def verify_claim(
    claim_text: str, documents: list[RerankedEvidence], nli_variant: str | None = None
) -> list[NLIVerdict]:
    """`nli_variant` defaults to settings.nli_model - passed explicitly only
    by the model A/B comparison script, so normal callers (the orchestrator)
    are unaffected and keep using whichever backend is configured."""
    if not documents:
        return []

    model = get_nli_model(nli_variant)
    labels = get_nli_labels(nli_variant)

    # premise = evidence sentence (plus its immediate predecessor, see
    # _with_preceding_context), hypothesis = claim: "entailment" means the
    # evidence supports the claim. Every sentence of every document is scored
    # in a single batched call for efficiency.
    pairs: list[tuple[str, str]] = []
    owner_doc_index: list[int] = []
    sentence_texts: list[str] = []
    all_candidates = [_split_sentences(f"{doc.title}. {doc.snippet}") for doc in documents]
    all_selected = _select_relevant_sentences_batch(claim_text, all_candidates)
    for doc_index, (candidates, selected) in enumerate(zip(all_candidates, all_selected)):
        for index, _ in selected:
            premise = _with_preceding_context(candidates, index)
            pairs.append((premise, claim_text))
            owner_doc_index.append(doc_index)
            sentence_texts.append(premise)

    logits = model.predict(pairs, batch_size=32)
    probs = _softmax(np.asarray(logits))

    contradiction_idx = labels.index("contradiction")
    entailment_idx = labels.index("entailment")

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
    # Tracks whether max_contradiction[doc] came from an explicit hedge
    # redirect (real textual evidence the source calls this a myth) rather
    # than a raw NLI contradiction call (the model's own, less trustworthy,
    # bias toward "contradiction" on merely-unrelated text - see below).
    hedge_redirected = [False] * len(documents)
    for i, doc_index in enumerate(owner_doc_index):
        prob_row = probs[i]
        entailment = float(prob_row[entailment_idx])
        contradiction = float(prob_row[contradiction_idx])

        # a question commits to neither answer - don't let it vote either
        # way, unlike a hedge marker (below) where the direction is known
        # and just needs redirecting
        if _is_unanswered_question(sentence_texts[i]):
            entailment = 0.0
            contradiction = 0.0
        # this specific sentence reads as entailing the claim, but it's
        # phrased as describing a myth/misconception - that's the source
        # refuting the claim, not confirming it, so redirect its vote
        # skipped when the claim itself carries the marker ("there is no
        # evidence that vaccines cause autism"): then the shared hedge is
        # agreement, not the source refuting the claim
        elif (
            entailment >= ENTAILMENT_TRUST_THRESHOLD
            and _is_hedged(sentence_texts[i])
            and not _is_hedged(claim_text)
        ):
            contradiction = max(contradiction, entailment)
            entailment = 0.0
            hedge_redirected[doc_index] = True
        # the sentence states the claim's own figures (within rounding), so
        # whatever NLI read as contradiction is string-level number mismatch
        # - "299,792" vs "300,000" - not a disagreement about the fact
        elif contradiction >= CONTRADICTION_TRUST_THRESHOLD and _numbers_agree(claim_text, sentence_texts[i]):
            contradiction = 0.0

        max_entailment[doc_index] = max(max_entailment[doc_index], entailment)
        max_contradiction[doc_index] = max(max_contradiction[doc_index], contradiction)

    verdicts = []
    for doc_index, doc in enumerate(documents):
        entailment, contradiction = max_entailment[doc_index], max_contradiction[doc_index]

        if doc.cross_encoder_score < MIN_RELEVANCE_FOR_VERDICT:
            label, confidence = "neutral", max(entailment, contradiction)
        elif hedge_redirected[doc_index] and contradiction >= CONTRADICTION_TRUST_THRESHOLD:
            # explicit hedge language beats a bare, unhedged restatement of
            # the claim elsewhere in the same document - e.g. an article
            # titled "The Moon is made of green cheese" trivially restates
            # the claim as its own title (prepended to every document's
            # text below), which would otherwise win as "entailment"
            # outright over the sentence that actually calls it a myth.
            # Confirmed live: paragraph-level reranking (stage 6) shrank
            # the sentence pool enough that this bare title-sentence, which
            # used to be crowded out by more diverse content, now reliably
            # survives into the vote.
            label, confidence = "contradiction", contradiction
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
