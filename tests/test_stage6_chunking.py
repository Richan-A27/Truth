from app.pipeline.stage6_reranking import _best_chunk_per_document, _chunk, _dynamic_top_k


def test_chunk_splits_on_paragraph_breaks():
    text = "First paragraph about bats.\n\nSecond paragraph about echolocation.\n\nThird about vision."
    assert _chunk(text) == [
        "First paragraph about bats.",
        "Second paragraph about echolocation.",
        "Third about vision.",
    ]


def test_chunk_falls_back_to_sentences_when_no_paragraph_breaks():
    text = "Bats are mammals. Bats can see. Bats use echolocation."
    chunks = _chunk(text)
    assert len(chunks) == 3
    assert chunks[0] == "Bats are mammals."


def test_chunk_empty_text_returns_no_chunks():
    assert _chunk("") == []
    assert _chunk("   ") == []


def test_dynamic_top_k_keeps_tight_top_3_for_a_clear_winner():
    # rank 1 to rank 3 gap of 5.0, well past STRONG_WINNER_MARGIN
    assert _dynamic_top_k([9.0, 5.0, 4.0, 3.0, 2.0, 1.0]) == 3


def test_dynamic_top_k_widens_when_scores_are_bunched():
    # rank 1 to rank 3 gap of only 0.3
    scores = [5.0, 4.9, 4.7, 4.5, 4.3, 4.1, 3.9, 3.7, 3.5]
    assert _dynamic_top_k(scores) == 8


def test_dynamic_top_k_never_exceeds_available_documents():
    assert _dynamic_top_k([5.0, 4.0]) == 2


def test_dynamic_top_k_ignores_floating_point_noise_at_the_margin():
    # rank1 - rank3 = 2.0000001, a hair over STRONG_WINNER_MARGIN in raw
    # float terms but not once rounded to SCORE_PRECISION - two calls
    # carrying the same real-world relevance must not disagree on top_k
    # because of a difference this small.
    scores_a = [5.0000001, 4.5, 3.0000002, 2.0, 1.0]
    scores_b = [5.0, 4.5, 3.0, 2.0, 1.0]
    assert _dynamic_top_k(scores_a) == _dynamic_top_k(scores_b)


def test_dynamic_top_k_is_deterministic_for_identical_input():
    scores = [7.2, 6.9, 6.5, 4.0, 3.0, 2.0]
    results = {_dynamic_top_k(list(scores)) for _ in range(20)}
    assert results == {_dynamic_top_k(scores)}


def test_best_chunk_per_document_reduces_to_one_slot_per_document():
    # Document 0 contributes 3 chunks, document 1 contributes 1 - even
    # though two of document 0's chunks outscore document 1's only chunk,
    # the output must have exactly one entry per document, not per chunk.
    pairs = [
        ("claim", "doc0 paragraph 1"),
        ("claim", "doc0 paragraph 2"),
        ("claim", "doc0 paragraph 3"),
        ("claim", "doc1 paragraph 1"),
    ]
    owner_doc_index = [0, 0, 0, 1]
    scores = [3.2, 7.1, 4.0, 6.8]

    best_score, best_chunk = _best_chunk_per_document(pairs, owner_doc_index, scores, num_documents=2)

    assert len(best_score) == len(best_chunk) == 2
    assert best_score == [7.1, 6.8]
    assert best_chunk == ["doc0 paragraph 2", "doc1 paragraph 1"]


def test_best_chunk_per_document_handles_a_document_with_no_chunks():
    # a document whose text produced zero chunks (e.g. empty snippet)
    # must not crash the reduction or silently borrow another document's
    # score - it keeps -inf, sorting it firmly last rather than raising.
    pairs = [("claim", "doc1 paragraph 1")]
    owner_doc_index = [1]
    scores = [5.0]

    best_score, best_chunk = _best_chunk_per_document(pairs, owner_doc_index, scores, num_documents=2)

    assert best_score[0] == float("-inf")
    assert best_chunk[0] == ""
    assert best_score[1] == 5.0
