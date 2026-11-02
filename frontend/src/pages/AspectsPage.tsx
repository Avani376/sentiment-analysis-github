/** Aspect Intelligence page — rule-based baseline, evidence spans visible. */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { PageHeader, DatasetSelect, useDatasets, NoDatasetState } from "../components/AnalysisShell";
import { Card, ConfidenceBar, EmptyState, ErrorState, Skeleton } from "../components/ui";
import { api } from "../lib/api";
import { labelStyle, pct } from "../lib/format";
import type { AspectsOut } from "../lib/types";

export function AspectsPage() {
  const datasets = useDatasets();
  const [datasetId, setDatasetId] = useState("");
  const activeId = datasetId || datasets.data?.[0]?.id || "";

  const aspects = useQuery({
    queryKey: ["aspects", activeId],
    queryFn: () => api.get<AspectsOut>(`/api/v1/datasets/${activeId}/aspects`),
    enabled: Boolean(activeId),
  });

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader
        title="Aspect Intelligence"
        subtitle="Which product aspects customers discuss — and whether each mention reads positive or negative."
      />
      {datasets.isLoading ? (
        <Skeleton className="h-10 w-72" />
      ) : (datasets.data ?? []).length === 0 ? (
        <NoDatasetState />
      ) : (
        <>
          <div className="mb-5 flex items-center gap-3">
            <DatasetSelect datasets={datasets.data} activeId={activeId} onSelect={setDatasetId} />
            {aspects.data && (
              <span className="text-xs text-slate-500">{aspects.data.clauses_analyzed} clauses analyzed</span>
            )}
          </div>

          <Card className="mb-5 border-amber-500/20 bg-amber-500/[0.03]">
            <p className="text-[11px] leading-relaxed text-amber-200/70">
              <strong className="text-amber-300">Transparent baseline:</strong>{" "}
              {aspects.data?.method ??
                "rule-based aspect lexicon + clause-level polarity from a registered sentiment model. Every claim carries its exact evidence clause — this is NOT a trained ABSA model."}
            </p>
          </Card>

          {aspects.isLoading ? (
            <div className="space-y-3">
              <Skeleton className="h-32 w-full" />
              <Skeleton className="h-32 w-full" />
            </div>
          ) : aspects.isError ? (
            <ErrorState message="Could not load aspect analysis." />
          ) : !aspects.data || aspects.data.aspects.length === 0 ? (
            <EmptyState
              title="No aspect mentions found"
              hint="No known aspect terms (battery, delivery, support, pricing…) appear in this dataset."
            />
          ) : (
            <div className="space-y-4">
              {aspects.data.aspects.map((aspect) => {
                const total = Math.max(1, aspect.mentions);
                return (
                  <Card key={aspect.category} className="fade-up">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold capitalize text-slate-100">
                          {aspect.category}
                        </p>
                        <p className="text-[11px] text-slate-500">
                          {aspect.mentions} mentions · avg confidence {pct(aspect.avg_confidence)}
                        </p>
                      </div>
                      <span
                        className={`rounded-full px-3 py-1 text-xs font-medium ${
                          aspect.positive >= aspect.negative
                            ? labelStyle("positive").chip
                            : labelStyle("negative").chip
                        }`}
                      >
                        {aspect.positive >= aspect.negative ? "net positive" : "net negative"}
                      </span>
                    </div>
                    <div className="mt-3">
                      <ConfidenceBar
                        fractions={[
                          { key: "positive", value: aspect.positive / total, bar: labelStyle("positive").bar },
                          { key: "negative", value: aspect.negative / total, bar: labelStyle("negative").bar },
                          { key: "neutral", value: aspect.neutral / total, bar: labelStyle("neutral").bar },
                        ]}
                      />
                      <p className="mt-1.5 text-[11px] text-slate-500">
                        {aspect.positive} positive · {aspect.negative} negative · {aspect.neutral} neutral
                      </p>
                    </div>
                    <div className="mt-3 grid gap-2 md:grid-cols-2">
                      {aspect.negative_evidence.map((m) => (
                        <div key={`n-${m.review_id}-${m.term}`} className="rounded-lg bg-rose-500/[0.06] px-3 py-2">
                          <p className="line-clamp-2 text-[11px] text-slate-300">“{m.evidence}”</p>
                          <p className="mt-1 text-[10px] text-rose-300/70">
                            review #{m.review_id} · {pct(m.confidence)}
                          </p>
                        </div>
                      ))}
                      {aspect.positive_evidence.map((m) => (
                        <div key={`p-${m.review_id}-${m.term}`} className="rounded-lg bg-emerald-500/[0.06] px-3 py-2">
                          <p className="line-clamp-2 text-[11px] text-slate-300">“{m.evidence}”</p>
                          <p className="mt-1 text-[10px] text-emerald-300/70">
                            review #{m.review_id} · {pct(m.confidence)}
                          </p>
                        </div>
                      ))}
                    </div>
                  </Card>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}
