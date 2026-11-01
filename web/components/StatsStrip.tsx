import { STATS } from "@/lib/constants";
import { CountUp } from "./ui/CountUp";
import { Reveal } from "./ui/Reveal";

export function StatsStrip() {
  return (
    <section className="border-y border-border bg-surface/60">
      <div className="mx-auto grid max-w-6xl grid-cols-2 gap-8 px-6 py-14 sm:grid-cols-4">
        {STATS.map((stat, i) => (
          <Reveal key={stat.label} delay={i * 0.06} className="text-center">
            <div className="font-serif text-4xl font-semibold text-accent">
              {typeof stat.value === "number" ? <CountUp value={stat.value} /> : stat.value}
              {stat.suffix}
            </div>
            <div className="mt-2 text-sm font-medium text-ink">{stat.label}</div>
            <div className="mt-0.5 text-xs text-ink-muted">{stat.detail}</div>
          </Reveal>
        ))}
      </div>
    </section>
  );
}
