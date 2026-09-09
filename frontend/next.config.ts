import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: [
    '127.0.0.1',
    'localhost',
    '*.trycloudflare.com',
    'perceived-structures-visiting-championship.trycloudflare.com',
    'princess-wines-tricks-spanking.trycloudflare.com',
  ],
  experimental: {
    optimizePackageImports: ['recharts', '@tabler/icons-react'],
    // Rewrites clone the request body; default 10MB truncates Qlik/Shopify CSVs
    // and the proxy then returns "Internal Server Error" as HTML.
    proxyClientMaxBodySize: '200mb',
  },
  // Browser calls /api on this origin; Next proxies to the FastAPI process.
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://127.0.0.1:8000/api/:path*',
      },
    ]
  },
};

export default nextConfig;
