import { USE_CASES } from "@/lib/constants";
import { Card } from "./ui/Card";
import { Reveal } from "./ui/Reveal";

export function UseCases() {
  return (
    <section id="use-cases" className="mx-auto max-w-6xl scroll-mt-20 px-6 py-24 sm:py-32">
      <Reveal>
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="font-serif text-3xl font-semibold text-ink sm:text-4xl">
            Wherever a claim shows up
          </h2>
          <p className="mt-4 text-balance text-lg leading-relaxed text-ink-muted">
            You don&rsquo;t have to take our word for it, or anyone else&rsquo;s.
          </p>
        </div>
      </Reveal>
      <div className="mt-14 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {USE_CASES.map((useCase, i) => (
          <Reveal key={useCase.title} delay={(i % 3) * 0.06}>
            <Card className="flex h-full flex-col gap-3 p-6">
              <span className="text-2xl">{useCase.icon}</span>
              <h3 className="font-medium text-ink">{useCase.title}</h3>
              <p className="text-sm leading-relaxed text-ink-muted">{useCase.scenario}</p>
              <p className="mt-auto border-t border-border pt-3 text-sm leading-relaxed text-ink">
                {useCase.outcome}
              </p>
            </Card>
          </Reveal>
        ))}
      </div>
    </section>
  );
}
