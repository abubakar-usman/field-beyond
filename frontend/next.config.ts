import type { NextConfig } from "next";

// Browser calls go to /api/* on the same origin.
// Locally Next rewrites them to the FastAPI server; on the VM Caddy routes /api before Next.
const backend = process.env.BACKEND_URL ?? "http://localhost:8000";

const config: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/:path*` }];
  },
};

export default config;
