from app.core.exceptions import PipelineError

MIN_CONTENT_LENGTH = 10
MAX_CONTENT_LENGTH = 20_000


def normalize_input(content: str) -> str:
    text = content.strip()
    if len(text) < MIN_CONTENT_LENGTH:
        raise PipelineError(f"Content too short (min {MIN_CONTENT_LENGTH} chars)")
    if len(text) > MAX_CONTENT_LENGTH:
        text = text[:MAX_CONTENT_LENGTH]
    return text
