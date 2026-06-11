import { NextResponse } from "next/server";

export function engineConfig() {
  const target = process.env.ENGINE_API_URL || "http://localhost:8000";
  const apiKey = process.env.ENGINE_API_KEY;
  if (process.env.NODE_ENV === "production" && !apiKey) {
    throw new Error("ENGINE_API_KEY must be set in production.");
  }
  return { target, apiKey: apiKey || "dev-key" };
}

export async function proxyEngine(
  path: string,
  init: RequestInit = {},
): Promise<NextResponse> {
  const { target, apiKey } = engineConfig();
  const headers = new Headers(init.headers);
  headers.set("X-API-Key", apiKey);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  try {
    const upstream = await fetch(`${target}${path}`, {
      ...init,
      headers,
      cache: "no-store",
    });
    const text = await upstream.text();
    let data: unknown = null;
    if (text) {
      try {
        data = JSON.parse(text);
      } catch {
        data = { detail: text };
      }
    }
    return NextResponse.json(data, { status: upstream.status });
  } catch {
    return NextResponse.json(
      {
        detail:
          "Could not reach the recommendation engine. Confirm the API is running and ENGINE_API_URL is set.",
      },
      { status: 502 },
    );
  }
}
