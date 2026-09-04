from app.clients import gemini_client
from app.schemas.claim import Claim


def extract_claims(content: str) -> list[Claim]:
    claim_texts = gemini_client.extract_claims(content)
    return [Claim(text=text, order=i) for i, text in enumerate(claim_texts)]
