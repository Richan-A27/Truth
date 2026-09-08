from app.pipeline.stage5_semantic_matching import _ranks_from_scores, reciprocal_rank_fusion


def test_ranks_from_scores_orders_highest_first():
    assert _ranks_from_scores([0.1, 0.9, 0.5]) == [3, 1, 2]


def test_ranks_from_scores_handles_ties_stably():
    ranks = _ranks_from_scores([0.5, 0.5, 0.5])
    assert sorted(ranks) == [1, 2, 3]


def test_reciprocal_rank_fusion_rewards_agreement_between_rankers():
    # doc 0 ranks #1 in both lists; doc 1 ranks #1 in one and #3 in the
    # other - agreement should beat a single strong-but-unconfirmed signal.
    bm25_scores = [10.0, 1.0, 5.0]
    sbert_scores = [0.9, 0.95, 0.1]
    fused = reciprocal_rank_fusion(bm25_scores, sbert_scores)
    assert fused[0] > fused[1]


def test_reciprocal_rank_fusion_survives_incomparable_score_scales():
    # BM25 scores can be in the tens; cosine similarities are bounded to
    # [-1, 1] - RRF must not let the raw magnitude of one list dominate.
    bm25_scores = [1000.0, 1.0]
    sbert_scores = [0.1, 0.9]
    fused = reciprocal_rank_fusion(bm25_scores, sbert_scores)
    # doc 0 wins BM25 by a huge margin but loses SBERT; doc 1 is the
    # reverse - a rank-based fusion should treat this as roughly a tie,
    # not let doc 0's enormous raw BM25 score win outright.
    assert abs(fused[0] - fused[1]) < 0.01
