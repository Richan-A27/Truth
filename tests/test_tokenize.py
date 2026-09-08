from app.core.tokenize import stem_tokenize


def test_stems_inflected_forms_to_match():
    """Without stemming, "vaccines" (claim) and "vaccine"/"vaccinated"
    (evidence) are unrelated tokens - exactly the mismatch behind why
    evidence titled "Vaccine misinformation" scored weakly against a claim
    about "vaccines"."""
    assert stem_tokenize("vaccines") == stem_tokenize("vaccine")
    assert stem_tokenize("vaccinated") == stem_tokenize("vaccine")
    assert stem_tokenize("contradiction") == stem_tokenize("contradicting")


def test_does_not_over_stem_short_words():
    """A naive suffix-stripper would wrongly conflate "gas"/"ga" or
    "was"/"wa" - this is why a real stemmer library is used instead of a
    hand-rolled one."""
    assert stem_tokenize("gas") == ["gas"]
    assert stem_tokenize("was") == ["was"]
