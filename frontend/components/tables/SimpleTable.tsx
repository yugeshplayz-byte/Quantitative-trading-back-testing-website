"use client";

import { ArrowDown, ArrowUp } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface Column<T> {
  key: string;
  header: ReactNode;
  align?: "left" | "right" | "center";
  /** Cell renderer; defaults to the raw value. */
  render?: (row: T, index: number) => ReactNode;
  /** Value used for client sorting; defaults to row[key]. */
  sortValue?: (row: T) => number | string | null;
  /** Extra classes for the cell (e.g. colour by sign). */
  cellClass?: (row: T) => string | undefined;
  sortable?: boolean;
  className?: string;
}

export function SimpleTable<T extends object>({
  columns,
  rows,
  maxHeight,
  onRowClick,
  rowKey,
  empty = "No data",
  initialSort,
  footer,
}: {
  columns: Column<T>[];
  rows: T[];
  maxHeight?: string;
  onRowClick?: (row: T) => void;
  rowKey?: (row: T, i: number) => string | number;
  empty?: ReactNode;
  initialSort?: { key: string; dir: "asc" | "desc" };
  footer?: ReactNode;
}) {
  const [sort, setSort] = useState(initialSort ?? null);
  const sorted = useMemo(() => {
    if (!sort) return rows;
    const col = columns.find((c) => c.key === sort.key);
    if (!col) return rows;
    const val = (r: T) => (col.sortValue ? col.sortValue(r) : ((r as Record<string, unknown>)[col.key] as number | string | null));
    return [...rows].sort((a, b) => {
      const va = val(a), vb = val(b);
      if (va === vb) return 0;
      if (va === null || va === undefined) return 1;
      if (vb === null || vb === undefined) return -1;
      return (va < vb ? -1 : 1) * (sort.dir === "asc" ? 1 : -1);
    });
  }, [rows, sort, columns]);

  return (
    <div className="overflow-auto rounded-md border border-border" style={{ maxHeight }}>
      <table className="w-full border-collapse text-[12px]">
        <thead className="sticky top-0 z-10 bg-surface-2">
          <tr>
            {columns.map((c) => {
              const active = sort?.key === c.key;
              return (
                <th
                  key={c.key}
                  onClick={c.sortable === false ? undefined : () => setSort({ key: c.key, dir: active && sort?.dir === "desc" ? "asc" : "desc" })}
                  className={cn(
                    "whitespace-nowrap border-b border-border px-2 py-1.5 text-[10.5px] font-semibold uppercase tracking-wide text-muted",
                    c.align === "right" ? "text-right" : c.align === "center" ? "text-center" : "text-left",
                    c.sortable !== false && "cursor-pointer select-none hover:text-foreground",
                    c.className,
                  )}
                >
                  <span className="inline-flex items-center gap-0.5">
                    {c.header}
                    {active && (sort?.dir === "asc" ? <ArrowUp size={10} /> : <ArrowDown size={10} />)}
                  </span>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.length === 0 && (
            <tr>
              <td colSpan={columns.length} className="p-4 text-center text-muted">
                {empty}
              </td>
            </tr>
          )}
          {sorted.map((r, i) => (
            <tr
              key={rowKey ? rowKey(r, i) : i}
              onClick={onRowClick ? () => onRowClick(r) : undefined}
              className={cn("border-b border-border/50 last:border-0", onRowClick && "cursor-pointer hover:bg-surface-2")}
            >
              {columns.map((c) => (
                <td
                  key={c.key}
                  className={cn(
                    "num whitespace-nowrap px-2 py-1",
                    c.align === "right" ? "text-right" : c.align === "center" ? "text-center" : "text-left",
                    c.cellClass?.(r),
                    c.className,
                  )}
                >
                  {c.render ? c.render(r, i) : String((r as Record<string, unknown>)[c.key] ?? "–")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
        {footer && <tfoot>{footer}</tfoot>}
      </table>
    </div>
  );
}
