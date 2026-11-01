import type { Metadata } from "next";
import { LiveDemo } from "@/components/LiveDemo";

export const metadata: Metadata = {
  title: "Verify a claim — Truth",
  description: "Paste a claim, a message, or an article and see the evidence behind it.",
};

export default function VerifyPage() {
  return <LiveDemo />;
}
