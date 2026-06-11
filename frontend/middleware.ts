import { NextRequest, NextResponse } from "next/server";

/** Optional HTTP basic auth for the clinician console (pilot deployments). */
export function middleware(request: NextRequest) {
  const user = process.env.CONSOLE_AUTH_USER;
  const pass = process.env.CONSOLE_AUTH_PASSWORD;
  if (!user || !pass) {
    return NextResponse.next();
  }

  const auth = request.headers.get("authorization");
  if (auth?.startsWith("Basic ")) {
    const decoded = atob(auth.slice(6));
    const sep = decoded.indexOf(":");
    const u = decoded.slice(0, sep);
    const p = decoded.slice(sep + 1);
    if (u === user && p === pass) {
      return NextResponse.next();
    }
  }

  return new NextResponse("Authentication required.", {
    status: 401,
    headers: { "WWW-Authenticate": 'Basic realm="Supplement Engine Console"' },
  });
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
