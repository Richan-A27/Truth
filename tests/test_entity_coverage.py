from app.pipeline.stage8_trust_scoring import _entity_coverage, score_claim
from app.schemas.claim import Claim, ExtractedEntity
from app.schemas.nli import NLIVerdict
from app.schemas.ranking import RerankedEvidence


def _claim_with_entities(text: str, entities: list[tuple[str, str]]) -> Claim:
    return Claim(text=text, order=0, entities=[ExtractedEntity(text=t, label=l) for t, l in entities])


EIFFEL_CLAIM = _claim_with_entities(
    "The Eiffel Tower is located in Paris, France.",
    [("The Eiffel Tower", "FAC"), ("Paris", "GPE"), ("France", "GPE")],
)


def test_full_coverage_when_all_entities_present():
    text = "The Eiffel Tower is a lattice tower on the Champ de Mars in Paris, France."
    assert _entity_coverage(EIFFEL_CLAIM, text) == 1.0


def test_partial_coverage_for_same_name_different_place():
    text = "Texas's Eiffel Tower is a landmark in the city of Paris, Texas."
    assert _entity_coverage(EIFFEL_CLAIM, text) < 1.0


def test_multi_token_entity_requires_all_tokens():
    claim = _claim_with_entities("x", [("February 2021", "DATE")])
    assert _entity_coverage(claim, "landed on February 18, 2021 successfully") == 1.0
    assert _entity_coverage(claim, "landed in February 2019") == 0.0


def test_claim_without_entities_is_not_penalised():
    claim = Claim(text="Water boils at 100 degrees.", order=0, entities=[])
    assert _entity_coverage(claim, "anything at all") == 1.0


def _verdict(label: str, title: str, snippet: str, ce: float) -> NLIVerdict:
    evidence = RerankedEvidence(
        source="wikipedia", title=title, url=f"https://example.com/{title}", snippet=snippet, cross_encoder_score=ce
    )
    return NLIVerdict(evidence=evidence, label=label, confidence=0.99)


def test_on_topic_support_outweighs_same_name_distractors():
    """Reproduces the observed failure: the real Eiffel Tower page supported
    the claim while a Texas replica and a Las Vegas casino contradicted it,
    dragging a true claim down to 'mixed'."""
    verdicts = [
        _verdict(
            "entailment",
            "Eiffel Tower",
            "The Eiffel Tower is a lattice tower on the Champ de Mars in Paris, France.",
            10.36,
        ),
        _verdict(
            "contradiction",
            "Eiffel Tower (Paris, Texas)",
            "Texas's Eiffel Tower is a landmark in the city of Paris, Texas. The tower was constructed in 1993.",
            9.63,
        ),
        _verdict(
            "contradiction",
            "Paris Las Vegas",
            "Paris Las Vegas is a casino hotel on the Las Vegas Strip in Paradise, Nevada.",
            2.34,
        ),
    ]

    result = score_claim(EIFFEL_CLAIM, verdicts)
    assert result.trust_score > 50, f"expected net-positive score, got {result.trust_score}"
