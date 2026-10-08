"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { createContext, useContext } from "react";
import { apiGet, apiPost, ApiError } from "./api";
import type { BacktestResult } from "./types";

// ------------------------------------------------------------------ selected backtest
export interface BtContext {
  id: string;
  current: BacktestResult | null;
  list: BacktestResult[];
  setId: (id: string) => void;
  loading: boolean;
  error: Error | null;
}

export const BtCtx = createContext<BtContext | null>(null);

export function useBt(): BtContext {
  const ctx = useContext(BtCtx);
  if (!ctx) throw new Error("useBt must be used inside <Providers>");
  return ctx;
}

// ------------------------------------------------------------------ queries
/** GET /backtests/{selected}{suffix}; waits for a selected backtest. */
export function useBtQuery<T>(suffix: string, enabled = true) {
  const { id } = useBt();
  return useQuery<T, ApiError>({
    queryKey: ["bt", id, suffix],
    queryFn: () => apiGet<T>(`/backtests/${id}${suffix}`),
    enabled: enabled && Boolean(id),
  });
}

export function useApiQuery<T>(path: string, enabled = true) {
  return useQuery<T, ApiError>({ queryKey: ["api", path], queryFn: () => apiGet<T>(path), enabled });
}

/**
 * POST computation keyed by its request body. Results are cached by react-query, so re-running the same
 * parameters is instant. Pass `body = null` to hold off (nothing runs until the user presses Run).
 */
export function usePostQuery<Res>(path: string, body: unknown | null) {
  return useQuery<Res, ApiError>({
    queryKey: ["post", path, body],
    queryFn: () => apiPost<Res>(path, body),
    enabled: body !== null,
    staleTime: 10 * 60_000,
  });
}

/** One-shot computation triggered by a button (POST). */
export function useRunner<Req, Res>(path: string) {
  const m = useMutation<Res, ApiError, Req>({ mutationFn: (body) => apiPost<Res>(path, body) });
  return { run: m.mutate, runAsync: m.mutateAsync, data: m.data, pending: m.isPending, error: m.error, reset: m.reset };
}
