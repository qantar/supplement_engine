import { NextRequest } from "next/server";
import { proxyEngine } from "@/lib/engine-proxy";

export async function POST(req: NextRequest) {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return Response.json(
      { detail: "Request body must be valid JSON." },
      { status: 400 },
    );
  }
  return proxyEngine("/v1/feedback", {
    method: "POST",
    body: JSON.stringify(body),
  });
}
