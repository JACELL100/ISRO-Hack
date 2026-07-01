import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Backend URL is hardcoded directly in lib/api.ts and components.
  // NOTE: output:'standalone' is for Docker / self-hosted Node deployments only.
  // Vercel manages its own output format — do NOT set output:'standalone' here.
};

export default nextConfig;
