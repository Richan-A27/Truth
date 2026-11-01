import type { Metadata } from "next";
import { Fraunces, Inter } from "next/font/google";
import { AuthProvider } from "@/context/AuthContext";
import { MotionProvider } from "@/components/MotionProvider";
import { Navbar } from "@/components/Navbar";
import "./globals.css";

const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-fraunces",
  weight: ["500", "600"],
});

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "Truth — Explainable Fact Verification",
  description:
    "A 9-stage AI pipeline that extracts claims, gathers evidence, and produces an explainable trust score.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${fraunces.variable} ${inter.variable}`}>
      <body className="font-sans antialiased bg-bg text-ink">
        <MotionProvider>
          <AuthProvider>
            <Navbar />
            {children}
          </AuthProvider>
        </MotionProvider>
      </body>
    </html>
  );
}
