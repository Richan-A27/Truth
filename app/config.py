from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"

    # "gemini" (cloud, fast, 20 req/day free tier), "groq" (cloud, fast), or "ollama" (local,
    # slow ~7-8s/call on this machine, no quota). Affects claim extraction,
    # explanation, and stage 7b's evidence-claim resolution (see
    # evidence_claim_resolution_enabled below) - the last of these can issue
    # up to evidence_claim_resolution_max_docs calls per claim, making it
    # the highest-volume of the three; a claim-heavy run on "gemini" can
    # exhaust the free tier in just 2-3 verifications.
    llm_backend: str = "gemini"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_timeout_seconds: float = 60.0

    # llm_backend="groq": hosted open-weights models, fast and with generous
    # free-tier limits. gpt-oss-20b: fast, strong at instruction-following.
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-20b"
    groq_timeout_seconds: float = 20.0

    # "current" (generic cross-encoder/nli-deberta-v3-base) or
    # "fact_verification" (same architecture/size class, fine-tuned on
    # MNLI+FEVER+ANLI - see app.ml.model_registry.NLI_MODEL_VARIANTS).
    # Everything else in stage 7 - batching, sentence selection, relevance
    # floor, hedge detection, thresholds - stays identical between the two,
    # so this isolates the effect of the model itself.
    nli_model: str = "current"

    # Stage 7b: for evidence stage 7 scored "neutral" on a document stage 6
    # already judged relevant (not evidence dismissed as off-topic), ask
    # the configured LLM (llm_backend above) to normalize that document's
    # text into one clean, unhedged sentence and re-run NLI against just
    # that sentence - a second, less-ambiguous chance at a confident label.
    # On by default; kept togglable as a fast rollback path, same as every
    # other pipeline knob here.
    evidence_claim_resolution_enabled: bool = True
    # Per-claim cap on how many first-pass-neutral, relevance-passing
    # documents get an LLM call, taken in descending cross_encoder_score
    # order - stage 6 can retain up to 8 documents, and Ollama's ~7-8s/call
    # latency makes resolving all of them per claim impractical.
    # Lowered from 3 to 1: on Groq's free tier (200k tokens/day for
    # gpt-oss-20b) three rewrites per claim exhausted the daily quota within
    # a few eval runs, after which 7b silently stopped contributing.
    evidence_claim_resolution_max_docs: int = 1
    # Evidence text sent per rewrite is capped to this many characters - the
    # reranker's best paragraph is already the relevant part, and the prompt
    # is billed per token.
    evidence_claim_resolution_max_chars: int = 500
    evidence_claim_resolution_timeout_seconds: float = 20.0

    database_url: str = "postgresql+asyncpg://truth_user:truth_pass@localhost:5432/truth_db"

    semantic_scholar_api_key: str = ""

    # Contact info sent to free APIs that reward identified requests with
    # higher rate limits ("polite pool"). Not secrets - an email or URL.
    wikipedia_contact: str = ""
    openalex_mailto: str = ""
    crossref_mailto: str = ""

    # Per-source ceilings, all bounded by evidence_deadline_seconds: whatever
    # has not answered by the deadline is cancelled and the verdict is formed
    # from the sources that did. Confirmed via a diagnostic run with these
    # temporarily raised to 30s: GDELT's failures are genuine ConnectTimeouts
    # and Semantic Scholar's are genuine 429s returned in <0.5s, not premature
    # cutoffs - raising these further doesn't help, it just waits longer for
    # the same rejection.
    gdelt_timeout_seconds: float = 2.5
    semantic_scholar_timeout_seconds: float = 2.5
    wikipedia_timeout_seconds: float = 2.5
    openalex_timeout_seconds: float = 2.5
    crossref_timeout_seconds: float = 2.5
    google_news_timeout_seconds: float = 2.5
    # Entity resolution runs concurrently with evidence retrieval (stage8
    # needs it, stages 3-7 don't), so a slow/failed lookup adds no latency of
    # its own as long as it fits inside that window.
    wikidata_timeout_seconds: float = 2.0
    # Hard cap while no source has answered yet; once one has, the others get
    # only evidence_grace_seconds before they are abandoned.
    evidence_deadline_seconds: float = 2.5
    evidence_grace_seconds: float = 0.25

    app_env: str = "development"
    log_level: str = "INFO"

    # Comma-separated list of origins allowed to call this API cross-origin
    # (e.g. the web/ Next.js app in local dev). Plain str field, split at use
    # time, to sidestep pydantic-settings' list-env-var parsing.
    cors_allow_origins_raw: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
