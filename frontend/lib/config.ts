/**
 * Backend base URL. Configure with NEXT_PUBLIC_API_URL (see .env.example).
 * The localhost fallback below is a development convenience ONLY and is never used in production
 * builds - a production deployment without NEXT_PUBLIC_API_URL shows a configuration error instead.
 */
const configured = process.env.NEXT_PUBLIC_API_URL?.trim().replace(/\/+$/, "");
const isProd = process.env.NODE_ENV === "production";

export const API_URL: string = configured ?? (isProd ? "" : "http://localhost:8000");
export const API_CONFIGURED: boolean = Boolean(configured) || !isProd;
