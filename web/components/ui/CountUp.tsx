"use client";

import { useInView, useReducedMotion } from "framer-motion";
import { useEffect, useRef, useState } from "react";

// Counts from 0 to `value` once the number scrolls into view (or straight
// away with `immediate`). Jumps to the final value under reduced motion.
export function CountUp({
  value,
  duration = 1.2,
  immediate = false,
  className = "",
}: {
  value: number;
  duration?: number;
  immediate?: boolean;
  className?: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });
  const reduceMotion = useReducedMotion();
  const [display, setDisplay] = useState(0);
  const start = immediate || inView;

  useEffect(() => {
    if (!start) return;
    if (reduceMotion) {
      setDisplay(value);
      return;
    }
    let frame = 0;
    const startedAt = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - startedAt) / (duration * 1000));
      const eased = 1 - Math.pow(1 - t, 3);
      setDisplay(Math.round(value * eased));
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [start, value, duration, reduceMotion]);

  return (
    <span ref={ref} className={`tabular-nums ${className}`}>
      {display}
    </span>
  );
}
