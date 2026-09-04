from app.schemas.evidence import RetrievedEvidence


class RankedEvidence(RetrievedEvidence):
    semantic_similarity_score: float = 0.0


class RerankedEvidence(RankedEvidence):
    cross_encoder_score: float = 0.0
