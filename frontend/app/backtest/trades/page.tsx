"use client";

import { useQuery } from "@tanstack/react-query";
import { createColumnHelper, flexRender, getCoreRowModel, useReactTable, type SortingState } from "@tanstack/react-table";
import { ArrowDown, ArrowUp, Download } from "lucide-react";
import { useMemo, useState } from "react";
import { TradeViewer } from "@/components/backtest/TradeViewer";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/card";
import { Field, Input, Select } from "@/components/ui/inputs";
import { ErrorBlock, LoadingBlock } from "@/components/ui/state";
import { apiGet, apiUrl } from "@/lib/api";
import { money, num, pnlClass, signedMoney } from "@/lib/format";
import { useBt, useBtQuery } from "@/lib/hooks";
import { cn } from "@/lib/utils";

interface Row {
  id: string; symbol: string; date: string; entry_time: string; exit_time: string; direction: "Long" | "Short";
  entry_price: number; exit_price: number; quantity: number; stop: number; target: number | null;
  gross_pnl: number; fees: number; slippage: number; net_pnl: number; r_multiple: number; mae: number; mfe: number;
  duration_minutes: number; regime: string; setup: string; confidence: number; exit_reason: string;
}
interface Page { total: number; page: number; page_size: number; rows: Row[]; summary: { net_pnl: number; winners: number } }
interface Facets { symbols: string[]; setups: string[]; regimes: string[]; exit_reasons: string[]; time_buckets: string[]; weekdays: string[] }

const col = createColumnHelper<Row>();
const t = (s: string) => s.slice(11, 16);
const columns = [
  col.accessor("id", { header: "Trade ID" }),
  col.accessor("symbol", { header: "Symbol" }),
  col.accessor("date", { header: "Date" }),
  col.accessor("entry_time", { header: "Entry", cell: (c) => t(c.getValue()) }),
  col.accessor("exit_time", { header: "Exit", cell: (c) => t(c.getValue()) }),
  col.accessor("direction", { header: "Dir", cell: (c) => <span className={c.getValue() === "Long" ? "text-up" : "text-down"}>{c.getValue()}</span> }),
  col.accessor("entry_price", { header: "Entry px", cell: (c) => num(c.getValue()) }),
  col.accessor("exit_price", { header: "Exit px", cell: (c) => num(c.getValue()) }),
  col.accessor("quantity", { header: "Qty" }),
  col.accessor("stop", { header: "Stop", cell: (c) => num(c.getValue()) }),
  col.accessor("target", { header: "Target", cell: (c) => (c.getValue() === null ? "–" : num(c.getValue())) }),
  col.accessor("gross_pnl", { header: "Gross P&L", cell: (c) => <span className={pnlClass(c.getValue())}>{signedMoney(c.getValue(), 2)}</span> }),
  col.accessor("fees", { header: "Fees", cell: (c) => money(c.getValue(), 2) }),
  col.accessor("slippage", { header: "Slippage", cell: (c) => money(c.getValue(), 2) }),
  col.accessor("net_pnl", { header: "Net P&L", cell: (c) => <span className={cn("font-semibold", pnlClass(c.getValue()))}>{signedMoney(c.getValue(), 2)}</span> }),
  col.accessor("r_multiple", { header: "R", cell: (c) => num(c.getValue()) }),
  col.accessor("mae", { header: "MAE", cell: (c) => money(c.getValue(), 0) }),
  col.accessor("mfe", { header: "MFE", cell: (c) => money(c.getValue(), 0) }),
  col.accessor("duration_minutes", { header: "Duration", cell: (c) => `${Math.round(c.getValue())}m` }),
  col.accessor("regime", { header: "Regime" }),
  col.accessor("setup", { header: "Setup" }),
  col.accessor("confidence", { header: "Conf", cell: (c) => num(c.getValue(), 0) }),
];

