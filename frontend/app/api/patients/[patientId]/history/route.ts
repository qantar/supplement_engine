import { proxyEngine } from "@/lib/engine-proxy";

export async function GET(
  _req: Request,
  { params }: { params: { patientId: string } },
) {
  const { searchParams } = new URL(_req.url);
  const limit = searchParams.get("limit") ?? "10";
  return proxyEngine(
    `/v1/patients/${encodeURIComponent(params.patientId)}/history?limit=${limit}`,
  );
}
