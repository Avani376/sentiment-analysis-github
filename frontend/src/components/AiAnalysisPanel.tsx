/** AI analysis panel: launch background jobs, track progress, view analytics, export. */

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, CircleAlert, Database, Download, Play, Sparkles } from "../components/icons";
import { Button, Card, ConfidenceBar, EmptyState, SectionTitle, Skeleton, Tooltip } from "../components/ui";
import { useToast } from "../components/Toast";
import { api, ApiError } from "../lib/api";
import { labelStyle, pct } from "../lib/format";
import type { DatasetAnalytics, JobOut } from "../lib/types";

function useJobPolling(jobId: string | null) {
  return useQuery({
    queryKey: ["job", jobId],
    queryFn: () => api.get<JobOut>(`/api/v1/jobs/${jobId}`),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "queued" || status === "running" ? 1200 : false;
    },
  });
}

function ModelResult({ analytics }: { analytics: DatasetAnalytics }) {
  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
      {analytics.per_model.map((model) => {
        const total = Math.max(1, model.predictions);
        const fractions = ["positive", "negative", "neutral"]
          .filter((label) => (model.label_counts[label] ?? 0) > 0)
          .map((label) => ({
            key: label,
            value: (model.label_counts[label] ?? 0) / total,
            bar: labelStyle(label).bar,
          }));
        return (
          <Card key={model.model_key} className="fade-up">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-slate-100">{model.model_key}</p>
                <p className="text-[11px] text-slate-500">v{model.model_version}</p>
              </div>
              <Tooltip text="Average predicted-class probability across this dataset's reviews">
                <span className="rounded-full bg-white/5 px-2 py-0.5 text-[11px] text-slate-300 ring-1 ring-white/10">
                  conf {pct(model.avg_confidence)}
                </span>
              </Tooltip>
            </div>
            <div className="mt-3">
              <ConfidenceBar fractions={fractions} heightClass="h-2.5" />
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-400">
              <span>{model.predictions} predictions</span>
              {Object.entries(model.label_counts).map(([label, count]) => (
                <span key={label} className="flex items-center gap-1.5">
                  <span className={`h-1.5 w-1.5 rounded-full ${labelStyle(label).dot}`} />
                  {labelStyle(label).name} {count}
                </span>
              ))}
            </div>
          </Card>
        );
      })}
    </div>
  );
}

