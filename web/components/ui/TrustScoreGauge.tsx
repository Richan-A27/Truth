"use client";

import { motion } from "framer-motion";
import { CountUp } from "./CountUp";

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
  const progress = Math.max(0, Math.min(100, score)) / 100;
  const color = colorForScore(score);

  return (
    <div
      className="relative inline-flex shrink-0 items-center justify-center"
      style={{ width: size, height: size }}
      role="img"
      aria-label={loading ? "Analyzing" : `Trust score ${Math.round(score)} out of 100`}
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
        {loading ? (
          // an indeterminate arc sweeping round the track
          <motion.circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="rgb(var(--accent))"
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={`${circumference * 0.22} ${circumference}`}
            style={{ originX: "50%", originY: "50%" }}
            animate={{ rotate: 360 }}
            transition={{ duration: 1.1, repeat: Infinity, ease: "linear" }}
          />
        ) : (
          <motion.circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset: circumference * (1 - progress) }}
            transition={{ duration: 1.1, ease: [0.22, 1, 0.36, 1] }}
          />
        )}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        {loading ? (
          <span className="text-xs text-ink-muted">analyzing…</span>
        ) : (
          // the number scales with the gauge instead of a fixed text size
          <span className="font-serif font-semibold leading-none text-ink" style={{ fontSize: Math.max(12, size * 0.28) }}>
            <CountUp value={Math.round(score)} immediate duration={1.1} />
          </span>
        )}
      </div>
    </div>
  );
}
