/** Business Insights — deterministic, evidence-cited statements. */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { PageHeader, DatasetSelect, useDatasets, NoDatasetState } from "../components/AnalysisShell";
import { Card, EmptyState, ErrorState, SectionTitle, Skeleton } from "../components/ui";
import { api } from "../lib/api";
import type { InsightsOut, InsightOut } from "../lib/types";

const KIND_STYLES: Record<string, { chip: string; label: string }> = {
  executive_summary: { chip: "bg-indigo-500/12 text-indigo-300 ring-1 ring-indigo-500/30", label: "Summary" },
  positive_theme: { chip: "bg-emerald-500/12 text-emerald-300 ring-1 ring-emerald-500/30", label: "Positive theme" },
  negative_theme: { chip: "bg-rose-500/12 text-rose-300 ring-1 ring-rose-500/30", label: "Negative theme" },
  complaint: { chip: "bg-rose-500/12 text-rose-300 ring-1 ring-rose-500/30", label: "Recurring complaint" },
  recommendation: { chip: "bg-amber-500/12 text-amber-300 ring-1 ring-amber-500/30", label: "Suggested action" },
  topic: { chip: "bg-violet-500/12 text-violet-300 ring-1 ring-violet-500/30", label: "Topic" },
};

const STRENGTH_STYLES: Record<string, string> = {
  strong: "bg-emerald-500/12 text-emerald-300 ring-1 ring-emerald-500/30",
  moderate: "bg-amber-500/12 text-amber-300 ring-1 ring-amber-500/30",
  weak: "bg-slate-500/12 text-slate-400 ring-1 ring-slate-500/30",
};

function InsightCard({ insight }: { insight: InsightOut }) {
  const style = KIND_STYLES[insight.kind] ?? {
    chip: "bg-white/5 text-slate-300 ring-1 ring-white/10",
    label: insight.kind,
  };
  return (
    <Card className="fade-up">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-slate-100">{insight.title}</p>
          <span className={`mt-1 inline-flex rounded-full px-2 py-0.5 text-[10px] ${style.chip}`}>
            {style.label}
          </span>
        </div>
        <span
          title={`Evidence strength: ${insight.strength} (${insight.evidence.statistic})`}
          className={`shrink-0 rounded-full px-2.5 py-0.5 text-[10px] font-medium ${STRENGTH_STYLES[insight.strength]}`}
        >
          {insight.strength} evidence
        </span>
      </div>
      <p className="mt-2 text-sm leading-relaxed text-slate-300">{insight.statement}</p>
      <div className="mt-3 rounded-lg bg-white/[0.03] px-3 py-2">
        <p className="text-[10px] uppercase tracking-wider text-slate-600">Evidence</p>
        <p className="text-[11px] text-slate-400">{insight.evidence.statistic}</p>
        {insight.evidence.review_ids.length > 0 && (
          <p className="mt-1 text-[11px] text-slate-500">
            Cited reviews:{" "}
            {insight.evidence.review_ids.map((id) => (
              <span key={id} className="mr-1.5 font-mono text-slate-400">
                #{id}
              </span>
            ))}
          </p>
        )}
      </div>
    </Card>
  );
}

export function InsightsPage() {
  const datasets = useDatasets();
  const [datasetId, setDatasetId] = useState("");
  const activeId = datasetId || datasets.data?.[0]?.id || "";

  const insights = useQuery({
    queryKey: ["insights", activeId],
    queryFn: () => api.get<InsightsOut>(`/api/v1/datasets/${activeId}/insights`),
    enabled: Boolean(activeId),
  });

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader
        title="Business Insights"
        subtitle="Deterministic statements computed from your data — every claim cites its reviews or statistics."
      />
      {datasets.isLoading ? (
        <Skeleton className="h-10 w-72" />
      ) : (datasets.data ?? []).length === 0 ? (
        <NoDatasetState />
      ) : (
        <>
          <div className="mb-5 flex items-center gap-3">
            <DatasetSelect datasets={datasets.data} activeId={activeId} onSelect={setDatasetId} />
            {insights.data && (
              <span className="text-xs text-slate-500">
                computed from: {insights.data.generated_from.join(" · ")}
              </span>
            )}
          </div>

          {insights.isLoading ? (
            <div className="space-y-4">
              <Skeleton className="h-36 w-full" />
              <Skeleton className="h-36 w-full" />
            </div>
          ) : insights.isError ? (
            <ErrorState message="Could not load insights." />
          ) : !insights.data || insights.data.insights.length === 0 ? (
            <EmptyState
              title="No insights could be generated"
              hint="Run the AI analysis first — insights need persisted predictions, aspects and topics."
            />
          ) : (
            <SectionTitle title="Evidence-first insights" subtitle="Facts and suggested actions are labelled separately." />
          )}
          <div className="space-y-4">
            {insights.data?.insights.map((insight) => (
              <InsightCard key={insight.id} insight={insight} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
