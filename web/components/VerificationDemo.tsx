"use client";

import { AnimatePresence, motion, useInView, useReducedMotion } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import { DEMO_SCENARIOS, type DemoVerdict } from "@/lib/constants";
import { TrustScoreGauge } from "./ui/TrustScoreGauge";

// A looping, scripted walk through one verification - claim, search,
// judgement, score - alternating a false claim with a true one, so the
// hero shows what the product does instead of describing it.

const STEPS = ["Claim", "Search", "Judge", "Score"] as const;
// ms each step stays on screen before advancing
const STEP_DURATIONS = [1700, 1800, 2600, 3200];

const VERDICT_STYLES: Record<DemoVerdict, { label: string; className: string }> = {
  supports: { label: "Supports", className: "border-success/30 bg-success/10 text-success" },
  contradicts: { label: "Contradicts", className: "border-danger/30 bg-danger/10 text-danger" },
  neutral: { label: "Off-topic", className: "border-neutral/30 bg-neutral/10 text-neutral" },
};

function highlightEntities(text: string, entities: readonly string[], active: boolean) {
  if (!active || entities.length === 0) return text;
  const pattern = new RegExp(`(${entities.map((e) => e.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`, "g");
  return text.split(pattern).map((part, i) =>
    entities.includes(part) ? (
      <motion.mark
        key={i}
        initial={{ backgroundColor: "rgba(166, 43, 63, 0)" }}
        animate={{ backgroundColor: "rgba(166, 43, 63, 0.14)" }}
        transition={{ duration: 0.4, delay: 0.1 * i }}
        className="rounded px-0.5 text-ink"
      >
        {part}
      </motion.mark>
    ) : (
      <span key={i}>{part}</span>
    )
  );
}

export function VerificationDemo() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { margin: "-60px" });
  const reduceMotion = useReducedMotion();
  const [scenarioIndex, setScenarioIndex] = useState(0);
  const [step, setStep] = useState(reduceMotion ? 3 : 0);

  useEffect(() => {
    // static final frame under reduced motion; paused while off screen
    if (reduceMotion) {
      setStep(3);
      return;
    }
    if (!inView) return;
    const timer = setTimeout(() => {
      if (step < STEPS.length - 1) {
        setStep(step + 1);
      } else {
        setScenarioIndex((i) => (i + 1) % DEMO_SCENARIOS.length);
        setStep(0);
      }
    }, STEP_DURATIONS[step]);
    return () => clearTimeout(timer);
  }, [step, inView, reduceMotion]);

  const scenario = DEMO_SCENARIOS[scenarioIndex];

  return (
    <div ref={ref} className="relative mx-auto w-full max-w-md" aria-label="Animated example of a verification">
      <div aria-hidden className="absolute -inset-6 -z-10 rounded-[2rem] bg-accent-soft/40 blur-2xl" />
      <div className="overflow-hidden rounded-2xl border border-border bg-surface shadow-soft-lg">
        {/* window chrome + step rail */}
        <div className="flex items-center justify-between border-b border-border bg-bg px-4 py-2.5">
          <div className="flex gap-1.5" aria-hidden>
            <span className="h-2.5 w-2.5 rounded-full bg-border" />
            <span className="h-2.5 w-2.5 rounded-full bg-border" />
            <span className="h-2.5 w-2.5 rounded-full bg-border" />
          </div>
          <ol className="flex items-center gap-1 text-[11px] font-medium">
            {STEPS.map((label, i) => (
              <li
                key={label}
                className={`rounded-full px-2 py-0.5 transition-colors duration-300 ${
                  i === step ? "bg-accent text-white" : i < step ? "text-accent" : "text-ink-muted"
                }`}
              >
                {label}
              </li>
            ))}
          </ol>
        </div>

        <div className="min-h-[536px] p-5">
          {/* the claim */}
          <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">Claim</p>
          <AnimatePresence mode="wait">
            <motion.p
              key={scenario.claim}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.35 }}
              className="mt-1.5 font-serif text-lg leading-snug text-ink"
            >
              &ldquo;{highlightEntities(scenario.claim, scenario.entities, step >= 1)}&rdquo;
            </motion.p>
          </AnimatePresence>

          {/* sources being searched */}
          <div className="mt-4 flex flex-wrap items-center gap-2">
            {scenario.sources.map((source, i) => (
              <motion.span
                key={`${scenarioIndex}-${source}`}
                initial={false}
                animate={{ opacity: step >= 1 ? 1 : 0.35 }}
                className="inline-flex items-center gap-1.5 rounded-full border border-border px-2.5 py-1 text-xs text-ink-muted"
              >
                <span className="relative flex h-1.5 w-1.5">
                  {step === 1 && (
                    <motion.span
                      className="absolute inline-flex h-full w-full rounded-full bg-accent"
                      animate={{ scale: [1, 2.4], opacity: [0.6, 0] }}
                      transition={{ duration: 0.9, repeat: Infinity, delay: i * 0.2 }}
                    />
                  )}
                  <span className={`relative inline-flex h-1.5 w-1.5 rounded-full ${step >= 1 ? "bg-accent" : "bg-border"}`} />
                </span>
                {source}
              </motion.span>
            ))}
            {step === 1 && (
              <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-xs text-ink-muted">
                reading ~20 documents…
              </motion.span>
            )}
          </div>

          {/* evidence, stamped with a verdict */}
          <div className="mt-4 space-y-2">
            <AnimatePresence>
              {step >= 2 &&
                scenario.evidence.map((ev, i) => (
                  <motion.div
                    key={`${scenarioIndex}-${ev.source}`}
                    initial={{ opacity: 0, x: 24 }}
                    animate={{ opacity: ev.verdict === "neutral" && step >= 3 ? 0.45 : 1, x: 0 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.4, delay: step === 2 ? i * 0.35 : 0 }}
                    className="flex items-start gap-3 rounded-xl border border-border bg-bg p-3"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="text-[10px] font-semibold uppercase tracking-wide text-ink-muted">{ev.source}</p>
                      <p className="mt-0.5 line-clamp-2 text-xs leading-relaxed text-ink">{ev.text}</p>
                    </div>
                    <motion.span
                      initial={{ opacity: 0, scale: 1.6, rotate: -8 }}
                      animate={{ opacity: 1, scale: 1, rotate: 0 }}
                      transition={{ type: "spring", stiffness: 380, damping: 18, delay: step === 2 ? i * 0.35 + 0.3 : 0 }}
                      className={`shrink-0 rounded-md border px-1.5 py-0.5 text-[10px] font-semibold uppercase ${VERDICT_STYLES[ev.verdict].className}`}
                    >
                      {VERDICT_STYLES[ev.verdict].label}
                    </motion.span>
                  </motion.div>
                ))}
            </AnimatePresence>
          </div>

          {/* the score */}
          <AnimatePresence>
            {step >= 3 && (
              <motion.div
                key={`score-${scenarioIndex}`}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.4 }}
                className="mt-4 flex items-center gap-4 border-t border-border pt-4"
              >
                <TrustScoreGauge score={scenario.score} size={64} />
                <div>
                  <p
                    className={`text-sm font-semibold ${scenario.score >= 65 ? "text-success" : scenario.score <= 35 ? "text-danger" : "text-neutral"}`}
                  >
                    {scenario.verdictLabel}
                  </p>
                  <p className="mt-0.5 text-xs leading-relaxed text-ink-muted">{scenario.summary}</p>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
