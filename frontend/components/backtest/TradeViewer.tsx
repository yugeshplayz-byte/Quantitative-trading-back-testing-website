"use client";

import { useState } from "react";
import { CandleChart, type CandleBar, type Marker } from "@/components/charts/CandleChart";
import { StatTable } from "@/components/metrics/StatTable";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { ToggleField } from "@/components/ui/inputs";
import { Query } from "@/components/ui/state";
import { duration, money, num, signedMoney } from "@/lib/format";
import { useBtQuery } from "@/lib/hooks";
import type { Trade } from "@/lib/types";

interface ChartData {
  trade: Trade;
  bars: CandleBar[];
  stop_path: { t: string; price: number }[];
  levels: { entry: number; exit: number; stop: number; target: number | null };
  events: Marker[];
}

export function TradeViewer({ tradeId, onClose }: { tradeId: string | null; onClose: () => void }) {
  return (
    <Dialog open={tradeId !== null} onOpenChange={(o) => !o && onClose()}>
      <DialogContent title={tradeId ? `Trade ${tradeId}` : "Trade"} description="Entry, exit, stop, target and management events. Hover the chart for OHLC.">
        {tradeId && <Body id={tradeId} />}
      </DialogContent>
    </Dialog>
  );
}

function Body({ id }: { id: string }) {
  const q = useBtQuery<ChartData>(`/trades/${id}/chart`);
  const [vwap, setVwap] = useState(true);
  const [ema, setEma] = useState(true);
  return (
    <Query q={q} label="Loading trade chart…" height="h-80">
      {(d) => {
        const t = d.trade;
        return (
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_280px]">
            <div className="min-w-0">
              <div className="mb-2 flex flex-wrap items-center gap-2 text-[11px]">
                <Badge tone={t.direction === "Long" ? "up" : "down"}>{t.direction}</Badge>
                <Badge>{t.symbol}</Badge>
                <Badge tone="accent">{t.setup}</Badge>
                <Badge>{t.regime}</Badge>
                <span className="ml-auto flex items-center gap-3 text-muted">
                  <Legend color="#a371f7" label="VWAP" />
                  <Legend color="#4c8dff" label="EMA 9" />
                  <Legend color="#f0b429" label="EMA 21" />
                  <Legend color="#f6465d" label="Stop" />
                  <Legend color="#2ebd85" label="Target" />
                </span>
              </div>
              <CandleChart
                bars={d.bars}
                entryTime={t.entry_time}
                exitTime={t.exit_time}
                direction={t.direction}
                levels={d.levels}
                stopPath={d.stop_path}
                events={d.events}
                show={{ vwap, ema }}
              />
              <div className="mt-2 grid max-w-md grid-cols-2 gap-2">
                <ToggleField label="VWAP" checked={vwap} onChange={setVwap} />
                <ToggleField label="EMAs" checked={ema} onChange={setEma} />
              </div>
              {d.events.length > 0 && (
                <p className="mt-2 text-[11px] text-muted">
                  Events: {d.events.map((e) => `${e.kind.replace("_", " ")} @ ${e.price} (${e.time.slice(11, 16)})`).join(" · ")}
                </p>
              )}
            </div>
            <div className="space-y-3">
              <StatTable
                rows={[
                  { label: "Gross P&L", value: signedMoney(t.gross_pnl, 2), tone: t.gross_pnl >= 0 ? "up" : "down" },
                  { label: "Commission & fees", value: money(t.fees, 2) },
                  { label: "Slippage", value: money(t.slippage, 2) },
                  { label: "Net P&L", value: signedMoney(t.net_pnl, 2), tone: t.net_pnl >= 0 ? "up" : "down" },
                  { label: "R multiple", value: num(t.r_multiple, 2) },
                  { label: "MAE", value: `${money(t.mae, 2)} (${num(t.mae_points)} pts)` },
                  { label: "MFE", value: `${money(t.mfe, 2)} (${num(t.mfe_points)} pts)` },
                  { label: "Duration", value: duration(t.duration_minutes) },
                  { label: "Quantity", value: t.quantity },
                  { label: "Initial risk", value: money(t.risk_dollars, 2) },
                  { label: "Confidence", value: num(t.confidence, 0) },
                  { label: "ATR percentile", value: num(t.atr_percentile, 0) },
                ]}
              />
              <div className="rounded-md border border-border p-2 text-[11.5px]">
                <div className="text-muted">Entry reason</div>
                <div>{t.entry_reason}</div>
                <div className="mt-1.5 text-muted">Exit reason</div>
                <div>{t.exit_reason}</div>
                <div className="mt-1.5 text-muted">Regime (known at signal time)</div>
                <div>{t.regime}</div>
              </div>
            </div>
          </div>
        );
      }}
    </Query>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1">
      <span className="h-0.5 w-3" style={{ background: color }} />
      {label}
    </span>
  );
}
