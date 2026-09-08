from types import ModuleType

from app.config import get_settings


def get_llm_client() -> ModuleType:
    """The configured claim-extraction/explanation backend.

    Both gemini_client and ollama_client expose the same two functions
    (extract_claims, generate_explanation), so callers don't need to care
    which one they get.
    """
    from app.clients import gemini_client, ollama_client

    return ollama_client if get_settings().llm_backend == "ollama" else gemini_client
