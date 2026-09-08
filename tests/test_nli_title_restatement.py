import pytest

from app.pipeline.stage7_nli_verification import verify_claim
from app.schemas.ranking import RerankedEvidence


@pytest.mark.integration
def test_hedge_redirect_beats_a_bare_title_restatement():
    """Regression test: a myth-description article's title trivially
    restates the claim ("The Moon is made of green cheese" is both the
    claim and the article's title, prepended to every document's text) -
    that bare, unhedged sentence used to win as "entailment" outright even
    when the very next sentence explicitly calls it a myth and gets
    correctly hedge-redirected to contradiction. Confirmed live: this real
    stage-6-selected chunk scored 77/likely_true before the fix."""
    evidence = RerankedEvidence(
        source="wikipedia",
        title="The Moon is made of green cheese",
        url="https://en.wikipedia.org/wiki/The_Moon_is_made_of_green_cheese",
        snippet=(
            'The Moon is made of green cheese. "The Moon is made of green cheese" is a statement '
            "referring to a fanciful belief that the Moon is composed of cheese."
        ),
        cross_encoder_score=10.73,
    )
    verdicts = verify_claim("The Moon is made of green cheese.", [evidence])
    assert verdicts[0].label == "contradiction"
