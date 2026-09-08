import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: [
    '127.0.0.1',
    'localhost',
    '*.trycloudflare.com',
    'perceived-structures-visiting-championship.trycloudflare.com',
  ],
  experimental: {
    optimizePackageImports: ['recharts', '@tabler/icons-react'],
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
