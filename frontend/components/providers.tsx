"use client";

import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { TooltipProvider } from "@radix-ui/react-tooltip";
import { useState, type ReactNode } from "react";
import { apiGet } from "@/lib/api";
import { BtCtx } from "@/lib/hooks";
import { useLocalValue } from "@/lib/store";
import type { BacktestResult } from "@/lib/types";

function BacktestProvider({ children }: { children: ReactNode }) {
  const [stored, setStored] = useLocalValue("qbt_selected_backtest", "BT-000001");
  const q = useQuery<BacktestResult[]>({ queryKey: ["backtests"], queryFn: () => apiGet("/backtests") });
  const list = q.data ?? [];
  const current = list.find((b) => b.id === stored) ?? list[0] ?? null;
  return (
    <BtCtx.Provider
      value={{
        id: current?.id ?? "",
        current,
        list,
        setId: setStored,
        loading: q.isLoading,
        error: q.error as Error | null,
      }}
    >
      {children}
    </BtCtx.Provider>
  );
}

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(
    () => new QueryClient({ defaultOptions: { queries: { staleTime: 60_000, retry: 0, refetchOnWindowFocus: false } } }),
  );
  return (
    <QueryClientProvider client={client}>
      <TooltipProvider delayDuration={150}>
        <BacktestProvider>{children}</BacktestProvider>
      </TooltipProvider>
    </QueryClientProvider>
  );
}