const EMPTY = {
  date_from: "", date_to: "", result: "", direction: "", symbol: "", setup: "", regime: "", time_of_day: "", day_of_week: "",
  min_profit: "", max_profit: "", min_loss: "", max_loss: "", min_duration: "", max_duration: "",
};
type Filters = typeof EMPTY;

export default function TradesPage() {
  const { id } = useBt();
  const facets = useBtQuery<Facets>("/facets");
  const [filters, setFilters] = useState<Filters>(EMPTY);
  const [sorting, setSorting] = useState<SortingState>([{ id: "entry_time", desc: false }]);
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  const pageSize = 50;

  const qs = useMemo(() => {
    const p = new URLSearchParams();
    Object.entries(filters).forEach(([k, v]) => v !== "" && p.set(k, v));
    return p;
  }, [filters]);
  const sort = sorting[0];
  const path = useMemo(() => {
    const p = new URLSearchParams(qs);
    p.set("sort_by", sort?.id ?? "entry_time");
    p.set("sort_dir", sort?.desc ? "desc" : "asc");
    p.set("page", String(page));
    p.set("page_size", String(pageSize));
    return `/backtests/${id}/trades?${p.toString()}`;
  }, [qs, sort, page, id]);
  const q = useQuery<Page>({ queryKey: ["trades", path], queryFn: () => apiGet<Page>(path), enabled: Boolean(id), placeholderData: (prev) => prev });

  const data = useMemo(() => q.data?.rows ?? [], [q.data]);
  // TanStack Table is not memoisable by the React Compiler; the compiler simply skips this component.
  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({
    data,
    columns,
    state: { sorting },
    manualSorting: true,
    manualPagination: true,
    onSortingChange: (u) => {
      setSorting(u);
      setPage(1);
    },
    getCoreRowModel: getCoreRowModel(),
  });
  const set = (k: keyof Filters, v: string) => {
    setFilters((f) => ({ ...f, [k]: v }));
    setPage(1);
  };
  const total = q.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const f = facets.data;

  return (
    <>
      <PageHeader
        title="Trade explorer"
        description="Sort and filter every trade. Click a row for the trade chart with entry, exit, stop, target, VWAP and EMAs."
        actions={
          <Button asChild variant="secondary" size="sm">
            <a href={apiUrl(`/backtests/${id}/trades?${new URLSearchParams({ ...Object.fromEntries(qs), format: "csv", sort_by: sort?.id ?? "entry_time", sort_dir: sort?.desc ? "desc" : "asc" }).toString()}`)}>
              <Download size={13} /> Export CSV
            </a>
          </Button>
        }
      />
      <Panel title="Filters" className="mb-4" actions={<Button size="sm" variant="ghost" onClick={() => { setFilters(EMPTY); setPage(1); }}>Reset</Button>}>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6">
          <Field label="From"><Input type="date" value={filters.date_from} onChange={(e) => set("date_from", e.target.value)} /></Field>
          <Field label="To"><Input type="date" value={filters.date_to} onChange={(e) => set("date_to", e.target.value)} /></Field>
          <Field label="Result">
            <Select value={filters.result} onChange={(e) => set("result", e.target.value)}>
              <option value="">All</option><option value="winner">Winners</option><option value="loser">Losers</option>
            </Select>
          </Field>
          <Field label="Direction">
            <Select value={filters.direction} onChange={(e) => set("direction", e.target.value)}>
              <option value="">Long & short</option><option>Long</option><option>Short</option>
            </Select>
          </Field>
          <Field label="Symbol"><Select value={filters.symbol} onChange={(e) => set("symbol", e.target.value)}><option value="">All</option>{f?.symbols.map((s) => <option key={s}>{s}</option>)}</Select></Field>
          <Field label="Setup"><Select value={filters.setup} onChange={(e) => set("setup", e.target.value)}><option value="">All</option>{f?.setups.map((s) => <option key={s}>{s}</option>)}</Select></Field>
          <Field label="Regime"><Select value={filters.regime} onChange={(e) => set("regime", e.target.value)}><option value="">All</option>{f?.regimes.map((s) => <option key={s}>{s}</option>)}</Select></Field>
          <Field label="Time of day"><Select value={filters.time_of_day} onChange={(e) => set("time_of_day", e.target.value)}><option value="">All</option>{f?.time_buckets.map((s) => <option key={s}>{s}</option>)}</Select></Field>
          <Field label="Day of week"><Select value={filters.day_of_week} onChange={(e) => set("day_of_week", e.target.value)}><option value="">All</option>{f?.weekdays.map((s) => <option key={s}>{s}</option>)}</Select></Field>
          <Field label="Profit ≥ ($)"><Input type="number" value={filters.min_profit} onChange={(e) => set("min_profit", e.target.value)} /></Field>
          <Field label="Profit ≤ ($)"><Input type="number" value={filters.max_profit} onChange={(e) => set("max_profit", e.target.value)} /></Field>
          <Field label="Loss at least ($)"><Input type="number" value={filters.min_loss} onChange={(e) => set("min_loss", e.target.value)} /></Field>
          <Field label="Loss at most ($)"><Input type="number" value={filters.max_loss} onChange={(e) => set("max_loss", e.target.value)} /></Field>
          <Field label="Duration ≥ (min)"><Input type="number" value={filters.min_duration} onChange={(e) => set("min_duration", e.target.value)} /></Field>
          <Field label="Duration ≤ (min)"><Input type="number" value={filters.max_duration} onChange={(e) => set("max_duration", e.target.value)} /></Field>
        </div>
      </Panel>

      {q.error ? <ErrorBlock error={q.error} /> : !q.data ? <LoadingBlock label="Loading trades…" height="h-64" /> : (
        <Panel
          title={`${total.toLocaleString()} trades`}
          subtitle={`Filtered net P&L ${signedMoney(q.data.summary.net_pnl)} · ${q.data.summary.winners} winners`}
          bodyClassName="p-0"
          actions={
            <div className="flex items-center gap-2 text-[11px] text-muted">
              <Button size="sm" variant="secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>Prev</Button>
              <span className="num">{page} / {pages}</span>
              <Button size="sm" variant="secondary" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</Button>
            </div>
          }
        >
          <div className="max-h-[560px] overflow-auto">
            <table className="w-full border-collapse text-[12px]">
              <thead className="sticky top-0 z-10 bg-surface-2">
                {table.getHeaderGroups().map((hg) => (
                  <tr key={hg.id}>
                    {hg.headers.map((h) => {
                      const dir = h.column.getIsSorted();
                      return (
                        <th key={h.id} onClick={h.column.getToggleSortingHandler()} className="cursor-pointer select-none whitespace-nowrap border-b border-border px-2 py-1.5 text-left text-[10.5px] font-semibold uppercase tracking-wide text-muted hover:text-foreground">
                          <span className="inline-flex items-center gap-0.5">
                            {flexRender(h.column.columnDef.header, h.getContext())}
                            {dir === "asc" ? <ArrowUp size={10} /> : dir === "desc" ? <ArrowDown size={10} /> : null}
                          </span>
                        </th>
                      );
                    })}
                  </tr>
                ))}
              </thead>
              <tbody>
                {table.getRowModel().rows.map((r) => (
                  <tr key={r.id} onClick={() => setSelected(r.original.id)} className="cursor-pointer border-b border-border/50 hover:bg-surface-2">
                    {r.getVisibleCells().map((c) => (
                      <td key={c.id} className="num whitespace-nowrap px-2 py-1">{flexRender(c.column.columnDef.cell, c.getContext())}</td>
                    ))}
                  </tr>
                ))}
                {data.length === 0 && <tr><td colSpan={columns.length} className="p-6 text-center text-muted">No trades match these filters.</td></tr>}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
      <TradeViewer tradeId={selected} onClose={() => setSelected(null)} />
    </>
  );
}
