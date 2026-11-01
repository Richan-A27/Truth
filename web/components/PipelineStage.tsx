"use client";

import { motion } from "framer-motion";
import type { PIPELINE_STAGES } from "@/lib/constants";

type Stage = (typeof PIPELINE_STAGES)[number];

export function PipelineStage({ stage }: { stage: Stage }) {
  return (
    <motion.div
      className="relative flex gap-5"
      initial="hidden"
      whileInView="shown"
      viewport={{ once: true, margin: "-35% 0px -35% 0px" }}
    >
      {/* node on the timeline - lights up as it reaches the middle of the screen */}
      {/* literal colours: framer-motion can't interpolate CSS variables (these mirror --surface, --ink-muted, --accent) */}
      <motion.span
        variants={{
          hidden: { backgroundColor: "rgb(255, 255, 255)", color: "rgb(92, 92, 87)", scale: 1 },
          shown: { backgroundColor: "rgb(166, 43, 63)", color: "rgb(255, 255, 255)", scale: [1, 1.18, 1] },
        }}
        transition={{ duration: 0.45 }}
        className="relative z-10 mt-4 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-border font-serif text-sm font-semibold"
      >
        {stage.number}
      </motion.span>

      <motion.div
        variants={{ hidden: { opacity: 0.45, x: 12 }, shown: { opacity: 1, x: 0 } }}
        transition={{ duration: 0.45, ease: "easeOut" }}
        className="flex-1 rounded-2xl border border-border bg-surface p-5 shadow-soft"
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-medium text-ink">{stage.title}</h3>
          <span className="rounded-full bg-accent-soft px-2.5 py-0.5 text-xs font-medium text-accent-hover">
            {stage.metric}
          </span>
        </div>
        <p className="mt-2 text-sm leading-relaxed text-ink-muted">{stage.description}</p>
        <span className="mt-3 inline-flex w-fit items-center rounded-full border border-border px-2.5 py-0.5 text-xs text-ink-muted">
          {stage.tech}
        </span>
      </motion.div>
    </motion.div>
  );
}