export function AiAnalysisPanel({ datasetId, datasetName }: { datasetId: string; datasetName: string }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [jobId, setJobId] = useState<string | null>(null);

  const analytics = useQuery({
    queryKey: ["analytics", datasetId],
    queryFn: () => api.get<DatasetAnalytics>(`/api/v1/datasets/${datasetId}/analytics`),
  });

  const launch = useMutation({
    mutationFn: () => api.post<JobOut>(`/api/v1/datasets/${datasetId}/analyze`, {}),
    onSuccess: (job) => {
      setJobId(job.id);
      toast("info", `Analysis queued: ${job.progress_total || "…"} prediction passes.`);
    },
    onError: (error) => {
      toast("error", error instanceof ApiError ? error.message : "Could not queue analysis.");
    },
  });

  const job = useJobPolling(jobId);
  const jobStatus = job.data?.status;
  const running = jobStatus === "queued" || jobStatus === "running";

  // refresh persisted analytics as soon as the job settles
  useEffect(() => {
    if (jobStatus === "succeeded") {
      void queryClient.invalidateQueries({ queryKey: ["analytics"] });
    }
  }, [jobStatus, queryClient]);

  if (running) {
    const done = job.data?.progress_current ?? 0;
    const total = Math.max(1, job.data?.progress_total ?? 1);
    return (
      <Card>
        <SectionTitle
          title="AI analysis running…"
          subtitle="Every review is scored by every available model. Predictions persist when the job completes."
        />
        <div className="h-2.5 w-full overflow-hidden rounded-full bg-slate-800">
          <div
            className="accent-gradient h-full transition-all duration-500"
            style={{ width: `${Math.round((done / total) * 100)}%` }}
          />
        </div>
        <p className="mt-2 text-xs text-slate-500">
          {done.toLocaleString()} / {total.toLocaleString()} prediction passes · job {jobId?.slice(0, 8)}…
        </p>
      </Card>
    );
  }

  if (jobStatus === "failed") {
    return (
      <Card>
        <SectionTitle title="Analysis failed" />
        <p className="flex items-center gap-2 text-sm text-rose-300">
          <CircleAlert className="h-4 w-4" /> {job.data?.error_message ?? "Unknown error."}
        </p>
        <Button className="mt-3" variant="ghost" onClick={() => setJobId(null)}>
          Dismiss
        </Button>
      </Card>
    );
  }

  return (
    <Card>
      <SectionTitle
        title="AI analysis"
        subtitle="Background job: every review scored by every available model. Login required."
        right={
          <div className="flex items-center gap-2">
            {analytics.data?.has_results && (
              <a
                href={`/api/v1/datasets/${datasetId}/export`}
                className="inline-flex items-center gap-2 rounded-xl bg-white/5 px-3 py-2 text-xs text-slate-200 ring-1 ring-white/10 transition hover:bg-white/10"
                download
              >
                <Download className="h-3.5 w-3.5" /> Export CSV
              </a>
            )}
            <Button onClick={() => launch.mutate()} disabled={launch.isPending}>
              <Play className="h-4 w-4" />
              {launch.isPending ? "Queuing…" : analytics.data?.has_results ? "Re-run analysis" : "Run AI analysis"}
            </Button>
          </div>
        }
      />

      {analytics.isLoading ? (
        <Skeleton className="h-24 w-full" />
      ) : analytics.isError ? (
        <p className="text-sm text-rose-300">Could not load analytics.</p>
      ) : analytics.data?.has_results ? (
        <>
          {jobStatus === "succeeded" && (
            <p className="mb-3 flex items-center gap-2 text-xs text-emerald-300">
              <CheckCircle2 className="h-4 w-4" /> Analysis complete — {analytics.data.total_predictions} predictions
              stored. Charts below are computed from persisted results.
            </p>
          )}
          <ModelResult analytics={analytics.data} />

          {analytics.data.examples.positive.length > 0 && (
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              {(["positive", "negative"] as const).map((kind) => {
                const items = analytics.data?.examples[kind] ?? [];
                if (items.length === 0) return null;
                return (
                  <div key={kind} className="rounded-xl bg-white/[0.03] p-4">
                    <p className="mb-2 flex items-center gap-2 text-xs font-medium text-slate-300">
                      <Sparkles className={`h-3.5 w-3.5 ${kind === "positive" ? "text-emerald-400" : "text-rose-400"}`} />
                      Most confident {kind} predictions
                    </p>
                    <ul className="space-y-2 text-[11px] leading-relaxed text-slate-500">
                      {items.map((example) => (
                        <li key={example.review_id} className="truncate" title={example.text}>
                          <span className="text-slate-300">{pct(example.confidence)}</span> — {example.text}
                        </li>
                      ))}
                    </ul>
                  </div>
                );
              })}
            </div>
          )}

          {Object.keys(analytics.data.agreement).length > 0 && (
            <div className="mt-4 flex flex-wrap gap-2 text-[11px] text-slate-500">
              <span className="font-medium text-slate-400">Model agreement:</span>
              {Object.entries(analytics.data.agreement).map(([pair, value]) => (
                <span key={pair} className="rounded-full bg-white/5 px-2 py-0.5 ring-1 ring-white/10">
                  {pair.replace("tfidf_logreg_", "").replace(" | ", " ↔ ")}: {pct(value)}
                </span>
              ))}
            </div>
          )}
        </>
      ) : (
        <EmptyState
          icon={<Database className="h-6 w-6" />}
          title={`"${datasetName}" has no stored predictions yet`}
          hint="Run the background analysis — every review is scored by the available models and results persist for dashboards and export."
        />
      )}
    </Card>
  );
}
