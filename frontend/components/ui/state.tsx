"use client";

import { Loader2, TriangleAlert } from "lucide-react";
import * as React from "react";
import type { UseQueryResult } from "@tanstack/react-query";
import { cn } from "@/lib/utils";

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("animate-spin text-muted", className)} size={16} />;
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-md bg-surface-2", className)} />;
}

export function LoadingBlock({ label = "Loading…", height = "h-40" }: { label?: string; height?: string }) {
  return (
    <div className={cn("flex items-center justify-center gap-2 rounded-lg border border-border bg-surface text-muted", height)}>
      <Spinner /> <span className="text-[12px]">{label}</span>
    </div>
  );
}

export function ErrorBlock({ error }: { error: unknown }) {
  const message = error instanceof Error ? error.message : String(error);
  return (
    <div className="flex items-start gap-2 rounded-lg border border-down/40 bg-down/5 p-3 text-[12px] text-down">
      <TriangleAlert size={15} className="mt-0.5 shrink-0" />
      <div className="min-w-0 whitespace-pre-wrap break-words">{message}</div>
    </div>
  );
}

export function EmptyState({ children }: { children: React.ReactNode }) {
  return <div className="rounded-lg border border-dashed border-border p-6 text-center text-[12px] text-muted">{children}</div>;
}

/** Renders loading / error states for a react-query result, then calls children with data. */
export function Query<T>({
  q,
  children,
  label,
  height,
}: {
  q: Pick<UseQueryResult<T>, "data" | "isLoading" | "error" | "isFetching">;
  children: (data: T) => React.ReactNode;
  label?: string;
  height?: string;
}) {
  if (q.error) return <ErrorBlock error={q.error} />;
  if (q.isLoading || q.data === undefined) return <LoadingBlock label={label} height={height} />;
  return <>{children(q.data)}</>;
}
