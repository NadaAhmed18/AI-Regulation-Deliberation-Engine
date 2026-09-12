import type { NextConfig } from "next";

// Accessible during Next.js Node.js server runtime (no NEXT_PUBLIC_ prefix required here)
const BACKEND_HOST = process.env.BACKEND_HOST || "127.0.0.1";
const BACKEND_PORT = process.env.BACKEND_PORT || "8000";
const BACKEND_DESTINATION =
  process.env.BACKEND_URL || `http://${BACKEND_HOST}:${BACKEND_PORT}`;

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${BACKEND_DESTINATION}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;