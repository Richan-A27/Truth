import type { VerificationResponse } from "@/lib/types";
import { Badge } from "./ui/Badge";
import { ClaimCard } from "./ClaimCard";
import { CopyLinkButton } from "./CopyLinkButton";
import { SaveToHistoryButton } from "./SaveToHistoryButton";
import { TrustScoreGauge } from "./ui/TrustScoreGauge";

export function VerificationResult({
  result,
  contentPreview,
}: {
  result: VerificationResponse;
  contentPreview?: string;
}) {
  const preview = contentPreview ?? result.claims[0]?.claim.text ?? result.explanation;

  return (
    <div>
      <div className="flex flex-col items-center gap-4 text-center sm:flex-row sm:text-left">
        <TrustScoreGauge score={result.trust_score} size={96} />
        <div>
          <Badge label={result.verdict_label} />
          <p className="mt-3 text-sm leading-relaxed text-ink-muted">{result.explanation}</p>
        </div>
      </div>

      <div className="mt-4 flex items-center justify-center gap-3 sm:justify-start">
        <CopyLinkButton runId={result.run_id} />
        <SaveToHistoryButton result={result} contentPreview={preview} />
      </div>

      {result.claims.length > 0 && (
        <div className="mt-8 space-y-3">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
            Claim by claim
          </h3>
          {result.claims.map((claim, i) => (
            <ClaimCard key={claim.claim.id} result={claim} defaultOpen={i === 0} />
          ))}
        </div>
      )}
    </div>
  );
}
