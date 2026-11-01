import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { Card } from "@/components/ui/Card";
import { VerificationResult } from "@/components/VerificationResult";
import type { VerificationResponse } from "@/lib/types";

async function getResult(runId: string): Promise<VerificationResponse | null> {
  const res = await fetch(`${process.env.TRUTH_API_URL}/verify/${runId}`, {
    cache: "no-store",
  });
  if (!res.ok) return null;
  return res.json();
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ runId: string }>;
}): Promise<Metadata> {
  const { runId } = await params;
  const result = await getResult(runId);
  if (!result) return { title: "Result not found — Truth" };

  return {
    title: `Trust score ${result.trust_score} — ${result.verdict_label.replace(/_/g, " ")} | Truth`,
    description: result.explanation,
  };
}

export default async function ResultPage({
  params,
}: {
  params: Promise<{ runId: string }>;
}) {
  const { runId } = await params;
  const result = await getResult(runId);
  if (!result) notFound();

  return (
    <div className="mx-auto max-w-3xl px-6 py-16">
      <Card className="p-6 sm:p-8">
        <VerificationResult result={result} />
      </Card>
    </div>
  );
}
