export const PIPELINE_STAGES = [
  {
    number: 1,
    title: "Content Input",
    description: "Raw text or a source URL comes in through the verify endpoint.",
    tech: "FastAPI",
  },
  {
    number: 2,
    title: "Claim Extraction",
    description: "Discrete, checkable claims are pulled out of the source text.",
    tech: "Gemini",
  },
  {
    number: 3,
    title: "Web Evidence Search",
    description: "Named entities anchor a search across independent evidence sources.",
    tech: "spaCy NER",
  },
  {
    number: 4,
    title: "Evidence Retrieval",
    description: "Candidate documents are scored against the claim by keyword overlap.",
    tech: "BM25",
  },
  {
    number: 5,
    title: "Semantic Matching",
    description: "Documents are embedded and matched on meaning, not just wording.",
    tech: "SBERT + FAISS",
  },
  {
    number: 6,
    title: "Evidence Re-ranking",
    description: "The strongest evidence is pushed to the top with a joint claim-evidence read.",
    tech: "Cross-Encoder",
  },
  {
    number: 7,
    title: "Claim Verification",
    description: "Each piece of evidence is judged as supporting, contradicting, or neutral.",
    tech: "DeBERTa NLI",
  },
  {
    number: 8,
    title: "Trust Scoring",
    description: "Verdicts are weighted by evidence quality into a single 0–100 score.",
    tech: "Weighted scoring",
  },
  {
    number: 9,
    title: "Result Delivery",
    description: "The score, verdict, and full explanation are returned and logged.",
    tech: "PostgreSQL",
  },
] as const;

export const TECH_STACK = [
  "FastAPI",
  "PostgreSQL",
  "Gemini",
  "spaCy",
  "SBERT",
  "FAISS",
  "Cross-Encoder",
  "DeBERTa NLI",
  "GDELT",
  "Semantic Scholar",
  "Wikipedia",
  "OpenAlex",
  "Crossref",
  "Google News",
] as const;

export const STATS = [
  { value: "<2s", label: "verification latency", detail: "down from ~19s" },
  { value: "9", label: "pipeline stages", detail: "input to explanation" },
  { value: "6", label: "evidence sources", detail: "queried independently" },
  { value: "0–100", label: "trust score", detail: "with a written explanation" },
] as const;

export const USE_CASES = [
  {
    icon: "📱",
    title: "Social media",
    scenario: "Sees a suspicious post on Instagram, Facebook, X, and the like.",
    outcome: "Truth checks the claims in it and hands back the evidence.",
  },
  {
    icon: "💬",
    title: "Forwarded messages",
    scenario: "Receives a questionable WhatsApp or Telegram forward.",
    outcome: "Truth verifies whether the information is supported or misleading.",
  },
  {
    icon: "📰",
    title: "News articles",
    scenario: "Reads an article from any news site.",
    outcome: "Truth breaks it into claims and checks each one individually.",
  },
  {
    icon: "🗳️",
    title: "Public & political claims",
    scenario: "Encounters an election, political, or government claim.",
    outcome: "Truth cross-checks it against independent, authoritative sources.",
  },
  {
    icon: "🤖",
    title: "AI-generated answers",
    scenario: "Gets an answer from an AI system.",
    outcome: "Truth checks whether the answer's claims are actually supported.",
  },
] as const;

export const EXAMPLE_CLAIMS = [
  "NASA's Perseverance rover landed on Mars in February 2021.",
  "The Eiffel Tower is located in Berlin, Germany.",
  "The human body has 206 bones in adulthood.",
] as const;
