import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 1. Prevent Next.js from buffering chunks in gzip/brotli
  compress: false,

  output: "standalone",

  // 2. Explicitly send anti-buffering headers directly from Next.js to Cloudflare
  async headers() {
    return [
      {
        source: "/api/:path*",
        headers: [
          { key: "X-Accel-Buffering", value: "no" },
          { key: "Cache-Control", value: "no-cache, no-transform" },
          { key: "Connection", value: "keep-alive" },
        ],
      },
    ];
  },

  async rewrites() {
    const backendHost = process.env.BACKEND_HOST || "backend";
    const backendPort = process.env.BACKEND_PORT || "8000";
    return [
      {
        source: "/api/:path*",
        destination: `http://${backendHost}:${backendPort}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;