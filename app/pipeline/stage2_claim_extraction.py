from app.clients import get_llm_client
from app.schemas.claim import Claim


def extract_claims(content: str) -> list[Claim]:
    claim_texts = get_llm_client().extract_claims(content)
    return [Claim(text=text, order=i) for i, text in enumerate(claim_texts)]
