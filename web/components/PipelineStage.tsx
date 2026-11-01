import { Card } from "./ui/Card";
import { Reveal } from "./ui/Reveal";
import type { PIPELINE_STAGES } from "@/lib/constants";

type Stage = (typeof PIPELINE_STAGES)[number];

export function PipelineStage({ stage, delay = 0 }: { stage: Stage; delay?: number }) {
  return (
    <Reveal delay={delay}>
      <Card className="flex h-full flex-col gap-3 p-6">
        <div className="flex items-center gap-3">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent-soft font-serif text-sm font-semibold text-accent-hover">
            {stage.number}
          </span>
          <h3 className="font-medium text-ink">{stage.title}</h3>
        </div>
        <p className="text-sm leading-relaxed text-ink-muted">{stage.description}</p>
        <span className="mt-auto inline-flex w-fit items-center rounded-full border border-border px-2.5 py-0.5 text-xs text-ink-muted">
          {stage.tech}
        </span>
      </Card>
    </Reveal>
  );
}
