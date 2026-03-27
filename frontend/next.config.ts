import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  experimental: {
    optimizePackageImports: ['recharts', '@tabler/icons-react'],
  },
};

export default nextConfig;
