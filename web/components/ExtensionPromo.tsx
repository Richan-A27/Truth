import Link from "next/link";
import { Reveal } from "./ui/Reveal";

export function ExtensionPromo() {
  return (
    <section id="extension" className="scroll-mt-20 bg-bg-alt py-24 sm:py-32">
      <div className="mx-auto max-w-4xl px-6 text-center">
        <Reveal>
          <span className="inline-flex items-center rounded-full border border-border bg-surface px-4 py-1.5 text-xs font-medium text-ink-muted">
            Browser extension
          </span>
          <h2 className="mx-auto mt-6 max-w-2xl text-balance font-serif text-3xl font-semibold text-ink sm:text-4xl">
            Take it with you, off this site
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-balance text-lg leading-relaxed text-ink-muted">
            Select any text on the web and right-click to verify it. Or drag a box
            over a screenshot, a quote in an image, anything &mdash; the extension
            reads it and checks it, right where you found it.
          </p>
        </Reveal>

        <Reveal delay={0.1}>
          <div className="mt-10 grid grid-cols-1 gap-4 text-left sm:grid-cols-2">
            <div className="rounded-2xl border border-border bg-surface p-5">
              <p className="font-medium text-ink">Right-click to verify</p>
              <p className="mt-1.5 text-sm leading-relaxed text-ink-muted">
                Select text on any page &mdash; a post, a message, an article &mdash;
                and check it without leaving the page.
              </p>
            </div>
            <div className="rounded-2xl border border-border bg-surface p-5">
              <p className="font-medium text-ink">Select a region to OCR</p>
              <p className="mt-1.5 text-sm leading-relaxed text-ink-muted">
                Text inside an image or a screenshot works too &mdash; drag a box
                around it and Truth reads it for you.
              </p>
            </div>
          </div>
        </Reveal>

        <Reveal delay={0.16}>
          <Link
            href="/extension"
            className="mt-10 inline-flex items-center justify-center gap-2 rounded-full bg-accent px-6 py-3 text-sm font-medium text-white transition-all duration-200 hover:-translate-y-0.5 hover:bg-accent-hover"
          >
            Get the extension
          </Link>
        </Reveal>
      </div>
    </section>
  );
}
