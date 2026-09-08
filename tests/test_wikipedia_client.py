import pytest

from app.clients.wikipedia_client import _paragraphs_excluding_boilerplate, _select_relevant_paragraphs


def test_paragraphs_excluding_boilerplate_drops_reference_sections():
    full_text = (
        "Bats are winged mammals.\n"
        "== Etymology ==\n"
        "The name comes from an old word for flying mice.\n"
        "== References ==\n"
        "Smith, J. (2001). A study of bats.\n"
        "== External links ==\n"
        "Bat Conservation International website.\n"
    )
    paragraphs = _paragraphs_excluding_boilerplate(full_text)
    assert paragraphs == ["Bats are winged mammals.", "The name comes from an old word for flying mice."]


def test_select_relevant_paragraphs_prefers_higher_keyword_overlap():
    paragraphs = [
        "The Eiffel Tower is a wrought-iron lattice tower in Paris.",
        "Bats use echolocation to navigate and hunt for insects in complete darkness.",
        "Many species of bats have excellent vision and are not blind.",
    ]
    selected = _select_relevant_paragraphs(paragraphs, {"bat", "blind", "vision"}, max_chars=1000)
    assert selected[0] == "Many species of bats have excellent vision and are not blind."


def test_select_relevant_paragraphs_drops_non_matching_text():
    paragraphs = ["The Eiffel Tower is a wrought-iron lattice tower in Paris."]
    assert _select_relevant_paragraphs(paragraphs, {"bat", "echolocation"}, max_chars=1000) == []


def test_select_relevant_paragraphs_respects_char_budget():
    paragraphs = ["bat " * 100, "bat " * 100, "bat " * 100]
    selected = _select_relevant_paragraphs(paragraphs, {"bat"}, max_chars=250)
    assert len(selected) == 1


def test_select_relevant_paragraphs_pulls_in_a_colon_ending_predecessor():
    """Regression test: the real Wikipedia "5G" article, verbatim. "Two
    main versions of the conspiracy theory exist:" shares no vocabulary
    with a query about 5G/immune systems and would never be selected on
    its own - but without it, the next paragraph reads as a confident,
    unhedged assertion rather than a conspiracy theory being described.

    Merged into ONE returned string (not two adjacent list entries): the
    caller rejoins the list with "\\n\\n", and stage 6's paragraph-level
    reranking scores each "\\n\\n" chunk independently, keeping only the
    single best-scoring one - two separate entries would let stage 6 split
    this exact pairing back apart and discard the context one stage later.
    """
    paragraphs = [
        "During the early months of the pandemic, Australian anti-lockdown protesters carried anti-5G signs.",
        "Two main versions of the conspiracy theory exist:",
        "The first claims that radiation from 5G weakens the immune system, making people more vulnerable "
        "to SARS-CoV-2, the virus that causes COVID-19.",
        "The second claims that 5G causes COVID-19.",
    ]
    selected = _select_relevant_paragraphs(paragraphs, {"5g", "immun", "system"}, max_chars=1000)
    assert (
        "Two main versions of the conspiracy theory exist: The first claims that radiation from 5G weakens "
        "the immune system, making people more vulnerable to SARS-CoV-2, the virus that causes COVID-19."
    ) in selected
    # never split across two separate entries - a colon-predecessor merged
    # with its target must survive as one atomic chunk
    assert "Two main versions of the conspiracy theory exist:" not in selected


def test_select_relevant_paragraphs_does_not_pull_in_a_non_colon_predecessor():
    paragraphs = [
        "The Eiffel Tower is a wrought-iron lattice tower in Paris, unrelated to the topic below.",
        "Bats have functional eyesight and are not blind.",
    ]
    selected = _select_relevant_paragraphs(paragraphs, {"bat", "blind"}, max_chars=1000)
    assert selected == ["Bats have functional eyesight and are not blind."]


@pytest.mark.integration
async def test_deep_fetch_surfaces_content_the_lead_and_snippet_both_miss():
    """A claim about bat vision/blindness pulls in "Yuma myotis" and similar
    species articles via search, but the fact that lives on the main "Bat"
    page - that most bats are not actually blind - sits in the Anatomy
    section, well past both the ~500-char intro and any single search-match
    snippet. Only the deep-fetch pass reaches it."""
    from app.clients.wikipedia_client import search

    docs = await search("are bats blind vision eyesight", limit=5)
    bat_doc = next((d for d in docs if d.title.lower() == "bat"), None)
    assert bat_doc is not None
    assert "vision" in bat_doc.snippet.lower() or "eyesight" in bat_doc.snippet.lower() or "blind" in bat_doc.snippet.lower()


@pytest.mark.integration
async def test_search_snippet_surfaces_content_beyond_the_lead_section():
    """The regression this exists for: "Bats are completely blind" scored
    unverified because the "Bat" article's ~1200-char lead never mentions
    echolocation or vision (both live in a later section, per the real
    article's ~50KB length) - the full-text search index does cover those
    sections, and gsrprop=snippet surfaces a match from wherever the claim's
    keywords actually appear, not just the intro."""
    from app.clients.wikipedia_client import search

    docs = await search("bats blind echolocation", limit=5)
    assert any("echolocation" in d.snippet.lower() or "echolocat" in d.snippet.lower() for d in docs)


@pytest.mark.integration
async def test_disambiguation_pages_still_excluded_with_snippet_enabled():
    from app.clients.wikipedia_client import search

    docs = await search("Mercury", limit=5)
    assert not any("(disambiguation)" in d.title.lower() for d in docs)
