from app.schemas.evidence import RetrievedEvidence


class RankedEvidence(RetrievedEvidence):
    semantic_similarity_score: float = 0.0
    rrf_score: float = 0.0


class RerankedEvidence(RankedEvidence):
    cross_encoder_score: float = 0.0
    # The single best-scoring paragraph/sentence found within this
    # document's text - additive, not a replacement for `snippet` (which
    # every existing reader, stage 7 included, keeps seeing unchanged).
    representative_paragraph: str = ""
