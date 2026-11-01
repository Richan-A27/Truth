"use client";

import { motion, useScroll, useSpring } from "framer-motion";
import { useRef } from "react";
import { PIPELINE_STAGES } from "@/lib/constants";
import { EvidenceFunnel } from "./EvidenceFunnel";
import { PipelineStage } from "./PipelineStage";
import { Reveal } from "./ui/Reveal";

// Stage numbers where a new phase of the pipeline begins.
const PHASE_LABELS: Record<number, string> = {
  1: "Understand",
  3: "Gather",
  4: "Rank",
  7: "Judge",
  9: "Deliver",
};

export function HowItWorks() {
  const timelineRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: timelineRef, offset: ["start 75%", "end 55%"] });
  // the progress line draws down the timeline as you scroll through it
  const lineScale = useSpring(scrollYProgress, { stiffness: 120, damping: 30, restDelta: 0.001 });

  return (
    <section id="how-it-works" className="mx-auto max-w-6xl scroll-mt-20 px-6 py-24 sm:py-32">
      <Reveal>
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="font-serif text-3xl font-semibold text-ink sm:text-4xl">How it works</h2>
          <p className="mt-4 text-balance text-lg leading-relaxed text-ink-muted">
            Every verdict passes through nine stages, from raw text to a scored,
            evidence-backed explanation &mdash; narrowing a pile of documents down
            to the few that actually answer the claim.
          </p>
        </div>
      </Reveal>

      <Reveal delay={0.1}>
        <EvidenceFunnel />
      </Reveal>

      <div ref={timelineRef} className="relative mx-auto mt-20 max-w-3xl">
        {/* track + scroll-driven progress line, centred on the stage nodes */}
        <div aria-hidden className="absolute bottom-4 left-[15px] top-4 w-px bg-border" />
        <motion.div
          aria-hidden
          className="absolute bottom-4 left-[15px] top-4 w-px origin-top bg-accent"
          style={{ scaleY: lineScale }}
        />
        <ol className="space-y-6">
          {PIPELINE_STAGES.map((stage) => (
            <li key={stage.number}>
              {PHASE_LABELS[stage.number] && (
                <p className="mb-3 ml-12 text-[11px] font-semibold uppercase tracking-[0.14em] text-accent">
                  {PHASE_LABELS[stage.number]}
                </p>
              )}
              <PipelineStage stage={stage} />
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
