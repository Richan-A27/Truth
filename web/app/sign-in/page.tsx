"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";

function SignInForm() {
  const { user, loading, signInWithGoogle } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = searchParams.get("next") || "/";
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!loading && user) {
      router.replace(next);
    }
  }, [loading, user, next, router]);

  const handleSignIn = async () => {
    setError(null);
    setSubmitting(true);
    try {
      await signInWithGoogle();
      router.replace(next);
    } catch {
      setError("Sign-in didn't go through. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto flex max-w-6xl items-center justify-center px-6 py-24 sm:py-32">
      <Card className="w-full max-w-sm p-8 text-center">
        <h1 className="font-serif text-2xl font-semibold text-ink">Sign in to Truth</h1>
        <p className="mt-2 text-sm leading-relaxed text-ink-muted">
          Save verification results and come back to them later.
        </p>

        <Button
          onClick={handleSignIn}
          disabled={submitting}
          className="mt-8 w-full"
        >
          {submitting ? "Signing in…" : "Continue with Google"}
        </Button>

        {error && <p className="mt-4 text-sm text-danger">{error}</p>}
      </Card>
    </div>
  );
}

export default function SignInPage() {
  return (
    <Suspense fallback={null}>
      <SignInForm />
    </Suspense>
  );
}
