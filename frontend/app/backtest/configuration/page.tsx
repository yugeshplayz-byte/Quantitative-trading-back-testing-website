"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ConfigForm } from "@/components/backtest/ConfigForm";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/card";
import { ErrorBlock, Query, Spinner } from "@/components/ui/state";
import { Field, Input, Select } from "@/components/ui/inputs";
import { apiPost } from "@/lib/api";
import { useApiQuery, useBt } from "@/lib/hooks";
import type { BacktestConfig, BacktestResult, Strategy, StrategyPreset } from "@/lib/types";
import type { DatasetReport } from "@/lib/types-api";

interface Meta {
  strategies: Strategy[];
  default_config: BacktestConfig;
  custom_code: { enabled: boolean };
  real_data: { directory: string; datasets: DatasetReport[] };
}

export default function ConfigurationPage() {
  const meta = useApiQuery<Meta>("/meta");
  const presets = useApiQuery<StrategyPreset[]>("/strategies");
  return (
    <>
      <PageHeader
        title="Backtest configuration"
        description="Configure a strategy, risk, trade management and execution costs, then run it. Every run is saved as an experiment (BT-xxxxxx) with its seed and git commit."
      />
      <Query q={meta}>{(m) => <Editor meta={m} presets={presets.data ?? []} onPresetSaved={() => presets.refetch()} />}</Query>
    </>
  );
}

function Editor({ meta, presets, onPresetSaved }: { meta: Meta; presets: StrategyPreset[]; onPresetSaved: () => void }) {
  const router = useRouter();
  const qc = useQueryClient();
  const { setId } = useBt();
  const [cfg, setCfg] = useState<BacktestConfig>(meta.default_config);
  const [name, setName] = useState("");
  const [notes, setNotes] = useState("");
  const [presetName, setPresetName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [saved, setSaved] = useState<string | null>(null);

  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await apiPost<BacktestResult>("/backtest/run", { config: cfg, name: name || null, notes, version: "v1", tags: [] });
      await qc.invalidateQueries({ queryKey: ["backtests"] });
      setId(res.id);
      router.push("/");
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  const savePreset = async () => {
    if (!presetName.trim()) return;
    try {
      await apiPost("/strategies", { name: presetName.trim(), description: "", config: cfg, prop_rules: null });
      setSaved(`Saved "${presetName.trim()}"`);
      setPresetName("");
      onPresetSaved();
    } catch (e) {
      setError(e);
    }
  };

  const isCustom = cfg.strategy.startsWith("custom:");
  return (
    <div className="space-y-4">
      <Panel title="Run">
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Name (optional)" className="w-64">
            <Input value={name} placeholder="e.g. MNQ trend, wider stop" onChange={(e) => setName(e.target.value)} />
          </Field>
          <Field label="Notes" className="w-72">
            <Input value={notes} onChange={(e) => setNotes(e.target.value)} />
          </Field>
          <Field label="Load saved strategy" className="w-56">
            <Select
              value=""
              onChange={(e) => {
                const p = presets.find((x) => String(x.id) === e.target.value);
                if (p) setCfg({ ...meta.default_config, ...p.config });
              }}
            >
              <option value="">Choose…</option>
              {presets.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </Select>
          </Field>
          <Button variant="primary" onClick={run} disabled={busy}>
            {busy ? <Spinner className="text-white" /> : null}
            {busy ? (isCustom ? "Running in sandbox…" : "Running…") : "Run backtest"}
          </Button>
        </div>
        <div className="mt-3 flex flex-wrap items-end gap-3 border-t border-border pt-3">
          <Field label="Save current settings as preset" className="w-64">
            <Input value={presetName} placeholder="e.g. MNQ Trend V3" onChange={(e) => setPresetName(e.target.value)} />
          </Field>
          <Button onClick={savePreset} disabled={!presetName.trim()}>
            Save preset
          </Button>
          {saved && <span className="text-[12px] text-up">{saved}</span>}
        </div>
        {error ? <div className="mt-3"><ErrorBlock error={error} /></div> : null}
      </Panel>
      <ConfigForm value={cfg} onChange={setCfg} strategies={meta.strategies} datasets={meta.real_data.datasets} />
    </div>
  );
}
