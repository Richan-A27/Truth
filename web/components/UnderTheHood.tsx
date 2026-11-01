import { TECH_STACK } from "@/lib/constants";
import { Reveal } from "./ui/Reveal";

export function UnderTheHood() {
  return (
    <section className="bg-bg-alt py-24 sm:py-32">
      <div className="mx-auto max-w-6xl px-6">
        <Reveal>
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="font-serif text-3xl font-semibold text-ink sm:text-4xl">
              Under the hood
            </h2>
            <p className="mt-4 text-balance text-lg leading-relaxed text-ink-muted">
              Every trust score traces back to real evidence and a model-level
              judgment &mdash; nothing about the pipeline is a black box.
            </p>
          </div>
        </Reveal>
        <Reveal delay={0.1}>
          <div className="mt-10 flex flex-wrap justify-center gap-2.5">
            {TECH_STACK.map((tech) => (
              <span
                key={tech}
                className="rounded-full border border-border bg-surface px-4 py-2 text-sm text-ink-muted"
              >
                {tech}
              </span>
            ))}
          </div>
        </Reveal>
      </div>
    </section>
  );
}
