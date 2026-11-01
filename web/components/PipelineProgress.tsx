"use client";

import { motion } from "framer-motion";
import { useEffect, useState } from "react";

// The pipeline's phases, ticking along while a request is in flight. The
// backend doesn't stream progress, so this paces itself on typical stage
// timings and holds on the last step until the result arrives.
const STEPS = [
  { label: "Extracting claims", ms: 900 },
  { label: "Searching Wikipedia and Google News", ms: 2400 },
  { label: "Ranking the evidence", ms: 1500 },
  { label: "Checking each source against the claim", ms: 1800 },
  { label: "Scoring and writing the explanation", ms: Infinity },
];

export function PipelineProgress() {
  const [active, setActive] = useState(0);

  useEffect(() => {
    if (!Number.isFinite(STEPS[active].ms)) return;
    const timer = setTimeout(() => setActive((a) => a + 1), STEPS[active].ms);
    return () => clearTimeout(timer);
  }, [active]);

  return (
    <ol className="mx-auto w-full max-w-sm space-y-3" aria-live="polite">
      {STEPS.map((step, i) => {
        const done = i < active;
        const current = i === active;
        return (
          <motion.li
            key={step.label}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: i <= active ? 1 : 0.4, x: 0 }}
            transition={{ duration: 0.3, delay: i * 0.05 }}
            className="flex items-center gap-3 text-sm"
          >
            <span
              className={`relative flex h-5 w-5 shrink-0 items-center justify-center rounded-full border transition-colors duration-300 ${
                done ? "border-accent bg-accent text-white" : current ? "border-accent" : "border-border"
              }`}
            >
              {done ? (
                <motion.svg
                  viewBox="0 0 12 12"
                  className="h-3 w-3"
                  initial={{ pathLength: 0 }}
                  animate={{ pathLength: 1 }}
                  aria-hidden
                >
                  <motion.path
                    d="M2.5 6.5l2.2 2.2 4.8-5"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={1.8}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    initial={{ pathLength: 0 }}
                    animate={{ pathLength: 1 }}
                    transition={{ duration: 0.3 }}
                  />
                </motion.svg>
              ) : current ? (
                <motion.span
                  className="h-2 w-2 rounded-full bg-accent"
                  animate={{ scale: [1, 1.5, 1], opacity: [1, 0.5, 1] }}
                  transition={{ duration: 1, repeat: Infinity }}
                />
              ) : null}
            </span>
            <span className={current ? "font-medium text-ink" : done ? "text-ink" : "text-ink-muted"}>
              {step.label}
              {current && "…"}
            </span>
          </motion.li>
        );
      })}
    </ol>
  );
}
