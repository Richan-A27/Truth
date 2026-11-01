import { ExtensionPromo } from "@/components/ExtensionPromo";
import { Footer } from "@/components/Footer";
import { Hero } from "@/components/Hero";
import { HowItWorks } from "@/components/HowItWorks";
import { StatsStrip } from "@/components/StatsStrip";
import { UnderTheHood } from "@/components/UnderTheHood";
import { UseCases } from "@/components/UseCases";

export default function Home() {
  return (
    <main>
      <Hero />
      <StatsStrip />
      <UseCases />
      <HowItWorks />
      <ExtensionPromo />
      <UnderTheHood />
      <Footer />
    </main>
  );
}
