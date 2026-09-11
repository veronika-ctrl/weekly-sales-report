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
    // Klaviyo reporting retries can wait on Retry-After (~45s); default 30s
    // proxy timeout becomes a spurious Internal Server Error in the UI.
    proxyTimeout: 300_000,
  },
  // Local `next dev`: browser /api is proxied to the FastAPI process on this machine.
  // This rewrite does NOT work on Vercel (nothing listens on 127.0.0.1:8000 there).
  // Production must set NEXT_PUBLIC_API_URL to a persistent FastAPI host (Render/Railway).
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
