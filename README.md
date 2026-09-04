# Truth — AI Misinformation Verification Backend

Backend + AI pipeline for automated, explainable fact-checking. Takes raw
text, extracts checkable claims, gathers evidence from GDELT (news),
Semantic Scholar (academic), and Wikipedia (reference), then verifies each
claim with a retrieval → re-ranking → NLI pipeline and produces a 0-100
Trust Score with a natural-language explanation.

## Pipeline

1. **Content Input** — raw text via `POST /verify`
2. **Claim Extraction** — Gemini LLM
3. **Web Evidence Search** — spaCy NER + GDELT / Semantic Scholar / Wikipedia
4. **Evidence Retrieval** — BM25
5. **Semantic Matching** — SBERT + FAISS
6. **Evidence Re-ranking** — Cross-Encoder
7. **Claim Verification** — DeBERTa NLI (entailment/contradiction/neutral)
8. **Trust Scoring** — custom weighted algorithm
9. **Result Delivery** — FastAPI JSON response, logged to PostgreSQL

## Setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
# edit .env and set GEMINI_API_KEY

./scripts/init_db.sh          # creates truth_db/truth_user, runs migrations
python scripts/download_models.py   # pre-fetches spaCy/SBERT/CrossEncoder/NLI models
```

## Run

```bash
source .venv/bin/activate
uvicorn app.main:app --reload
```

## Try it

```bash
curl http://localhost:8000/health

curl -X POST http://localhost:8000/verify \
  -H "Content-Type: application/json" \
  -d '{"content": "The Eiffel Tower is located in Berlin, Germany."}'

curl -X POST http://localhost:8000/verify \
  -H "Content-Type: application/json" \
  -d '{"content": "NASA'\''s Perseverance rover landed on Mars in February 2021."}'

curl http://localhost:8000/verify/<run_id>
```

## Tests

```bash
pytest -m "not integration"   # fast, mocked, CI-safe
pytest -m integration         # needs real models/network/GEMINI_API_KEY
```
