"use client";

function colorForScore(score: number) {
  if (score >= 65) return "rgb(var(--success))";
  if (score <= 35) return "rgb(var(--danger))";
  return "rgb(var(--neutral))";
}

export function TrustScoreGauge({
  score,
  size = 120,
  loading = false,
}: {
  score: number;
  size?: number;
  loading?: boolean;
}) {
  const strokeWidth = size * 0.09;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const progress = loading ? 0.28 : Math.max(0, Math.min(100, score)) / 100;
  const offset = circumference * (1 - progress);
  const color = loading ? "rgb(var(--accent))" : colorForScore(score);

  return (
    <div
      className="relative inline-flex items-center justify-center"
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="rgb(var(--border))"
          strokeWidth={strokeWidth}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className={loading ? "animate-pulse" : "transition-[stroke-dashoffset] duration-700 ease-out"}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        {loading ? (
          <span className="text-xs text-ink-muted">analyzing…</span>
        ) : (
          <span className="font-serif text-3xl font-semibold text-ink">{Math.round(score)}</span>
        )}
      </div>
    </div>
  );
}
