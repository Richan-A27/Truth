"use client";

import { useEffect, useState } from "react";
import { callVerify, VerifyError } from "@/lib/api";
import { EXAMPLE_CLAIMS } from "@/lib/constants";
import type { VerificationResponse } from "@/lib/types";
import { Button } from "./ui/Button";
import { Card } from "./ui/Card";
import { Reveal } from "./ui/Reveal";
import { PipelineProgress } from "./PipelineProgress";
import { VerificationResult } from "./VerificationResult";

type Status = "idle" | "loading" | "success" | "error";

const PENDING_SAVE_KEY = "truth:pendingSave";

export function LiveDemo() {
  const [content, setContent] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [result, setResult] = useState<VerificationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Restores an in-progress result after a signed-out "save" round-trips
  // through /sign-in — the response is cached here, not re-fetched.
  useEffect(() => {
    const raw = sessionStorage.getItem(PENDING_SAVE_KEY);
    if (!raw) return;
    try {
      const pending = JSON.parse(raw) as { result: VerificationResponse; contentPreview: string };
      setResult(pending.result);
      setContent(pending.contentPreview);
      setStatus("success");
    } catch {
      // Malformed/stale entry; ignore.
    } finally {
      sessionStorage.removeItem(PENDING_SAVE_KEY);
    }
  }, []);

  const runVerify = async (text: string) => {
    if (!text.trim() || status === "loading") return;
    setStatus("loading");
    setError(null);
    setResult(null);
    try {
      const data = await callVerify(text.trim());
      setResult(data);
      setStatus("success");
    } catch (err) {
      setError(err instanceof VerifyError ? err.message : "Something went wrong.");
      setStatus("error");
    }
  };

  return (
    <section className="mx-auto max-w-3xl px-6 py-16 sm:py-24">
      <Reveal>
        <div className="text-center">
          <h2 className="font-serif text-3xl font-semibold text-ink sm:text-4xl">
            See it verify something
          </h2>
          <p className="mt-4 text-balance text-lg leading-relaxed text-ink-muted">
            Paste a claim or a short excerpt. This calls the live pipeline &mdash;
            not a canned response.
          </p>
        </div>
      </Reveal>

      <Reveal delay={0.1}>
        <Card className="mt-10 p-6 sm:p-8">
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="e.g. The Eiffel Tower is located in Berlin, Germany."
            rows={4}
            maxLength={5000}
            aria-label="Content to verify"
            className="w-full resize-none rounded-xl border border-border bg-bg p-4 text-sm text-ink placeholder:text-ink-muted focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20"
          />

          <div className="mt-3 flex flex-wrap gap-2">
            {EXAMPLE_CLAIMS.map((example) => (
              <button
                key={example}
                type="button"
                onClick={() => {
                  setContent(example);
                  runVerify(example);
                }}
                className="rounded-full border border-border px-3 py-1.5 text-xs text-ink-muted transition-colors hover:bg-bg-alt"
              >
                Try: &ldquo;{example.length > 40 ? `${example.slice(0, 40)}…` : example}&rdquo;
              </button>
            ))}
          </div>

          <div className="mt-5 flex items-center justify-between">
            <span className="text-xs text-ink-muted">{content.length}/5000</span>
            <Button
              onClick={() => runVerify(content)}
              disabled={status === "loading" || !content.trim()}
            >
              {status === "loading" ? "Verifying…" : "Verify"}
            </Button>
          </div>

          {status === "loading" && (
            <div className="mt-8 border-t border-border pt-8">
              <PipelineProgress />
            </div>
          )}

          {status === "error" && error && (
            <div className="mt-6 rounded-xl border border-danger/20 bg-danger/5 p-4 text-sm text-danger">
              {error}
            </div>
          )}

          {status === "success" && result && (
            <div className="mt-8 border-t border-border pt-8">
              <VerificationResult result={result} contentPreview={content} />
            </div>
          )}
        </Card>
      </Reveal>
    </section>
  );
}
