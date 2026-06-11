/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Emit a self-contained server bundle for the Docker runtime stage.
  output: "standalone",
  // Proxy API calls to the FastAPI backend so the browser hits same-origin.
  async rewrites() {
    const target = process.env.ENGINE_API_URL || "http://localhost:8000";
    return [{ source: "/api/engine/:path*", destination: `${target}/:path*` }];
  },
};
export default nextConfig;
