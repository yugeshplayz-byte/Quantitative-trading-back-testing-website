import type { NextConfig } from "next";

// STATIC_EXPORT=1 builds plain HTML/JS into `out/`, which the FastAPI backend (or any static host) can serve.
// Normal `npm run dev` / Vercel builds are unaffected.
const staticExport = process.env.STATIC_EXPORT === "1";

const nextConfig: NextConfig = {
  ...(staticExport ? { output: "export" as const, trailingSlash: true } : {}),
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
