"use client";

import { MotionConfig } from "framer-motion";
import type { ReactNode } from "react";

// Honours the OS "reduce motion" setting for every framer-motion animation
// below it: transforms are skipped, opacity fades are kept.
export function MotionProvider({ children }: { children: ReactNode }) {
  return <MotionConfig reducedMotion="user">{children}</MotionConfig>;
}
