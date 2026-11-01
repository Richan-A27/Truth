import Link from "next/link";
import { Reveal } from "./ui/Reveal";
import { VerificationDemo } from "./VerificationDemo";

export function Hero() {
  return (
    <section className="relative overflow-hidden">
      <div aria-hidden className="bg-dot-grid pointer-events-none absolute inset-0" />
      <div
        aria-hidden
        className="pointer-events-none absolute -top-40 left-1/2 h-[420px] w-[720px] -translate-x-1/2 rounded-full bg-accent-soft/50 blur-3xl"
      />
      <div className="relative mx-auto grid max-w-6xl items-center gap-14 px-6 py-20 sm:py-28 lg:grid-cols-[1.1fr_1fr] lg:gap-10">
        <div className="text-center lg:text-left">
          <Reveal>
            <span className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-4 py-1.5 text-xs font-medium text-ink-muted">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-60 motion-reduce:animate-none" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-accent" />
              </span>
              A 9-stage explainable verification pipeline
            </span>
          </Reveal>
          <Reveal delay={0.08}>
            <h1 className="mx-auto mt-8 max-w-3xl text-balance font-serif text-4xl font-semibold leading-[1.15] text-ink sm:text-5xl lg:mx-0">
              Truth doesn&rsquo;t ask you to trust it.
              <br />
              <span className="text-accent">It shows you the evidence.</span>
            </h1>
          </Reveal>
          <Reveal delay={0.16}>
            <p className="mx-auto mt-6 max-w-xl text-balance text-lg leading-relaxed text-ink-muted lg:mx-0">
              Paste a claim, a message, an article &mdash; anything. Truth breaks it
              into checkable claims, gathers evidence from independent sources, and
              shows you exactly what supports or contradicts it.
            </p>
          </Reveal>
          <Reveal delay={0.24}>
            <div className="mt-10 flex flex-wrap items-center justify-center gap-4 lg:justify-start">
              <Link
                href="/verify"
                className="inline-flex items-center justify-center gap-2 rounded-full bg-accent px-6 py-3 text-sm font-medium text-white transition-all duration-200 hover:-translate-y-0.5 hover:bg-accent-hover"
              >
                Try it
              </Link>
              <a
                href="#how-it-works"
                className="inline-flex items-center justify-center gap-2 rounded-full border border-border bg-surface/60 px-6 py-3 text-sm font-medium text-ink transition-all duration-200 hover:-translate-y-0.5 hover:bg-bg-alt"
              >
                See how it works
              </a>
            </div>
          </Reveal>
        </div>

        <Reveal delay={0.2}>
          <VerificationDemo />
        </Reveal>
      </div>
    </section>
  );
}
