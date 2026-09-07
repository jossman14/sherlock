import type { NextConfig } from "next";

// UI dan API disatukan di satu origin lewat rewrite: browser cukup memanggil
// /api/... tanpa CORS, dan aliran SSE tidak perlu penanganan khusus.
const API = process.env.SHERLOCK_API_URL ?? "http://127.0.0.1:8477";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API}/api/:path*` }];
  },
};

export default nextConfig;
