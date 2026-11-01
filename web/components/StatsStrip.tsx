import { STATS } from "@/lib/constants";
import { Reveal } from "./ui/Reveal";

export function StatsStrip() {
  return (
    <section className="mx-auto max-w-6xl px-6 py-20">
      <div className="grid grid-cols-2 gap-8 sm:grid-cols-4">
        {STATS.map((stat, i) => (
          <Reveal key={stat.label} delay={i * 0.06} className="text-center">
            <div className="font-serif text-4xl font-semibold text-accent">{stat.value}</div>
            <div className="mt-2 text-sm font-medium text-ink">{stat.label}</div>
            <div className="mt-0.5 text-xs text-ink-muted">{stat.detail}</div>
          </Reveal>
        ))}
      </div>
    </section>
  );
}
