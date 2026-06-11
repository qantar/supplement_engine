import { NextRequest } from "next/server";
import type { RecommendationRequest } from "@/lib/types";
import { proxyEngine } from "@/lib/engine-proxy";

export async function POST(req: NextRequest) {
  let body: RecommendationRequest;
  try {
    body = (await req.json()) as RecommendationRequest;
  } catch {
    return Response.json(
      { detail: "Request body must be valid JSON." },
      { status: 400 },
    );
  }

  if (!body.patient_id && !body.patient) {
    return Response.json(
      { detail: "Provide patient_id or inline patient profile." },
      { status: 400 },
    );
  }

  return proxyEngine("/v1/recommendations", {
    method: "POST",
    body: JSON.stringify(body),
  });
}
