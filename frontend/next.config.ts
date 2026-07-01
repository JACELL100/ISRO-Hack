import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // NEXT_PUBLIC_API_URL is injected at build-time by Vercel (project env var)
  // or read from .env.local in development. The NEXT_PUBLIC_ prefix makes it
  // available in the browser bundle automatically — no env block needed here.
  //
  // Default fallback for local development only:
  env: {
    NEXT_PUBLIC_API_URL:
      process.env.NEXT_PUBLIC_API_URL || "https://backend-isrohack.onrender.com",
  },
  // NOTE: output:'standalone' is for Docker / self-hosted Node deployments only.
  // Vercel manages its own output format — do NOT set output:'standalone' here.
};

export default nextConfig;
