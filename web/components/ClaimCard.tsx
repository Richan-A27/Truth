"use client";

import { useState } from "react";
import type { ClaimTrustResult, NLIVerdict } from "@/lib/types";
import { Badge } from "./ui/Badge";
import { TrustScoreGauge } from "./ui/TrustScoreGauge";

function EvidenceRow({ verdict }: { verdict: NLIVerdict }) {
  const { evidence } = verdict;
  return (
    <a
      href={evidence.url}
      target="_blank"
      rel="noopener noreferrer"
      className="block rounded-xl border border-border bg-bg p-4 transition-colors hover:bg-bg-alt"
    >
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs font-medium uppercase tracking-wide text-ink-muted">
          {evidence.source.replace(/_/g, " ")}
        </span>
        <span className="text-xs text-ink-muted">
          {Math.round(verdict.confidence * 100)}% confidence
        </span>
      </div>
      <p className="mt-1.5 text-sm font-medium text-ink line-clamp-1">{evidence.title}</p>
      <p className="mt-1 text-sm leading-relaxed text-ink-muted line-clamp-2">
        {evidence.representative_paragraph || evidence.snippet}
      </p>
    </a>
  );
}

export function ClaimCard({ result, defaultOpen = false }: { result: ClaimTrustResult; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const hasEvidence =
    result.supporting_evidence.length > 0 || result.contradicting_evidence.length > 0;

  return (
    <div className="rounded-2xl border border-border bg-surface">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-4 p-5 text-left"
      >
        <TrustScoreGauge score={result.trust_score} size={48} />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-ink">{result.claim.text}</p>
          <div className="mt-1.5">
            <Badge label={result.verdict_label} />
          </div>
        </div>
        <span className="shrink-0 text-ink-muted">{open ? "−" : "+"}</span>
      </button>

      {open && (
        <div className="border-t border-border px-5 pb-5 pt-4">
          <p className="text-sm leading-relaxed text-ink-muted">{result.explanation}</p>

          {hasEvidence && (
            <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
              {result.supporting_evidence.length > 0 && (
                <div>
                  <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-success">
                    Supporting evidence
                  </h4>
                  <div className="space-y-2">
                    {result.supporting_evidence.map((v, i) => (
                      <EvidenceRow key={i} verdict={v} />
                    ))}
                  </div>
                </div>
              )}
              {result.contradicting_evidence.length > 0 && (
                <div>
                  <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-danger">
                    Contradicting evidence
                  </h4>
                  <div className="space-y-2">
                    {result.contradicting_evidence.map((v, i) => (
                      <EvidenceRow key={i} verdict={v} />
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
