export interface ExtractedEntity {
  text: string;
  label: string;
  wikidata_description: string | null;
}

export interface Claim {
  id: string;
  text: string;
  order: number;
  entities: ExtractedEntity[];
}

export type EvidenceSource =
  | "gdelt"
  | "semantic_scholar"
  | "openalex"
  | "wikipedia"
  | "crossref"
  | "google_news";

export interface RerankedEvidence {
  source: EvidenceSource;
  title: string;
  url: string;
  snippet: string;
  published_date: string | null;
  bm25_score: number;
  semantic_similarity_score: number;
  rrf_score: number;
  cross_encoder_score: number;
  representative_paragraph: string;
}

export type NLILabel = "entailment" | "contradiction" | "neutral";

export interface NLIVerdict {
  evidence: RerankedEvidence;
  label: NLILabel;
  confidence: number;
  resolved_evidence_claim: string | null;
  llm_refined: boolean;
}

export interface ClaimTrustResult {
  claim: Claim;
  trust_score: number;
  verdict_label: string;
  supporting_evidence: NLIVerdict[];
  contradicting_evidence: NLIVerdict[];
  explanation: string;
  breakdown: Record<string, unknown>;
}

export interface VerificationResponse {
  run_id: string;
  trust_score: number;
  verdict_label: string;
  explanation: string;
  claims: ClaimTrustResult[];
  created_at: string;
}

export interface VerifyErrorResponse {
  error: string;
}
