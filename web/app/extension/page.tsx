import type { Metadata } from "next";
import { Card } from "@/components/ui/Card";

export const metadata: Metadata = {
  title: "Browser extension — Truth",
  description:
    "Verify text and screenshots anywhere on the web with the Truth browser extension.",
};

const STEPS = [
  {
    title: "Download",
    body: "Get the extension folder from the Truth repository (extension/).",
  },
  {
    title: "Open your browser's extensions page",
    body: "Chrome, Edge, or Brave — go to the extensions page and turn on Developer mode.",
  },
  {
    title: "Load unpacked",
    body: "Click “Load unpacked” and select the extension/ folder. That's it.",
  },
];

export default function ExtensionPage() {
  return (
    <div className="mx-auto max-w-3xl px-6 py-16 sm:py-24">
      <div className="text-center">
        <h1 className="font-serif text-3xl font-semibold text-ink sm:text-4xl">
          Verify anywhere, not just here
        </h1>
        <p className="mx-auto mt-4 max-w-xl text-balance text-lg leading-relaxed text-ink-muted">
          The Truth extension brings the same evidence-checking pipeline to any page
          you&rsquo;re already on.
        </p>
      </div>

      <div className="mt-12 grid grid-cols-1 gap-5 sm:grid-cols-2">
        <Card className="p-6">
          <h2 className="font-medium text-ink">Right-click to verify</h2>
          <p className="mt-2 text-sm leading-relaxed text-ink-muted">
            Select any text on a page &mdash; a post, a forwarded message, a line in
            an article &mdash; right-click, and choose &ldquo;Verify with
            Truth.&rdquo; A card appears right there with the trust score and a link
            to the full report.
          </p>
        </Card>
        <Card className="p-6">
          <h2 className="font-medium text-ink">Select a region to OCR</h2>
          <p className="mt-2 text-sm leading-relaxed text-ink-muted">
            Text inside an image or a screenshot isn&rsquo;t selectable &mdash; so
            drag a box around it instead. The extension reads the text locally (no
            server calls for the OCR step) and verifies what it finds.
          </p>
        </Card>
      </div>

      <div className="mt-16">
        <h2 className="text-center font-serif text-2xl font-semibold text-ink">
          Installing it
        </h2>
        <p className="mx-auto mt-2 max-w-md text-balance text-center text-sm text-ink-muted">
          Not yet on the Chrome Web Store &mdash; for now it loads unpacked, which
          takes about a minute.
        </p>
        <div className="mt-8 space-y-4">
          {STEPS.map((step, i) => (
            <div key={step.title} className="flex gap-4">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent-soft font-serif text-sm font-semibold text-accent-hover">
                {i + 1}
              </span>
              <div>
                <p className="font-medium text-ink">{step.title}</p>
                <p className="mt-1 text-sm leading-relaxed text-ink-muted">{step.body}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      <p className="mt-16 text-center text-sm text-ink-muted">
        The extension doesn&rsquo;t have its own sign-in yet &mdash; results verified
        there aren&rsquo;t saved to your{" "}
        <a href="/history" className="underline">
          history
        </a>
        . That&rsquo;s coming.
      </p>
    </div>
  );
}
