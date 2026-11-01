type Tone = "success" | "danger" | "neutral";

function toneForVerdict(label: string): Tone {
  const normalized = label.toLowerCase();
  if (normalized.includes("support") || normalized.includes("true") || normalized.includes("entail")) {
    return "success";
  }
  if (normalized.includes("contradict") || normalized.includes("false")) {
    return "danger";
  }
  return "neutral";
}

const toneClasses: Record<Tone, string> = {
  success: "bg-success/10 text-success border-success/20",
  danger: "bg-danger/10 text-danger border-danger/20",
  neutral: "bg-neutral/10 text-neutral border-neutral/20",
};

export function Badge({ label }: { label: string }) {
  const tone = toneForVerdict(label);
  return (
    <span
      className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-medium capitalize ${toneClasses[tone]}`}
    >
      {label.replace(/_/g, " ")}
    </span>
  );
}
