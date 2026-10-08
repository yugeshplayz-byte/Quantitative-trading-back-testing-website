"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { EdgeVerdict } from "@/components/metrics/EdgeVerdict";
import { SimpleTable } from "@/components/tables/SimpleTable";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/card";
import { Field, Input, NumberField, Select, Textarea } from "@/components/ui/inputs";
import { ErrorBlock, Query, Spinner } from "@/components/ui/state";
import { ApiError, apiDelete, apiGet, apiPost, apiPut, getAdminToken, setAdminToken } from "@/lib/api";
import { useApiQuery, useBt } from "@/lib/hooks";
import type { BacktestConfig, BacktestResult, DataModel, ParameterSpec } from "@/lib/types";

interface Meta { custom_code: { enabled: boolean; token_required: boolean }; default_config: BacktestConfig }
interface Template { id: string; name: string; description: string; code: string }
interface Saved { id: number; key: string; name: string; description: string; code: string; parameters: ParameterSpec[] }
interface Validation { ok: boolean; problems?: string[]; traceback?: string; parameters?: ParameterSpec[]; signal_mode?: string; has_fit?: boolean; smoke_signals?: number; seconds?: number }

export default function StrategyLabPage() {
  const meta = useApiQuery<Meta>("/meta");
  return (
    <>
      <PageHeader title="Strategy Lab" description="Paste your own Python strategy - including machine-learning models - and backtest it with the same engine, costs and honesty checks as the built-in strategies." />
      <Query q={meta}>{(m) => (m.custom_code.enabled ? <Lab meta={m} /> : <Disabled />)}</Query>
    </>
  );
}

function Disabled() {
  return (
    <Panel title="Custom strategy execution is turned off on this server">
      <div className="space-y-2 text-[12.5px]">
        <p>Running pasted Python means <b>executing arbitrary code on the machine that hosts the backend</b>. It is disabled by default so a public deployment can never be used to run someone else&apos;s code.</p>
        <p>To use it on your own computer, set this in <code className="num">backend/.env</code> and restart the backend:</p>
        <pre className="num rounded-md border border-border bg-background p-2">ENABLE_CUSTOM_CODE=true</pre>
        <p className="text-muted">For a hosted deployment that only you can reach, also set <code className="num">CUSTOM_CODE_TOKEN</code> to a long random value; the Strategy Lab will then ask for it. Never enable custom code on an open public server. See the README security section.</p>
      </div>
    </Panel>
  );
}

