"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";
import type { ClaimTrustResult, NLIVerdict } from "@/lib/types";
import { Badge } from "./ui/Badge";
import { TrustScoreGauge } from "./ui/TrustScoreGauge";

function EvidenceRow({ verdict, index }: { verdict: NLIVerdict; index: number }) {
  const { evidence } = verdict;
  return (
    <motion.a
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: 0.1 + index * 0.07 }}
      href={evidence.url}
      target="_blank"
      rel="noopener noreferrer"
      className="block rounded-xl border border-border bg-bg p-4 transition-colors hover:bg-bg-alt"
    >
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs font-medium uppercase tracking-wide text-ink-muted">
          {evidence.source.replace(/_/g, " ")}
        </span>
        <span className="text-xs text-ink-muted">{Math.round(verdict.confidence * 100)}% confidence</span>
      </div>
      {/* confidence as a thin bar under the header */}
      <div className="mt-2 h-0.5 w-full overflow-hidden rounded bg-border">
        <motion.div
          className={`h-full ${verdict.label === "entailment" ? "bg-success" : verdict.label === "contradiction" ? "bg-danger" : "bg-neutral"}`}
          initial={{ width: 0 }}
          animate={{ width: `${Math.round(verdict.confidence * 100)}%` }}
          transition={{ duration: 0.7, delay: 0.2 + index * 0.07, ease: "easeOut" }}
        />
      </div>
      <p className="mt-2 line-clamp-1 text-sm font-medium text-ink">{evidence.title}</p>
      <p className="mt-1 line-clamp-2 text-sm leading-relaxed text-ink-muted">
        {evidence.representative_paragraph || evidence.snippet}
      </p>
    </motion.a>
  );
}

// Supporting vs contradicting vs off-topic, as one proportional bar - the
// shape of the evidence at a glance, before reading any of it.
function EvidenceBalance({ result }: { result: ClaimTrustResult }) {
  const supporting = result.supporting_evidence.length;
  const contradicting = result.contradicting_evidence.length;
  const neutral = Number(result.breakdown?.neutral_count ?? 0);
  const total = supporting + contradicting + neutral;
  if (total === 0) return null;
  const segments = [
    { count: supporting, className: "bg-success", label: "supporting" },
    { count: contradicting, className: "bg-danger", label: "contradicting" },
    { count: neutral, className: "bg-neutral/40", label: "off-topic" },
  ];

  return (
    <div className="mt-4">
      <div className="flex h-2 w-full overflow-hidden rounded-full bg-border">
        {segments.map((s, i) =>
          s.count > 0 ? (
            <motion.div
              key={s.label}
              className={s.className}
              initial={{ width: 0 }}
              animate={{ width: `${(s.count / total) * 100}%` }}
              transition={{ duration: 0.6, delay: 0.1 + i * 0.1, ease: "easeOut" }}
            />
          ) : null
        )}
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-muted">
        {segments.map((s) => (
          <span key={s.label} className="inline-flex items-center gap-1.5">
            <span className={`h-2 w-2 rounded-full ${s.className}`} />
            {s.count} {s.label}
          </span>
        ))}
      </div>
    </div>
  );
}

export function ClaimCard({ result, defaultOpen = false }: { result: ClaimTrustResult; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const hasEvidence = result.supporting_evidence.length > 0 || result.contradicting_evidence.length > 0;

  return (
    <div className="rounded-2xl border border-border bg-surface transition-shadow hover:shadow-soft">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center gap-4 p-5 text-left"
      >
        <TrustScoreGauge score={result.trust_score} size={48} />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-ink">{result.claim.text}</p>
          <div className="mt-1.5">
            <Badge label={result.verdict_label} />
          </div>
        </div>
        <motion.span animate={{ rotate: open ? 45 : 0 }} className="shrink-0 text-lg leading-none text-ink-muted">
          +
        </motion.span>
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease: "easeOut" }}
            className="overflow-hidden"
          >
            <div className="border-t border-border px-5 pb-5 pt-4">
              <p className="text-sm leading-relaxed text-ink-muted">{result.explanation}</p>
              <EvidenceBalance result={result} />

              {hasEvidence && (
                <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2">
                  {result.supporting_evidence.length > 0 && (
                    <div>
                      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-success">
                        Supporting evidence
                      </h4>
                      <div className="space-y-2">
                        {result.supporting_evidence.map((v, i) => (
                          <EvidenceRow key={i} verdict={v} index={i} />
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
                          <EvidenceRow key={i} verdict={v} index={i} />
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
