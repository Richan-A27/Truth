"use client";

import { motion, useInView, useReducedMotion } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import { TrustScoreGauge } from "./ui/TrustScoreGauge";

// 20 documents in -> 8 survive ranking -> each judged -> one score out.
// The same narrowing every claim goes through, played once on scroll.

const TOTAL_DOCS = 20;
// which of the 20 survive reranking, and how NLI then judges them
const KEPT: Record<number, "supports" | "contradicts" | "neutral"> = {
  1: "contradicts",
  4: "contradicts",
  6: "neutral",
  9: "contradicts",
  12: "contradicts",
  13: "neutral",
  17: "contradicts",
  19: "neutral",
};

const PHASES = [
  { title: "Gather", caption: "~20 documents from Wikipedia and Google News" },
  { title: "Rank", caption: "BM25, embeddings and a cross-encoder keep the best 3–8" },
  { title: "Judge", caption: "NLI labels each one: supports, contradicts, or off-topic" },
  { title: "Score", caption: "Weighted into one 0–100 trust score" },
];

const DOC_COLORS = {
  supports: "bg-success",
  contradicts: "bg-danger",
  neutral: "bg-neutral/50",
};

const DOC_BORDERS = {
  supports: "border-success/50",
  contradicts: "border-danger/50",
  neutral: "border-border",
};

export function EvidenceFunnel() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-120px" });
  const reduceMotion = useReducedMotion();
  const [phase, setPhase] = useState(-1);

  useEffect(() => {
    if (!inView) return;
    if (reduceMotion) {
      setPhase(3);
      return;
    }
    setPhase(0);
    const timers = [1, 2, 3].map((p) => setTimeout(() => setPhase(p), p * 1300));
    return () => timers.forEach(clearTimeout);
  }, [inView, reduceMotion]);

  return (
    <div ref={ref} className="mx-auto mt-14 max-w-4xl rounded-2xl border border-border bg-surface p-6 shadow-soft sm:p-8">
      <div className="grid grid-cols-1 items-center gap-8 md:grid-cols-[1fr_auto]">
        <div className="mx-auto grid w-full max-w-xl grid-cols-10 gap-1.5 sm:gap-2" aria-hidden>
          {Array.from({ length: TOTAL_DOCS }, (_, i) => {
            const verdict = KEPT[i];
            const kept = verdict !== undefined;
            const dimmed = phase >= 1 && !kept;
            return (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 12 }}
                animate={{
                  opacity: phase < 0 ? 0 : dimmed ? 0.25 : 1,
                  y: phase < 0 ? 12 : 0,
                  scale: phase >= 1 && kept ? 1.08 : 1,
                }}
                transition={{ duration: 0.4, delay: phase === 0 ? i * 0.03 : 0 }}
                className={`relative aspect-[3/4] rounded-md border bg-bg transition-colors duration-500 ${
                  phase >= 2 && kept ? DOC_BORDERS[verdict] : "border-border"
                }`}
              >
                {/* text lines on the little document */}
                <div className="absolute inset-x-1.5 top-2 space-y-1">
                  <div className="h-0.5 rounded bg-border" />
                  <div className="h-0.5 w-3/4 rounded bg-border" />
                  <div className="h-0.5 rounded bg-border" />
                </div>
                {kept && (
                  <motion.span
                    initial={false}
                    animate={{ scale: phase >= 2 ? 1 : 0 }}
                    transition={{ type: "spring", stiffness: 400, damping: 20, delay: phase === 2 ? (i % 7) * 0.06 : 0 }}
                    className={`absolute bottom-1 right-1 h-2.5 w-2.5 rounded-full ${DOC_COLORS[verdict]}`}
                  />
                )}
              </motion.div>
            );
          })}
        </div>

        <div className="flex items-center justify-center gap-4 md:flex-col">
          <motion.span
            animate={{ opacity: phase >= 3 ? 1 : 0.2 }}
            className="text-2xl text-ink-muted md:rotate-0"
            aria-hidden
          >
            →
          </motion.span>
          <div className={`transition-opacity duration-500 ${phase >= 3 ? "" : "opacity-30"}`}>
            <TrustScoreGauge score={phase >= 3 ? 12 : 0} size={88} />
          </div>
        </div>
      </div>

      <ol className="mt-8 grid grid-cols-2 gap-4 border-t border-border pt-6 sm:grid-cols-4">
        {PHASES.map((p, i) => (
          <li key={p.title} className={`transition-opacity duration-500 ${phase >= i ? "opacity-100" : "opacity-35"}`}>
            <p className="flex items-center gap-2 text-sm font-medium text-ink">
              <span
                className={`flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-semibold transition-colors duration-500 ${
                  phase >= i ? "bg-accent text-white" : "bg-bg-alt text-ink-muted"
                }`}
              >
                {i + 1}
              </span>
              {p.title}
            </p>
            <p className="mt-1 text-xs leading-relaxed text-ink-muted">{p.caption}</p>
          </li>
        ))}
      </ol>

      <div className="mt-5 flex flex-wrap gap-4 text-xs text-ink-muted">
        <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-success" />supports</span>
        <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-danger" />contradicts</span>
        <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-neutral/50" />off-topic</span>
      </div>
    </div>
  );
}
