import type { NextConfig } from "next";

// When running inside Docker, this will point to http://backend:8000
const BACKEND_DESTINATION =
  process.env.BACKEND_URL ||
  `http://${process.env.BACKEND_HOST || "backend"}:${process.env.BACKEND_PORT || "8000"}`;

const nextConfig: NextConfig = {
  output: "standalone",
  serverExternalPackages: [],
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