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


def test_stem_tokenize_is_safe_across_threads():
    from concurrent.futures import ThreadPoolExecutor

    from app.core.tokenize import stem_tokenize

    text = "Perseverance deployed the experimental helicopter Ingenuity, performing controlled flights " * 40
    expected = stem_tokenize(text)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: stem_tokenize(text), range(64)))
    assert all(r == expected for r in results)
