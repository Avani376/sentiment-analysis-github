/** Topic Explorer — TF-IDF + KMeans clusters with sentiment and representatives. */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { PageHeader, DatasetSelect, useDatasets, NoDatasetState } from "../components/AnalysisShell";
import { Card, EmptyState, ErrorState, Skeleton } from "../components/ui";
import { api } from "../lib/api";
import { labelStyle } from "../lib/format";
import type { TopicsOut } from "../lib/types";

export function TopicsPage() {
  const datasets = useDatasets();
  const [datasetId, setDatasetId] = useState("");
  const [k, setK] = useState<number | null>(null);
  const activeId = datasetId || datasets.data?.[0]?.id || "";

  const topics = useQuery({
    queryKey: ["topics", activeId, k],
    queryFn: () =>
      api.get<TopicsOut>(`/api/v1/datasets/${activeId}/topics${k ? `?k=${k}` : ""}`),
    enabled: Boolean(activeId),
  });

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader
        title="Topic Explorer"
        subtitle="What customers talk about — TF-IDF + KMeans clustering with majority sentiment per topic."
      />
      {datasets.isLoading ? (
        <Skeleton className="h-10 w-72" />
      ) : (datasets.data ?? []).length === 0 ? (
        <NoDatasetState />
      ) : (
        <>
          <div className="mb-5 flex flex-wrap items-center gap-3">
            <DatasetSelect datasets={datasets.data} activeId={activeId} onSelect={setDatasetId} />
            <select
              value={k ?? ""}
              onChange={(e) => setK(e.target.value ? Number(e.target.value) : null)}
              className="rounded-xl border border-[var(--color-edge)] bg-[var(--color-panel-2)] px-3 py-2 text-sm text-slate-200 outline-none focus:border-indigo-500/50"
            >
              <option value="">Auto topics</option>
              {[3, 4, 5, 6].map((n) => (
                <option key={n} value={n}>
                  {n} topics
                </option>
              ))}
            </select>
            {topics.data?.adequate && (
              <span className="text-xs text-slate-500">{topics.data.topics.length} topics found</span>
            )}
          </div>

          {topics.isLoading ? (
            <div className="grid gap-4 md:grid-cols-2">
              <Skeleton className="h-48" />
              <Skeleton className="h-48" />
            </div>
          ) : topics.isError ? (
            <ErrorState message="Could not load topics." />
          ) : !topics.data?.adequate ? (
            <EmptyState
              title="Dataset too small for clustering"
              hint={topics.data?.message ?? "At least 8 reviews are needed."}
            />
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {topics.data.topics.map((topic) => (
                <Card key={topic.topic_id} className="fade-up">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-semibold text-slate-100">Topic {topic.topic_id + 1}</p>
                    {topic.sentiment ? (
                      <span
                        className={`rounded-full px-2.5 py-0.5 text-xs ${labelStyle(topic.sentiment).chip}`}
                      >
                        net {topic.sentiment}
                      </span>
                    ) : (
                      <span className="rounded-full bg-slate-500/10 px-2.5 py-0.5 text-xs text-slate-400">
                        no predictions
                      </span>
                    )}
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {topic.keywords.map((keyword) => (
                      <span
                        key={keyword}
                        className="rounded-full bg-indigo-500/10 px-2 py-0.5 text-[11px] text-indigo-200 ring-1 ring-indigo-500/25"
                      >
                        {keyword}
                      </span>
                    ))}
                  </div>
                  <p className="mt-2 text-[11px] text-slate-500">
                    {topic.size} reviews · {topic.positive}↑ / {topic.negative}↓ with predictions
                  </p>
                  <div className="mt-3 space-y-1.5">
                    {topic.representative.map((r) => (
                      <p
                        key={r.review_id}
                        title={r.text}
                        className="line-clamp-2 rounded-lg bg-white/[0.03] px-3 py-2 text-[11px] leading-relaxed text-slate-400"
                      >
                        <span className="font-mono text-slate-600">#{r.review_id}</span> {r.text}
                      </p>
                    ))}
                  </div>
                </Card>
              ))}
            </div>
          )}
          <p className="mt-4 text-center text-[11px] text-slate-600">{topics.data?.method}</p>
        </>
      )}
    </div>
  );
}
