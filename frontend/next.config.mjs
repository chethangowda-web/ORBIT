/** @type {import('next').NextConfig} */
const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
];

const nextConfig = {
  poweredByHeader: false,
  experimental: {
    cpus: 1,
    workerThreads: false,
  },
  // On Vercel the dashboard calls the backend through its own address (see lib/api-base.ts), so any
  // deployment address can sign in without the backend having to know it.
  async rewrites() {
    const api = process.env.NEXT_PUBLIC_API_URL || "";
    if (!/^https?:\/\//i.test(api)) return [];
    return [{ source: "/backend-api/:path*", destination: `${api.replace(/\/+$/, "")}/:path*` }];
  },
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
