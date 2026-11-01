"use client";

import { addDoc, collection, serverTimestamp } from "firebase/firestore";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { db } from "@/lib/firebase/client";
import type { VerificationResponse } from "@/lib/types";

type SaveState = "idle" | "saving" | "saved" | "error";

export function SaveToHistoryButton({
  result,
  contentPreview,
}: {
  result: VerificationResponse;
  contentPreview: string;
}) {
  const { user } = useAuth();
  const pathname = usePathname();
  const [state, setState] = useState<SaveState>("idle");

  if (!user) {
    const stashAndNavigate = () => {
      sessionStorage.setItem(
        "truth:pendingSave",
        JSON.stringify({ result, contentPreview })
      );
    };

    return (
      <Link
        href={`/sign-in?next=${encodeURIComponent(pathname || "/")}`}
        onClick={stashAndNavigate}
        className="text-xs text-ink-muted underline decoration-border underline-offset-2 hover:text-ink"
      >
        Sign in to save this result
      </Link>
    );
  }

  const handleSave = async () => {
    setState("saving");
    try {
      // db is guaranteed set here: `user` only becomes non-null via
      // AuthContext's onAuthStateChanged, which only runs when auth (and
      // therefore db) was initialized.
      await addDoc(collection(db!, "users", user.uid, "verifications"), {
        run_id: result.run_id,
        trust_score: result.trust_score,
        verdict_label: result.verdict_label,
        explanation: result.explanation,
        contentPreview: contentPreview.slice(0, 200),
        source: "web",
        savedAt: serverTimestamp(),
      });
      setState("saved");
    } catch {
      setState("error");
    }
  };

  if (state === "saved") {
    return <span className="text-xs text-success">Saved to history</span>;
  }

  return (
    <button
      type="button"
      onClick={handleSave}
      disabled={state === "saving"}
      className="inline-flex items-center gap-1.5 rounded-full border border-border px-3 py-1.5 text-xs text-ink-muted transition-colors hover:bg-bg-alt disabled:opacity-50"
    >
      {state === "saving" ? "Saving…" : state === "error" ? "Couldn't save — retry" : "Save to history"}
    </button>
  );
}
