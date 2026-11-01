import { NextResponse } from "next/server";

const MAX_CONTENT_LENGTH = 5000;
// Generous enough to cover the backend running on the local Ollama LLM
// backend (~7-8s/call, vs. Gemini's sub-second calls) - a multi-claim
// submission can trigger several sequential LLM calls (claim extraction,
// plus up to 3 evidence-resolution calls per claim in stage 7b).
const BACKEND_TIMEOUT_MS = 120_000;

export async function POST(req: Request) {
  let body: { content?: unknown; source_url?: unknown };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Request body must be JSON." }, { status: 400 });
  }

  const content = typeof body.content === "string" ? body.content.trim() : "";
  const sourceUrl = typeof body.source_url === "string" ? body.source_url : undefined;

  if (!content) {
    return NextResponse.json({ error: "Please enter some text to verify." }, { status: 400 });
  }
  if (content.length > MAX_CONTENT_LENGTH) {
    return NextResponse.json(
      { error: `Please keep submissions under ${MAX_CONTENT_LENGTH} characters.` },
      { status: 400 }
    );
  }

  const backendUrl = process.env.TRUTH_API_URL;
  if (!backendUrl) {
    return NextResponse.json(
      { error: "The verification service is not configured." },
      { status: 500 }
    );
  }

  try {
    const upstream = await fetch(`${backendUrl}/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content, source_url: sourceUrl }),
      signal: AbortSignal.timeout(BACKEND_TIMEOUT_MS),
    });

    const data = await upstream.json().catch(() => null);

    if (!upstream.ok) {
      const message =
        (data && typeof data === "object" && "detail" in data
          ? String((data as { detail: unknown }).detail)
          : null) ?? "The verification service rejected this request.";
      return NextResponse.json({ error: message }, { status: upstream.status });
    }

    return NextResponse.json(data);
  } catch (err) {
    const timedOut = err instanceof Error && err.name === "TimeoutError";
    return NextResponse.json(
      {
        error: timedOut
          ? "Verification is taking longer than expected. Please try again."
          : "Couldn't reach the verification service. Please try again in a moment.",
      },
      { status: timedOut ? 504 : 502 }
    );
  }
}
