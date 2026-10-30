import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip as ReTooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Database, Microscope, Scale, CheckCircle2, CircleAlert, FileUp } from "../components/icons";
import { Badge, Card, EmptyState, ErrorState, SectionTitle, Skeleton, Stat } from "../components/ui";
import { api } from "../lib/api";
import { bytes, dateTime, labelStyle, pct, PROVENANCE_STYLES } from "../lib/format";
import type { DatasetOut, ModelCompareResponse, ModelOut } from "../lib/types";

export function OverviewPage() {
  const datasets = useQuery({
    queryKey: ["datasets"],
    queryFn: () => api.get<DatasetOut[]>("/api/v1/datasets"),
  });
  const models = useQuery({
    queryKey: ["models"],
    queryFn: () => api.get<ModelOut[]>("/api/v1/models"),
    staleTime: 60_000,
  });
  const compare = useQuery({
    queryKey: ["compare"],
    queryFn: () => api.get<ModelCompareResponse>("/api/v1/models/compare"),
  });

  const datasetList = datasets.data ?? [];
  const totals = datasetList.reduce(
    (acc, d) => ({
      reviews: acc.reviews + d.stats.valid_rows,
      duplicates: acc.duplicates + d.stats.duplicate_rows,
      datasets: acc.datasets + 1,
    }),
    { reviews: 0, duplicates: 0, datasets: 0 },
  );

  const chartData = (compare.data?.evaluations ?? [])
    .filter((e) => e.metrics.accuracy !== null)
    .map((e) => ({
      name: e.model_key.replace("tfidf_logreg_", "").replace("_", " "),
      accuracy: (e.metrics.accuracy ?? 0) * 100,
      type: e.evaluation_type,
    }));

  const isLoading = datasets.isLoading || models.isLoading || compare.isLoading;

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-xl font-bold tracking-tight text-slate-100">Overview</h1>
        <p className="mt-1 text-sm text-slate-400">
          Every number on this page is computed from processed data — nothing is mocked.
        </p>
      </div>

      {/* KPI row */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {isLoading ? (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24 rounded-2xl" />)
        ) : (
          <>
            <Stat
              label="Reviews processed"
              value={totals.reviews.toLocaleString()}
              sub={`across ${totals.datasets} dataset${totals.datasets === 1 ? "" : "s"}`}
              accentClass="text-indigo-300"
            />
            <Stat
              label="Registered models"
              value={models.data?.length ?? "—"}
              sub={`${(models.data ?? []).filter((m) => m.provenance === "trained_in_repo").length} reproducible · ${(models.data ?? []).filter((m) => m.provenance === "legacy_artifact").length} legacy`}
            />
            <Stat
              label="Best reproduced accuracy"
              value={pct(
                Math.max(
                  0,
                  ...(compare.data?.evaluations ?? [])
                    .filter((e) => e.evaluation_type === "reproduced")
                    .map((e) => e.metrics.accuracy ?? 0),
                ) || null,
              )}
              sub="held-out IMDb test split (25k)"
              accentClass="text-emerald-300"
            />
            <Stat
              label="Rows cleaned at ingest"
              value={totals.duplicates.toLocaleString()}
              sub="exact duplicates dropped"
            />
          </>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-5">
        {/* Evaluation chart */}
        <Card className="lg:col-span-3">
          <SectionTitle
            title="Model evaluation"
            subtitle="Reproduced vs. historical reference metrics — kept strictly separate."
          />
          {compare.isLoading ? (
            <Skeleton className="h-56 w-full" />
          ) : chartData.length === 0 ? (
            <EmptyState
              icon={<Scale className="h-6 w-6" />}
              title="No evaluation artifacts yet"
              hint="Run backend/ml/train_logreg.py to generate reproduced metrics."
            />
          ) : (
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1c2a47" vertical={false} />
                  <XAxis dataKey="name" tick={{ fill: "#8fa3c2", fontSize: 11 }} axisLine={{ stroke: "#1c2a47" }} tickLine={false} />
                  <YAxis domain={[0, 100]} tick={{ fill: "#8fa3c2", fontSize: 11 }} axisLine={{ stroke: "#1c2a47" }} tickLine={false} />
                  <ReTooltip
                    contentStyle={{ background: "#0d1425", border: "1px solid #1c2a47", borderRadius: 12, fontSize: 12, color: "#e2e8f0" }}
                    formatter={(value) => [`${Number(value ?? 0).toFixed(2)}%`, "accuracy"]}
                  />
                  <Bar dataKey="accuracy" radius={[6, 6, 0, 0]} maxBarSize={56}>
                    {chartData.map((d, i) => (
                      <Cell key={i} fill={d.type === "reproduced" ? "#6366f1" : "#52607d"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
          <p className="mt-3 text-[11px] leading-relaxed text-slate-600">
            Indigo bars come from documented, seeded runs of <code className="text-slate-400">ml/train_logreg.py</code>.
            Grey bars are committed historical values whose pipeline no longer exists — shown for reference only.
          </p>
        </Card>

        {/* Model fleet */}
        <Card className="lg:col-span-2">
          <SectionTitle title="Model fleet" subtitle="Registry status (no weights loaded)." />
          <div className="space-y-3">
            {models.isLoading &&
              Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-14 w-full" />)}
            {(models.data ?? []).map((m) => {
              const prov = PROVENANCE_STYLES[m.provenance];
              return (
                <div key={m.key} className="flex items-center justify-between gap-3 rounded-xl bg-white/[0.03] px-3 py-2.5">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-slate-200">{m.display_name}</p>
                    <p className="truncate text-[11px] text-slate-500">{m.labels.join(" / ")}</p>
                  </div>
                  <div className="flex shrink-0 items-center gap-1.5">
                    <Badge className={prov.chip} title={prov.hint}>
                      {prov.name}
                    </Badge>
                    {m.enabled ? (
                      m.cached === false ? (
                        <Badge className="bg-amber-500/12 text-amber-300 ring-1 ring-amber-500/30" title="Weights not local; first use downloads them">
                          <CircleAlert className="h-3 w-3" /> download
                        </Badge>
                      ) : (
                        <Badge className="bg-emerald-500/10 text-emerald-300 ring-1 ring-emerald-500/25">
                          <CheckCircle2 className="h-3 w-3" /> ready
                        </Badge>
                      )
                    ) : (
                      <Badge className="bg-slate-500/10 text-slate-400 ring-1 ring-slate-500/25">disabled</Badge>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      </div>

      {/* Datasets */}
      <Card>
        <SectionTitle title="Datasets" subtitle="Uploaded review collections and their ingest statistics." />
        {datasets.isLoading ? (
          <Skeleton className="h-24 w-full" />
        ) : datasets.isError ? (
          <ErrorState message="Could not load datasets." />
        ) : datasetList.length === 0 ? (
          <EmptyState
            icon={<FileUp className="h-6 w-6" />}
            title="No datasets yet"
            hint="Upload a CSV of reviews through POST /api/v1/datasets/upload (or the Review Explorer once dataset upload lands in the UI)."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-[var(--color-edge)] text-[11px] uppercase tracking-wider text-slate-500">
                  <th className="pb-2 pr-4 font-medium">Name</th>
                  <th className="pb-2 pr-4 font-medium">Rows</th>
                  <th className="pb-2 pr-4 font-medium">Valid</th>
                  <th className="pb-2 pr-4 font-medium">Dups</th>
                  <th className="pb-2 pr-4 font-medium">Columns</th>
                  <th className="pb-2 font-medium">Uploaded</th>
                </tr>
              </thead>
              <tbody>
                {datasetList.map((d) => (
                  <tr key={d.id} className="border-b border-[var(--color-edge)]/50 last:border-0">
                    <td className="py-2.5 pr-4">
                      <p className="font-medium text-slate-200">{d.name}</p>
                      <p className="text-[11px] text-slate-500">
                        <Database className="mr-1 inline h-3 w-3" />
                        {d.original_filename} · {bytes(d.file_size_bytes)}
                      </p>
                    </td>
                    <td className="py-2.5 pr-4 text-slate-300">{d.stats.row_count}</td>
                    <td className="py-2.5 pr-4">
                      <span className={`inline-flex items-center gap-1.5 ${labelStyle(d.stats.valid_rows > 0 ? "positive" : null).chip} rounded-full px-2 py-0.5 text-xs`}>
                        {d.stats.valid_rows}
                      </span>
                    </td>
                    <td className="py-2.5 pr-4 text-slate-400">{d.stats.duplicate_rows}</td>
                    <td className="py-2.5 pr-4 font-mono text-[11px] text-slate-400">
                      {d.text_column}
                      {d.label_column ? ` · ${d.label_column}` : ""}
                      {d.timestamp_column ? ` · ${d.timestamp_column}` : ""}
                    </td>
                    <td className="py-2.5 text-slate-400">{dateTime(d.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <p className="pb-2 text-center text-[11px] text-slate-600">
        <Microscope className="mr-1 inline h-3 w-3" />
        Bulk background analysis, emotion, aspects and topics arrive in upcoming milestones — every button that
        exists today works.
      </p>
    </div>
  );
}
