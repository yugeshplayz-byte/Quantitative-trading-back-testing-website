type N = number | null | undefined;

const isNum = (v: N): v is number => typeof v === "number" && Number.isFinite(v);

export function money(v: N, digits = 0): string {
  if (!isNum(v)) return "–";
  const s = Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
  return `${v < 0 ? "-" : ""}$${s}`;
}
export function signedMoney(v: N, digits = 0): string {
  if (!isNum(v)) return "–";
  return `${v > 0 ? "+" : ""}${money(v, digits)}`;
}
export function num(v: N, digits = 2): string {
  if (!isNum(v)) return "–";
  return v.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}
export function int(v: N): string {
  return isNum(v) ? Math.round(v).toLocaleString("en-US") : "–";
}
/** Fractions in, percent out (0.123 -> 12.3%). */
export function pct(v: N, digits = 1): string {
  return isNum(v) ? `${(v * 100).toFixed(digits)}%` : "–";
}
/** Values already in percent units (12.3 -> 12.3%). */
export function pctRaw(v: N, digits = 1): string {
  return isNum(v) ? `${v.toFixed(digits)}%` : "–";
}
export function ratio(v: N, digits = 2): string {
  return isNum(v) ? v.toFixed(digits) : "–";
}
export function duration(mins: N): string {
  if (!isNum(mins)) return "–";
  if (mins < 60) return `${Math.round(mins)}m`;
  const h = Math.floor(mins / 60);
  return `${h}h ${Math.round(mins - h * 60)}m`;
}
export function days(v: N): string {
  return isNum(v) ? `${Math.round(v)}d` : "–";
}
export function shortDate(s: string | null | undefined): string {
  return s ? s.slice(0, 10) : "–";
}
export function pnlClass(v: N): string {
  if (!isNum(v) || v === 0) return "text-foreground";
  return v > 0 ? "text-up" : "text-down";
}
export function compact(v: N): string {
  if (!isNum(v)) return "–";
  const a = Math.abs(v);
  const s = a >= 1e6 ? `${(a / 1e6).toFixed(1)}M` : a >= 1e3 ? `${(a / 1e3).toFixed(1)}k` : a.toFixed(0);
  return `${v < 0 ? "-" : ""}${s}`;
}
export function titleCase(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
