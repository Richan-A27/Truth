export const PIPELINE_STAGES = [
  {
    number: 1,
    title: "Content Input",
    description: "Raw text or a source URL comes in through the verify endpoint.",
    tech: "FastAPI",
    metric: "any text",
  },
  {
    number: 2,
    title: "Claim Extraction",
    description: "Discrete, self-contained claims are pulled out of the source text.",
    tech: "LLM (Groq)",
    metric: "1 text → N claims",
  },
  {
    number: 3,
    title: "Web Evidence Search",
    description: "Named entities and the claim's subject anchor searches across Wikipedia and Google News.",
    tech: "spaCy NER",
    metric: "~20 documents",
  },
  {
    number: 4,
    title: "Evidence Retrieval",
    description: "Candidate documents are scored against the claim by keyword overlap.",
    tech: "BM25",
    metric: "keyword-scored",
  },
  {
    number: 5,
    title: "Semantic Matching",
    description: "Documents are embedded and matched on meaning, not just wording.",
    tech: "SBERT + FAISS",
    metric: "meaning-scored",
  },
  {
    number: 6,
    title: "Evidence Re-ranking",
    description: "The strongest evidence is pushed to the top with a joint claim-evidence read.",
    tech: "Cross-Encoder",
    metric: "top 3–8 kept",
  },
  {
    number: 7,
    title: "Claim Verification",
    description: "Each piece of evidence is judged as supporting, contradicting, or neutral — myths and hedges included.",
    tech: "DeBERTa NLI",
    metric: "3 sentences per doc",
  },
  {
    number: 8,
    title: "Trust Scoring",
    description: "Verdicts are weighted by evidence quality into a single 0–100 score.",
    tech: "Weighted scoring",
    metric: "→ 0–100",
  },
  {
    number: 9,
    title: "Result Delivery",
    description: "The score, verdict, and full explanation are returned and logged.",
    tech: "PostgreSQL",
    metric: "+ explanation",
  },
] as const;

export const TECH_STACK = [
  "FastAPI",
  "PostgreSQL",
  "Groq LLM",
  "spaCy",
  "SBERT",
  "FAISS",
  "Cross-Encoder",
  "DeBERTa NLI",
  "Wikipedia",
  "Wikidata",
  "Google News",
] as const;

// `value` counts up on scroll when numeric. Accuracy is from live runs of the
// labelled eval sets in scripts/eval_claims*.json.
export const STATS = [
  { value: 9, suffix: "", label: "pipeline stages", detail: "input to explanation" },
  { value: 20, suffix: "+", label: "documents read", detail: "per claim, before ranking" },
  { value: 91, suffix: "%", label: "eval accuracy", detail: "62 of 68 labelled claims" },
  { value: "0–100", suffix: "", label: "trust score", detail: "with a written explanation" },
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

export type DemoVerdict = "supports" | "contradicts" | "neutral";

// Scripted examples for the hero animation - modelled on real pipeline runs
// of these claims, simplified for display.
export const DEMO_SCENARIOS: readonly {
  claim: string;
  entities: readonly string[];
  sources: readonly string[];
  evidence: readonly { source: string; text: string; verdict: DemoVerdict }[];
  score: number;
  verdictLabel: string;
  summary: string;
}[] = [
  {
    claim: "The Eiffel Tower is located in Berlin, Germany.",
    entities: ["Eiffel Tower", "Berlin", "Germany"],
    sources: ["Wikipedia", "Google News", "Wikidata"],
    evidence: [
      {
        source: "Wikipedia · Eiffel Tower",
        text: "The Eiffel Tower is a wrought-iron lattice tower on the Champ de Mars in Paris, France.",
        verdict: "contradicts",
      },
      {
        source: "Google News",
        text: "Paris's Eiffel Tower welcomes record visitors this summer.",
        verdict: "contradicts",
      },
      {
        source: "Wikipedia · Berlin TV Tower",
        text: "The Fernsehturm is a television tower in central Berlin, Germany.",
        verdict: "neutral",
      },
    ],
    score: 3,
    verdictLabel: "Likely false",
    summary: "Every relevant source places the tower in Paris.",
  },
  {
    claim: "NASA's Perseverance rover landed on Mars in February 2021.",
    entities: ["NASA", "Perseverance", "Mars", "February 2021"],
    sources: ["Wikipedia", "Google News", "Wikidata"],
    evidence: [
      {
        source: "Wikipedia · Perseverance (rover)",
        text: "Perseverance landed in Jezero crater on Mars on 18 February 2021.",
        verdict: "supports",
      },
      {
        source: "Google News",
        text: "Four years after touchdown, Perseverance is still exploring Jezero crater.",
        verdict: "supports",
      },
      {
        source: "Wikipedia · Mars 2020",
        text: "The Mars 2020 mission launched from Cape Canaveral on 30 July 2020.",
        verdict: "neutral",
      },
    ],
    score: 90,
    verdictLabel: "Likely true",
    summary: "Independent sources agree on the landing date.",
  },
];
