/**
 * Backend base URL. Configure with NEXT_PUBLIC_API_URL (see .env.example):
 *   - an absolute URL (e.g. https://your-api.onrender.com) when frontend and backend are hosted separately;
 *   - the literal value `same-origin` when the backend serves this site itself (single-URL deployment).
 * The localhost fallback below is a development convenience ONLY and is never used in production
 * builds - a production deployment without NEXT_PUBLIC_API_URL shows a configuration error instead.
 */
const raw = process.env.NEXT_PUBLIC_API_URL?.trim().replace(/\/+$/, "");
const isProd = process.env.NODE_ENV === "production";
const sameOrigin = raw === "same-origin";

export const API_URL: string = sameOrigin ? "" : (raw ?? (isProd ? "" : "http://localhost:8000"));
export const API_CONFIGURED: boolean = sameOrigin || Boolean(raw) || !isProd;
