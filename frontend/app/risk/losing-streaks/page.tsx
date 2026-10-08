"use client";

import { BarsChart } from "@/components/charts/BarsChart";
import { Heatmap } from "@/components/charts/Heatmap";
import { PageHeader } from "@/components/layout/PageHeader";
import { KpiCard, KpiGrid } from "@/components/metrics/KpiCard";
import { Panel } from "@/components/ui/card";
import { Query } from "@/components/ui/state";
import { money, num, pct } from "@/lib/format";
import { useBtQuery } from "@/lib/hooks";
import type { StreakData } from "@/lib/types-api";

interface Report {
  loss_probability: number; longest: number; count: number; average: number; worst_streak_losses: number[];
  median_longest_streak_250: number;
  probabilities: { loss_probability: number; rows: { trades: number; probabilities: { k: number; probability: number }[] }[] };
}

export default function LosingStreaksPage() {
  const q = useBtQuery<Report>("/losing-streaks");
  const s = useBtQuery<StreakData>("/analytics/streaks");
  return (
    <>
      <PageHeader title="Losing streaks" description="How long can a losing run last? Observed history, plus the probability of at least one run of k consecutive losses within n trades given this strategy's loss rate (exact run-length calculation, assuming independent trades). Know this number before you trade real money so a normal streak does not make you abandon the plan." />
      <Query q={q} height="h-64">
        {(r) => (
          <div className="space-y-4">
            <KpiGrid>
              <KpiCard label="Longest historical streak" value={String(r.longest)} tone="down" />
              <KpiCard label="Losing streaks (any length)" value={String(r.count)} />
              <KpiCard label="Average streak length" value={num(r.average)} />
              <KpiCard label="Loss rate per trade" value={pct(r.loss_probability)} />
              <KpiCard label="Typical worst streak in 250 trades" value={String(r.median_longest_streak_250)} sub="seen in ≥50% of 250-trade samples" tone="warn" />
              <KpiCard label="Worst streak cost" value={money(r.worst_streak_losses[0])} tone="down" />
            </KpiGrid>
            <Panel title="Probability of at least one losing streak of length k" subtitle="Rows = number of trades; columns = streak length. Based on the observed loss rate.">
              <Heatmap
                rows={r.probabilities.rows.map((x) => `${x.trades} trades`)}
                cols={r.probabilities.rows[0].probabilities.map((p) => `${p.k}+`)}
                values={r.probabilities.rows.map((x) => x.probabilities.map((p) => p.probability * 100))}
                format={(v) => `${v.toFixed(0)}%`}
                diverging={false}
                higherIsBetter={false}
                rowLabelWidth="w-24"
              />
            </Panel>
            <Query q={s} height="h-40">
              {(d) => (
                <div className="grid gap-4 xl:grid-cols-2">
                  <Panel title="Historical consecutive-loss distribution"><BarsChart data={d.loss_distribution as unknown as Record<string, number>[]} xKey="length" bars={[{ key: "count", label: "Occurrences", color: "#f6465d" }]} height={220} yFormat={(v) => v.toFixed(0)} /></Panel>
                  <Panel title="Worst losing streaks by dollars lost" bodyClassName="p-2">
                    <ol className="list-decimal space-y-1 pl-6 text-[12px]">{r.worst_streak_losses.map((v, i) => <li key={i} className="num text-down">{money(v)}</li>)}</ol>
                  </Panel>
                </div>
              )}
            </Query>
          </div>
        )}
      </Query>
    </>
  );
}
