import Link from "next/link";
import { Reveal } from "./ui/Reveal";

export function Hero() {
  return (
    <section className="relative overflow-hidden">
      <div
        aria-hidden
        className="pointer-events-none absolute -top-40 left-1/2 h-[420px] w-[720px] -translate-x-1/2 rounded-full bg-accent-soft/50 blur-3xl"
      />
      <div className="relative mx-auto max-w-6xl px-6 py-28 text-center sm:py-36">
        <Reveal>
          <span className="inline-flex items-center rounded-full border border-border bg-surface px-4 py-1.5 text-xs font-medium text-ink-muted">
            A 9-stage explainable verification pipeline
          </span>
        </Reveal>
        <Reveal delay={0.08}>
          <h1 className="mx-auto mt-8 max-w-3xl text-balance font-serif text-4xl font-semibold leading-[1.15] text-ink sm:text-5xl">
            Truth doesn&rsquo;t ask you to trust it.
            <br />
            It shows you the evidence.
          </h1>
        </Reveal>
        <Reveal delay={0.16}>
          <p className="mx-auto mt-6 max-w-xl text-balance text-lg leading-relaxed text-ink-muted">
            Paste a claim, a message, an article &mdash; anything. Truth breaks it
            into checkable claims, gathers evidence from independent sources, and
            shows you exactly what supports or contradicts it.
          </p>
        </Reveal>
        <Reveal delay={0.24}>
          <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
            <Link
              href="/verify"
              className="inline-flex items-center justify-center gap-2 rounded-full bg-accent px-6 py-3 text-sm font-medium text-white transition-all duration-200 hover:-translate-y-0.5 hover:bg-accent-hover"
            >
              Try it
            </Link>
            <a
              href="#how-it-works"
              className="inline-flex items-center justify-center gap-2 rounded-full border border-border px-6 py-3 text-sm font-medium text-ink transition-all duration-200 hover:-translate-y-0.5 hover:bg-bg-alt"
            >
              See how it works
            </a>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
