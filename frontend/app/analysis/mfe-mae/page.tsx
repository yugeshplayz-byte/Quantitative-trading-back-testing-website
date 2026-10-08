"use client";

import { useMemo, useState } from "react";
import { ScatterPlot, type Group } from "@/components/charts/ScatterPlot";
import { PageHeader } from "@/components/layout/PageHeader";
import { KpiCard, KpiGrid } from "@/components/metrics/KpiCard";
import { Panel } from "@/components/ui/card";
import { Field, Select } from "@/components/ui/inputs";
import { Query } from "@/components/ui/state";
import { money, num } from "@/lib/format";
import { useBtQuery } from "@/lib/hooks";
import type { MfeMaeData } from "@/lib/types-api";

type By = "winner" | "direction" | "regime" | "setup";
const COLORS: Record<string, string> = { Winner: "#2ebd85", Loser: "#f6465d", Long: "#2ebd85", Short: "#f6465d" };

export default function MfeMaePage() {
  const q = useBtQuery<MfeMaeData>("/analytics/mfe-mae");
  const [by, setBy] = useState<By>("winner");

  const groups: Group[] = useMemo(() => {
    const pts = q.data?.points ?? [];
    const key = (p: MfeMaeData["points"][number]) => (by === "winner" ? (p.winner ? "Winner" : "Loser") : String(p[by]));
    const map = new Map<string, Group>();
    for (const p of pts) {
      const k = key(p);
      if (!map.has(k)) map.set(k, { name: k, color: COLORS[k], points: [] });
      map.get(k)!.points.push({ x: p.mae, y: p.mfe, id: p.id, net: p.net_pnl });
    }
    return [...map.values()];
  }, [q.data, by]);

  return (
    <>
      <PageHeader
        title="MFE / MAE"
        description="Each dot is one trade: how far it went against you (MAE, x) versus how far it went in your favour (MFE, y), in dollars for the initial position. Winners that reach high MFE then give it back suggest exit problems; winners with large MAE suggest stops that are too wide."
      />
      <Query q={q} height="h-96">
        {(d) => (
          <div className="space-y-4">
            <KpiGrid>
              <KpiCard label="Average MFE" value={money(d.stats.avg_mfe, 2)} tone="up" />
              <KpiCard label="Average MAE" value={money(d.stats.avg_mae, 2)} tone="down" />
              <KpiCard label="Winner MAE" value={money(d.stats.winner_mae, 2)} hint="How much winners went against you first" />
              <KpiCard label="Loser MAE" value={money(d.stats.loser_mae, 2)} />
              <KpiCard label="Winner MFE" value={money(d.stats.winner_mfe, 2)} />
              <KpiCard label="MFE capture" value={d.stats.mfe_capture === null ? "–" : `${num((d.stats.mfe_capture ?? 0) * 100, 0)}%`} hint="Average net P&L of winners / their MFE" />
            </KpiGrid>
            <Panel
              title="MAE vs MFE"
              actions={
                <Field label="Colour by" className="w-40">
                  <Select value={by} onChange={(e) => setBy(e.target.value as By)}>
                    <option value="winner">Winner / loser</option>
                    <option value="direction">Long / short</option>
                    <option value="regime">Regime</option>
                    <option value="setup">Setup</option>
                  </Select>
                </Field>
              }
            >
              <ScatterPlot groups={groups} xLabel="Maximum adverse excursion ($)" yLabel="Maximum favorable excursion ($)" xFormat={(v) => `$${v.toFixed(0)}`} yFormat={(v) => `$${v.toFixed(0)}`} height={420} />
              <p className="mt-2 text-[11px] text-muted">MAE/MFE use bar highs and lows against the initial entry. A stopped trade&apos;s MAE is capped at its fill price. Median MFE {money(d.stats.median_mfe, 2)} · median MAE {money(d.stats.median_mae, 2)} · correlation {num(d.stats.mae_mfe_corr)}.</p>
            </Panel>
          </div>
        )}
      </Query>
    </>
  );
}
