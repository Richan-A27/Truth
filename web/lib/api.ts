import type { VerificationResponse, VerifyErrorResponse } from "./types";

export class VerifyError extends Error {}

export async function callVerify(
  content: string,
  sourceUrl?: string
): Promise<VerificationResponse> {
  const res = await fetch("/api/verify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content, source_url: sourceUrl || undefined }),
  });

  const data = await res.json().catch(() => null);

  if (!res.ok) {
    const message =
      (data as VerifyErrorResponse | null)?.error ??
      "Something went wrong while verifying this content.";
    throw new VerifyError(message);
  }

  return data as VerificationResponse;
}
