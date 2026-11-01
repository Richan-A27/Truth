import { PIPELINE_STAGES } from "@/lib/constants";
import { PipelineStage } from "./PipelineStage";
import { Reveal } from "./ui/Reveal";

export function HowItWorks() {
  return (
    <section id="how-it-works" className="mx-auto max-w-6xl scroll-mt-20 px-6 py-24 sm:py-32">
      <Reveal>
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="font-serif text-3xl font-semibold text-ink sm:text-4xl">
            How it works
          </h2>
          <p className="mt-4 text-balance text-lg leading-relaxed text-ink-muted">
            Every verdict passes through nine stages, from raw text to a scored,
            evidence-backed explanation.
          </p>
        </div>
      </Reveal>
      <div className="mt-14 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {PIPELINE_STAGES.map((stage, i) => (
          <PipelineStage key={stage.number} stage={stage} delay={(i % 3) * 0.06} />
        ))}
      </div>
    </section>
  );
}