function Lab({ meta }: { meta: Meta }) {
  const qc = useQueryClient();
  const { setId } = useBt();
  const [token, setToken] = useState(getAdminToken());
  const templates = useApiQuery<Template[]>("/custom-strategies/templates");
  const saved = useQuery<Saved[], ApiError>({ queryKey: ["custom", token], queryFn: () => apiGet<Saved[]>("/custom-strategies") });

  const [name, setName] = useState("My strategy");
  const [description, setDescription] = useState("");
  const [code, setCode] = useState("");
  const [loadedId, setLoadedId] = useState<number | null>(null);
  const [validation, setValidation] = useState<Validation | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);

  const [run, setRun] = useState({ symbol: "MNQ", start: "2023-01-02", end: "2024-12-31", risk: 150, model: "random_walk" as DataModel });
  const [result, setResult] = useState<BacktestResult | null>(null);

  const load = (s: { name: string; description: string; code: string }, id: number | null) => {
    setName(s.name); setDescription(s.description); setCode(s.code); setLoadedId(id); setValidation(null); setResult(null); setError(null);
  };
  const act = async (label: string, fn: () => Promise<void>) => {
    setBusy(label); setError(null);
    try { await fn(); } catch (e) { setError(e); } finally { setBusy(null); }
  };

  const validate = () => act("validate", async () => setValidation(await apiPost<Validation>("/custom-strategies/validate", { name, description, code })));
  const persist = async (): Promise<Saved> => {
    const body = { name, description, code };
    const s = loadedId !== null ? await apiPut<Saved>(`/custom-strategies/${loadedId}`, body) : await apiPost<Saved>("/custom-strategies", body);
    setLoadedId(s.id);
    await qc.invalidateQueries({ queryKey: ["custom"] });
    await qc.invalidateQueries({ queryKey: ["api", "/meta"] });
    return s;
  };
  const save = () => act("save", async () => {
    const s = await persist();
    setLoadedId(s.id);
    await qc.invalidateQueries({ queryKey: ["custom"] });
    await qc.invalidateQueries({ queryKey: ["api", "/meta"] });
    setValidation({ ok: true, parameters: s.parameters });
  });
  const remove = () => act("delete", async () => {
    if (loadedId === null || !window.confirm(`Delete "${name}"?`)) return;
    await apiDelete(`/custom-strategies/${loadedId}`);
    setLoadedId(null);
    await qc.invalidateQueries({ queryKey: ["custom"] });
  });
  const backtest = () => act("run", async () => {
    const { id } = await persist(); // always run exactly the code that is in the editor
    const cfg: BacktestConfig = { ...meta.default_config, strategy: `custom:${id}`, symbol: run.symbol as BacktestConfig["symbol"], start_date: run.start, end_date: run.end, data_model: run.model, risk: { ...meta.default_config.risk, risk_dollars: run.risk } };
    const res = await apiPost<BacktestResult>("/backtest/run", { config: cfg, name: `${name} (${run.symbol})`, notes: "Custom strategy from the Strategy Lab", version: "v1", tags: ["custom"] });
    await qc.invalidateQueries({ queryKey: ["backtests"] });
    setId(res.id);
    setResult(res);
  });

  const trainDays = Math.max(0, Math.round((new Date(run.start).getTime() - new Date("2022-01-03").getTime()) / 86400000 * 5 / 7));
  const tokenNeeded = meta.custom_code.token_required && !token;

  return (
    <div className="space-y-4">
      {meta.custom_code.token_required && (
        <Panel title="Access token">
          <div className="flex items-end gap-3">
            <Field label="X-Admin-Token (this server requires one)" className="w-96"><Input type="password" value={token} onChange={(e) => setToken(e.target.value)} /></Field>
            <Button onClick={() => { setAdminToken(token); qc.invalidateQueries({ queryKey: ["custom"] }); }}>Use token</Button>
            <span className="text-[11px] text-muted">Kept in this tab&apos;s session storage only.</span>
          </div>
        </Panel>
      )}
      <div className="rounded-lg border border-warn/40 bg-warn/5 p-3 text-[12px] text-warn">
        Your code runs on the machine hosting the backend, in a separate process with a time limit and no access to the server&apos;s secrets, but Python cannot be perfectly sandboxed. Only run code you wrote or fully trust, and only on a machine you control.
      </div>
      {tokenNeeded ? null : (
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
          <div className="min-w-0 space-y-4">
            <Panel
              title="Strategy code"
              actions={
                <Select value="" className="h-7 w-56" onChange={(e) => { const t = templates.data?.find((x) => x.id === e.target.value); if (t) load({ name: t.name.replace(/^[^:]*: /, ""), description: t.description, code: t.code }, null); }}>
                  <option value="">Start from a template…</option>
                  {templates.data?.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                </Select>
              }
            >
              <div className="mb-3 grid grid-cols-2 gap-3">
                <Field label="Name"><Input className="font-sans" value={name} onChange={(e) => setName(e.target.value)} /></Field>
                <Field label="Description"><Input className="font-sans" value={description} onChange={(e) => setDescription(e.target.value)} /></Field>
              </div>
              <Textarea
                value={code}
                onChange={(e) => setCode(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Tab") {
                    e.preventDefault();
                    const t = e.currentTarget, s = t.selectionStart;
                    setCode(code.slice(0, s) + "    " + code.slice(t.selectionEnd));
                    requestAnimationFrame(() => { t.selectionStart = t.selectionEnd = s + 4; });
                  }
                }}
                rows={30}
                spellCheck={false}
                placeholder={"# Paste your strategy here, or pick a template above.\n# It must define:  class Strategy:  def signals(self, bars): ..."}
                className="w-full text-[12px] leading-relaxed"
              />
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <Button onClick={validate} disabled={!code.trim() || busy !== null}>{busy === "validate" && <Spinner />} Validate</Button>
                <Button onClick={save} disabled={!code.trim() || !name.trim() || busy !== null}>{busy === "save" && <Spinner />} {loadedId ? "Save changes" : "Save strategy"}</Button>
                {loadedId !== null && <Button variant="danger" onClick={remove} disabled={busy !== null}>Delete</Button>}
                <span className="text-[11px] text-muted">{code.split("\n").length} lines{loadedId ? ` · saved as custom:${loadedId}` : " · not saved yet"}</span>
              </div>
              {error ? <div className="mt-3"><ErrorBlock error={error} /></div> : null}
              {validation && (
                <div className={"mt-3 rounded-md border p-3 text-[12px] " + (validation.ok ? "border-up/40 bg-up/5" : "border-down/40 bg-down/5")}>
                  {validation.ok ? (
                    <>
                      <div className="font-semibold text-up">Valid.{validation.signal_mode ? ` Signal mode: ${validation.signal_mode}.` : ""}{validation.has_fit ? " Has fit() - trained on pre-test data only." : ""}{validation.smoke_signals !== undefined ? ` ${validation.smoke_signals} signals on a smoke run.` : ""}</div>
                      {validation.parameters && validation.parameters.length > 0 && (
                        <div className="mt-2"><SimpleTable rows={validation.parameters} columns={[{ key: "key", header: "Parameter" }, { key: "default", header: "Default", align: "right" }, { key: "min", header: "Min", align: "right" }, { key: "max", header: "Max", align: "right" }, { key: "step", header: "Step", align: "right" }]} /></div>
                      )}
                    </>
                  ) : (
                    <>
                      <div className="font-semibold text-down">Not valid</div>
                      <ul className="mt-1 list-disc pl-5">{(validation.problems ?? []).map((p, i) => <li key={i}>{p}</li>)}</ul>
                      {validation.traceback && <pre className="num mt-2 overflow-auto rounded border border-border bg-background p-2 text-[11px]">{validation.traceback}</pre>}
                    </>
                  )}
                </div>
              )}
            </Panel>

            <Panel title="Backtest this strategy" subtitle="Runs through the same engine, fills and costs as every other strategy. Models are trained ONLY on bars before the start date.">
              <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
                <Field label="Symbol"><Select value={run.symbol} onChange={(e) => setRun({ ...run, symbol: e.target.value })}>{["MNQ", "NQ", "MES", "ES"].map((s) => <option key={s}>{s}</option>)}</Select></Field>
                <Field label="Start (test begins)"><Input type="date" value={run.start} min="2022-03-01" onChange={(e) => setRun({ ...run, start: e.target.value })} /></Field>
                <Field label="End"><Input type="date" value={run.end} max="2025-12-31" onChange={(e) => setRun({ ...run, end: e.target.value })} /></Field>
                <NumberField label="Risk per trade ($)" value={run.risk} step={25} min={1} onChange={(v) => setRun({ ...run, risk: v ?? 150 })} />
                <Field label="Market model"><Select value={run.model} onChange={(e) => setRun({ ...run, model: e.target.value as DataModel })}><option value="real">Real data (your CSV)</option><option value="random_walk">Random walk (no edge)</option><option value="structured">Engineered edge (validation)</option></Select></Field>
              </div>
              <p className="mt-2 text-[11px] text-muted">Training history available before the start date: about {trainDays} trading days{trainDays < 150 ? " - short; an ML model may be badly under-trained" : ""}. On the default random-walk market a sound strategy should NOT be profitable - if yours is, suspect a bug or leakage before celebrating.</p>
              <div className="mt-3 flex items-center gap-3">
                <Button variant="primary" onClick={backtest} disabled={!code.trim() || !name.trim() || busy !== null}>{busy === "run" && <Spinner className="text-white" />} {busy === "run" ? "Training & running in sandbox…" : "Save & run backtest"}</Button>
                <span className="text-[11px] text-muted">ML strategies can take 10–60 seconds (includes the lookahead check).</span>
              </div>
              {result && (
                <div className="mt-4 space-y-3">
                  {result.meta.lookahead && (
                    <div className={"rounded-md border p-3 text-[12px] " + (result.meta.lookahead.status === "ok" ? "border-up/40 bg-up/5" : result.meta.lookahead.status === "suspect" ? "border-down/40 bg-down/5 text-down" : "border-warn/40 bg-warn/5 text-warn")}>
                      <b>Lookahead check: {result.meta.lookahead.status.toUpperCase()}.</b> {result.meta.lookahead.message}
                    </div>
                  )}
                  <EdgeVerdict metrics={result.metrics} />
                  <div className="flex gap-2">
                    <Button asChild variant="primary" size="sm"><Link href="/">Open dashboard ({result.id})</Link></Button>
                    <Button asChild size="sm"><Link href="/robustness/overfitting">Robustness & overfitting</Link></Button>
                    <Button asChild size="sm"><Link href="/robustness/walk-forward">Walk-forward</Link></Button>
                  </div>
                </div>
              )}
            </Panel>
          </div>

          <div className="space-y-4">
            <Panel title="Saved strategies" bodyClassName="p-2">
              <Query q={saved} height="h-20">
                {(rows) => rows.length === 0 ? <p className="p-2 text-[12px] text-muted">None yet. Pick a template and save it.</p> : (
                  <ul className="divide-y divide-border">
                    {rows.map((s) => (
                      <li key={s.id}>
                        <button onClick={async () => { const full = await apiGet<Saved>(`/custom-strategies/${s.id}`); load(full, s.id); }} className={"w-full px-2 py-1.5 text-left hover:bg-surface-2 " + (s.id === loadedId ? "bg-surface-2" : "")}>
                          <div className="text-[12.5px]">{s.name} {s.id === loadedId && <Badge tone="accent">open</Badge>}</div>
                          <div className="text-[11px] text-muted">{s.key} · {s.parameters.length} parameters</div>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </Query>
            </Panel>
            <Panel title="The contract">
              <pre className="num overflow-auto rounded-md border border-border bg-background p-2 text-[11px] leading-relaxed">{`class Strategy:
    params = {"lookback": 20}      # tunable numbers

    def fit(self, train_bars):     # optional (ML)
        ...                        # sees ONLY bars
                                   # before the start date

    def signals(self, bars):
        # return DataFrame, one row per bar:
        #   side        +1 long / -1 short / 0
        #   confidence  optional (0-1 or 0-100)
        #   setup       optional label
        #   exit_long / exit_short  optional bools
        ...`}</pre>
              <p className="mt-2 text-[11.5px] text-muted">bars columns: ts, date, open, high, low, close, volume, tod (minutes since 09:30), day_id, atr, vwap. A signal on a bar is acted on at the NEXT bar&apos;s open. Set <code className="num">signal_mode = &quot;position&quot;</code> if you return a desired position every bar instead of entry events. Allowed imports: numpy, pandas, scipy, sklearn, statsmodels, xgboost, lightgbm, torch, math, and the standard-library basics.</p>
            </Panel>
            <Panel title="Keeping ML honest">
              <ul className="list-disc space-y-1.5 pl-4 text-[11.5px] text-muted">
                <li><b className="text-foreground/90">Never use future data.</b> Labels like <code className="num">close.shift(-h)</code> are fine ONLY inside <code className="num">fit()</code>, on train bars. In <code className="num">signals()</code> use past data only.</li>
                <li>Do not scale or normalise with statistics from the whole series. Fit scalers inside <code className="num">fit()</code>.</li>
                <li>Set random seeds (<code className="num">random_state=0</code>) so results and the lookahead check are reproducible.</li>
                <li>The lookahead check truncates the data at five points and flags signals that change. It is a strong hint, not proof.</li>
                <li>One lucky run proves nothing: use walk-forward, the p-value and the overfitting page. Every variant you try raises the odds of fooling yourself.</li>
              </ul>
            </Panel>
          </div>
        </div>
      )}
    </div>
  );
}
