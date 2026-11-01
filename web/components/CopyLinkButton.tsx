"use client";

import { useState } from "react";

export function CopyLinkButton({ runId }: { runId: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    const url = `${window.location.origin}/result/${runId}`;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard access denied; nothing meaningful to recover to here.
    }
  };

  return (
    <button
      type="button"
      onClick={handleCopy}
      className="inline-flex items-center gap-1.5 rounded-full border border-border px-3 py-1.5 text-xs text-ink-muted transition-colors hover:bg-bg-alt"
    >
      {copied ? "Copied!" : "Copy link"}
    </button>
  );
}
