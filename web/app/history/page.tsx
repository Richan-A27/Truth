"use client";

import { collection, getDocs, orderBy, query, Timestamp } from "firebase/firestore";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { db } from "@/lib/firebase/client";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";

interface HistoryItem {
  id: string;
  run_id: string;
  trust_score: number;
  verdict_label: string;
  contentPreview: string;
  source: "web" | "extension";
  savedAt: Timestamp | null;
}

export default function HistoryPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [items, setItems] = useState<HistoryItem[] | null>(null);

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/sign-in?next=/history");
    }
  }, [loading, user, router]);

  useEffect(() => {
    if (!user) return;
    // db is guaranteed set whenever user is (see SaveToHistoryButton).
    const q = query(
      collection(db!, "users", user.uid, "verifications"),
      orderBy("savedAt", "desc")
    );
    getDocs(q).then((snapshot) => {
      setItems(
        snapshot.docs.map((d) => ({ id: d.id, ...(d.data() as Omit<HistoryItem, "id">) }))
      );
    });
  }, [user]);

  if (loading || !user) return null;

  return (
    <div className="mx-auto max-w-3xl px-6 py-16">
      <h1 className="font-serif text-3xl font-semibold text-ink">Your history</h1>
      <p className="mt-2 text-ink-muted">Verifications you&rsquo;ve saved.</p>

      <div className="mt-8 space-y-3">
        {items === null && <p className="text-sm text-ink-muted">Loading…</p>}

        {items?.length === 0 && (
          <p className="text-sm text-ink-muted">
            Nothing saved yet.{" "}
            <Link href="/verify" className="underline">
              Verify something
            </Link>{" "}
            and save the result.
          </p>
        )}

        {items?.map((item) => (
          <Link key={item.id} href={`/result/${item.run_id}`}>
            <Card className="flex items-center gap-4 p-4 transition-colors hover:bg-bg-alt">
              <span className="font-serif text-2xl font-semibold text-accent">
                {item.trust_score}
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm text-ink">{item.contentPreview}</p>
                <div className="mt-1.5 flex items-center gap-2">
                  <Badge label={item.verdict_label} />
                  <span className="text-xs text-ink-muted">
                    {item.savedAt?.toDate().toLocaleDateString() ?? ""}
                  </span>
                  {item.source === "extension" && (
                    <span className="text-xs text-ink-muted">via extension</span>
                  )}
                </div>
              </div>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
