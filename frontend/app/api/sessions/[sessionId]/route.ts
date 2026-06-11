import { proxyEngine } from "@/lib/engine-proxy";

export async function GET(
  _req: Request,
  { params }: { params: { sessionId: string } },
) {
  return proxyEngine(`/v1/sessions/${encodeURIComponent(params.sessionId)}`);
}
