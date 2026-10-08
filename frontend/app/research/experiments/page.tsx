"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Star, Trash2, Pencil } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { SimpleTable } from "@/components/tables/SimpleTable";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field, Input, Textarea } from "@/components/ui/inputs";
import { ErrorBlock, Query } from "@/components/ui/state";
import { apiDelete, apiPatch } from "@/lib/api";
import { num, pnlClass, shortDate, signedMoney } from "@/lib/format";
import { useApiQuery, useBt } from "@/lib/hooks";
import type { Experiment } from "@/lib/types";

export default function ExperimentsPage() {
  const q = useApiQuery<Experiment[]>("/experiments");
  const qc = useQueryClient();
  const { setId, id: currentId } = useBt();
  const [editing, setEditing] = useState<Experiment | null>(null);
  const [err, setErr] = useState<unknown>(null);

  const refresh = async () => {
    await qc.invalidateQueries({ queryKey: ["api", "/experiments"] });
    await qc.invalidateQueries({ queryKey: ["backtests"] });
  };
  const patch = async (e: Experiment, body: Record<string, unknown>) => {
    try { await apiPatch(`/experiments/${e.id}`, body); await refresh(); } catch (x) { setErr(x); }
  };
  const remove = async (e: Experiment) => {
    if (!window.confirm(`Delete ${e.id} "${e.name}"? This cannot be undone.`)) return;
    try { await apiDelete(`/backtests/${e.id}`); await refresh(); } catch (x) { setErr(x); }
  };

  return (
    <>
      <PageHeader title="Experiments" description="Every backtest is an experiment with its parameters, dataset, seed and git commit, so any result can be reproduced. Keep failed ideas too - the number of things you tried is what makes a lucky result misleading." />
      {err ? <div className="mb-3"><ErrorBlock error={err} /></div> : null}
      <Query q={q}>
        {(rows) => (
          <Panel title={`${rows.length} experiments`} bodyClassName="p-2">
            <SimpleTable
              rows={rows}
              initialSort={{ key: "id", dir: "desc" }}
              columns={[
                { key: "favorite", header: "★", sortable: false, render: (r) => <button onClick={() => patch(r, { favorite: !r.favorite })} aria-label="Toggle favourite"><Star size={14} className={r.favorite ? "fill-warn text-warn" : "text-muted"} /></button> },
                { key: "id", header: "ID" },
                { key: "name", header: "Name", className: "font-sans", render: (r) => <button className="text-left hover:text-accent" onClick={() => setId(r.id)} title="Select this backtest">{r.name}{r.id === currentId && <Badge tone="accent" className="ml-1.5">selected</Badge>}</button> },
                { key: "strategy", header: "Strategy / ver.", render: (r) => `${r.strategy} · ${r.version}` },
                { key: "dataset", header: "Dataset", render: (r) => <span className="text-muted">{r.dataset}</span> },
                { key: "dates", header: "Dates", sortValue: (r) => r.start_date, render: (r) => `${shortDate(r.start_date)} → ${shortDate(r.end_date)}` },
                { key: "parameters", header: "Parameters", sortable: false, render: (r) => Object.keys(r.parameters).length ? Object.entries(r.parameters).map(([k, v]) => `${k}=${v}`).join(", ") : <span className="text-muted">defaults</span> },
                { key: "risk", header: "Risk", sortable: false, render: (r) => r.risk_settings.sizing_mode === "fixed_dollar" ? `$${r.risk_settings.risk_dollars}` : r.risk_settings.sizing_mode === "percent" ? `${r.risk_settings.risk_pct}%` : `${r.risk_settings.contracts} ct` },
                { key: "net", header: "Net P&L", align: "right", sortValue: (r) => r.metrics.net_profit as number, render: (r) => signedMoney(r.metrics.net_profit as number), cellClass: (r) => pnlClass(r.metrics.net_profit as number) },
                { key: "pf", header: "PF", align: "right", sortValue: (r) => r.metrics.profit_factor as number, render: (r) => num(r.metrics.profit_factor as number) },
                { key: "sh", header: "Sharpe", align: "right", sortValue: (r) => r.metrics.sharpe as number, render: (r) => num(r.metrics.sharpe as number) },
                { key: "p", header: "p-value", align: "right", sortValue: (r) => r.metrics.expectancy_pvalue as number, render: (r) => ((r.metrics.expectancy_pvalue as number | null) === null ? "–" : num(r.metrics.expectancy_pvalue as number, 3)), cellClass: (r) => ((r.metrics.expectancy_pvalue as number) <= 0.05 && (r.metrics.expectancy as number) > 0 ? "text-up" : "text-muted") },
                { key: "tags", header: "Tags", sortable: false, render: (r) => <span className="flex gap-1">{r.tags.map((t) => <Badge key={t}>{t}</Badge>)}</span> },
                { key: "created_at", header: "Created", render: (r) => r.created_at.slice(0, 16).replace("T", " ") },
                { key: "git_commit", header: "Commit" },
                { key: "seed", header: "Seed", align: "right" },
                { key: "actions", header: "", sortable: false, render: (r) => (
                  <span className="flex items-center gap-1.5">
                    <button onClick={() => setEditing(r)} aria-label="Edit"><Pencil size={13} className="text-muted hover:text-foreground" /></button>
                    <Link href="/research/comparison" onClick={() => setId(r.id)} className="text-[11px] text-accent hover:underline">compare</Link>
                    <button onClick={() => remove(r)} aria-label="Delete"><Trash2 size={13} className="text-muted hover:text-down" /></button>
                  </span>
                ) },
              ]}
            />
            <p className="px-2 pt-2 text-[11px] text-muted">p-value: t-test of the average trade vs zero. Green only when the strategy is profitable AND p ≤ 0.05.</p>
          </Panel>
        )}
      </Query>
      <EditDialog exp={editing} onClose={() => setEditing(null)} onSave={async (body) => { if (editing) { await patch(editing, body); setEditing(null); } }} />
      <p className="mt-2 text-[11px] text-muted">Money columns are net of costs. Experiments overlap in time, so adding their P&amp;L together is not meaningful.</p>
    </>
  );
}

