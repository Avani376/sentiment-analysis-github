/** Emotion Intelligence page — separate task from sentiment, mapping shown. */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { PageHeader, DatasetSelect, useDatasets, NoDatasetState } from "../components/AnalysisShell";
import { Card, EmptyState, ErrorState, SectionTitle, Skeleton } from "../components/ui";
import { api } from "../lib/api";
import { labelStyle, pct } from "../lib/format";
import type { DatasetEmotionAnalytics } from "../lib/types";

const EMOTION_COLORS: Record<string, string> = {
  joy: "bg-emerald-500",
  anger: "bg-rose-500",
  sadness: "bg-sky-500",
  disgust: "bg-lime-600",
  fear: "bg-violet-500",
  surprise: "bg-amber-400",
  neutral: "bg-slate-500",
};

export function EmotionsPage() {
  const datasets = useDatasets();
  const [datasetId, setDatasetId] = useState("");
  const activeId = datasetId || datasets.data?.[0]?.id || "";

  const emotions = useQuery({
    queryKey: ["emotions", activeId],
    queryFn: () => api.get<DatasetEmotionAnalytics>(`/api/v1/emotions/datasets/${activeId}`),
    enabled: Boolean(activeId),
  });

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader
        title="Emotion Intelligence"
        subtitle="What customers FEEL — classified separately from sentiment. Mappings are documented approximations."
      />
      {datasets.isLoading ? (
        <Skeleton className="h-10 w-72" />
      ) : (datasets.data ?? []).length === 0 ? (
        <NoDatasetState />
      ) : (
        <>
          <div className="mb-5 flex items-center gap-3">
            <DatasetSelect datasets={datasets.data} activeId={activeId} onSelect={setDatasetId} />
            {emotions.data && (
              <span className="text-xs text-slate-500">
                {emotions.data.analyzed_reviews}/{emotions.data.total_reviews} reviews carry emotion
                results (model: {emotions.data.model_key})
              </span>
            )}
          </div>

          {emotions.isLoading ? (
            <Skeleton className="h-64 w-full" />
          ) : emotions.isError ? (
            <ErrorState message="Could not load emotion analytics." />
          ) : !emotions.data?.has_results ? (
            <EmptyState
              title="No emotion results yet"
              hint="Run the AI analysis for this dataset in the Review Explorer — the emotion model runs as part of the background job."
            />
          ) : (
            <>
              <Card>
                <SectionTitle title="Emotion distribution" subtitle="Dominant emotion per review." />
                <div className="space-y-3">
                  {emotions.data.distribution.map((entry) => (
                    <div key={entry.emotion}>
                      <div className="mb-1 flex items-center justify-between text-xs">
                        <span className="text-slate-300">
                          {entry.presentation}{" "}
                          <span className="text-slate-600">({entry.emotion})</span>
                        </span>
                        <span className="text-slate-400">
                          {entry.count} · {pct(entry.share, 0)}
                        </span>
                      </div>
                      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-800">
                        <div
                          className={`h-full ${EMOTION_COLORS[entry.emotion] ?? "bg-indigo-500"}`}
                          style={{ width: `${entry.share * 100}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
                <p className="mt-4 text-[11px] leading-relaxed text-slate-600">
                  Labels come from j-hartmann/emotion-english-distilroberta-base (public checkpoint).
                  Frustration, excitement and disappointment are not native model labels — they map to
                  anger, joy and sadness respectively, and are presented as approximations.
                </p>
              </Card>

              <div className="mt-5 grid gap-4 md:grid-cols-2">
                {emotions.data.distribution.slice(0, 4).map((entry) => {
                  const items = emotions.data?.examples[entry.emotion] ?? [];
                  if (items.length === 0) return null;
                  return (
                    <Card key={entry.emotion}>
                      <SectionTitle title={entry.presentation} subtitle="Most representative reviews" />
                      <ul className="space-y-2">
                        {items.map((example) => (
                          <li key={example.id} className="rounded-lg bg-white/[0.03] px-3 py-2">
                            <p className="line-clamp-2 text-xs leading-relaxed text-slate-300">
                              {example.text}
                            </p>
                            <p className="mt-1 flex items-center gap-2 text-[10px] text-slate-600">
                              <span className={`rounded-full px-1.5 py-px ${labelStyle(example.label).chip}`}>
                                {example.dominant_emotion}
                              </span>
                              {pct(example.confidence)} confidence · #{example.id}
                            </p>
                          </li>
                        ))}
                      </ul>
                    </Card>
                  );
                })}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
