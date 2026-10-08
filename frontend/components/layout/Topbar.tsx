"use client";

import { Menu } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Select } from "@/components/ui/inputs";
import { API_URL } from "@/lib/config";
import { useBt } from "@/lib/hooks";

export function Topbar({ onMenu }: { onMenu: () => void }) {
  const { id, current, list, setId, loading, error } = useBt();
  return (
    <header className="no-print flex h-12 shrink-0 items-center gap-3 border-b border-border bg-surface px-3">
      <button onClick={onMenu} className="rounded p-1 text-muted hover:bg-surface-2 md:hidden" aria-label="Open menu">
        <Menu size={18} />
      </button>
      <div className="flex min-w-0 items-center gap-2">
        <span className="hidden text-[11px] uppercase tracking-wide text-muted sm:inline">Backtest</span>
        <Select
          value={id}
          onChange={(e) => setId(e.target.value)}
          disabled={loading || list.length === 0}
          className="h-7 w-[min(360px,46vw)] text-[12px]"
          aria-label="Selected backtest"
        >
          {list.length === 0 && <option value="">{loading ? "Loading…" : "No backtests"}</option>}
          {list.map((b) => (
            <option key={b.id} value={b.id}>
              {b.id} · {b.name}
            </option>
          ))}
        </Select>
      </div>
      {current && (
        <div className="hidden items-center gap-1.5 lg:flex">
          <Badge>{current.symbol}</Badge>
          <Badge>{current.config.timeframe}</Badge>
          <Badge tone={current.config.data_model === "structured" ? "warn" : "neutral"}>
            {current.config.data_model === "structured" ? "engineered market" : "random walk"}
          </Badge>
          {current.tags.slice(0, 2).map((t) => (
            <Badge key={t}>{t}</Badge>
          ))}
        </div>
      )}
      <div className="ml-auto flex items-center gap-3 text-[11px] text-muted">
        <Link href="/backtest/configuration" className="rounded border border-border px-2 py-1 hover:bg-surface-2 hover:text-foreground">
          + New backtest
        </Link>
        <span className="hidden items-center gap-1.5 xl:flex" title={`API: ${API_URL || "not configured"}`}>
          <span className={"h-1.5 w-1.5 rounded-full " + (error ? "bg-down" : loading ? "bg-warn" : "bg-up")} />
          {error ? "API unreachable" : loading ? "Connecting" : "API connected"}
        </span>
      </div>
    </header>
  );
}