function EditDialog({ exp, onClose, onSave }: { exp: Experiment | null; onClose: () => void; onSave: (b: Record<string, unknown>) => void }) {
  return (
    <Dialog open={exp !== null} onOpenChange={(o) => !o && onClose()}>
      <DialogContent title={exp ? `Edit ${exp.id}` : "Edit"} description="Rename, tag, annotate or change the version label." className="w-[min(560px,94vw)]">
        {exp && <EditBody key={exp.id} exp={exp} onSave={onSave} />}
      </DialogContent>
    </Dialog>
  );
}

function EditBody({ exp, onSave }: { exp: Experiment; onSave: (b: Record<string, unknown>) => void }) {
  const [name, setName] = useState(exp.name);
  const [version, setVersion] = useState(exp.version);
  const [tags, setTags] = useState(exp.tags.join(", "));
  const [notes, setNotes] = useState(exp.notes);
  return (
    <div className="space-y-3">
      <Field label="Name"><Input className="font-sans" value={name} onChange={(e) => setName(e.target.value)} /></Field>
      <Field label="Version"><Input className="font-sans" value={version} onChange={(e) => setVersion(e.target.value)} /></Field>
      <Field label="Tags (comma-separated)"><Input className="font-sans" value={tags} onChange={(e) => setTags(e.target.value)} /></Field>
      <Field label="Notes"><Textarea rows={4} className="font-sans" value={notes} onChange={(e) => setNotes(e.target.value)} /></Field>
      <Button variant="primary" onClick={() => onSave({ name, version, notes, tags: tags.split(",").map((t) => t.trim()).filter(Boolean) })}>Save</Button>
    </div>
  );
}
