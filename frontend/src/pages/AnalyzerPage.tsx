import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Sparkles, Send, Timer } from "../components/icons";
import { Button, Card, ConfidenceBar, ErrorState, SectionTitle, Skeleton, Tooltip } from "../components/ui";
import { api, ApiError } from "../lib/api";
import { labelStyle, ms, PROVENANCE_STYLES } from "../lib/format";
import type { ModelOut, SingleAnalyzeResponse } from "../lib/types";

const EXAMPLES: Record<string, string> = {
  positive:
    "Absolutely loved this product — the build quality is superb and it exceeded every expectation I had.",
  negative:
    "Terrible experience. It arrived broken, the app crashes constantly, and support ignored my emails for two weeks.",
  mixed:
    "The camera is superb and battery life amazed me, but the screen scratches far too easily and the charger is not included.",
};

function ModelResultCard({
  prediction,
  provenance,
}: {
  prediction: SingleAnalyzeResponse["predictions"][number];
  provenance?: string;
}) {
  const style = labelStyle(prediction.label);
  const provenanceStyle = provenance ? PROVENANCE_STYLES[provenance] : undefined;
  const fractions = Object.entries(prediction.probabilities).map(([key, value]) => ({
    key,
    value,
    bar: labelStyle(key).bar,
  }));

  return (
    <Card className="fade-up">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-slate-100">{prediction.model_display_name}</p>
          <p className="mt-0.5 flex items-center gap-2 text-[11px] text-slate-500">
            {prediction.model_key} · v{prediction.model_version}
            {provenanceStyle && (
              <span className={`rounded-full px-1.5 py-px text-[10px] ${provenanceStyle.chip}`} title={provenanceStyle.hint}>
                {provenanceStyle.name}
              </span>
            )}
          </p>
        </div>
        <span
          className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide ${style.chip}`}
        >
          {style.name}
        </span>
      </div>

      <div className="mt-4 flex items-baseline gap-2">
        <p className="text-3xl font-semibold tracking-tight text-slate-100">
          {(prediction.confidence * 100).toFixed(1)}%
        </p>
        <p className="text-xs text-slate-500">predicted-class probability</p>
      </div>

      <div className="mt-2">
        <ConfidenceBar fractions={fractions} />
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
        {Object.entries(prediction.probabilities).map(([key, value]) => (
          <div key={key} className="flex items-center justify-between rounded-lg bg-white/[0.03] px-3 py-2">
            <span className="flex items-center gap-1.5 text-slate-400">
              <span className={`h-1.5 w-1.5 rounded-full ${labelStyle(key).dot}`} />
              {labelStyle(key).name}
            </span>
            <span className="font-medium text-slate-200">{(value * 100).toFixed(2)}%</span>
          </div>
        ))}
      </div>

      <p className="mt-3 flex items-center gap-1.5 text-[11px] text-slate-500">
        <Timer className="h-3 w-3" /> inference {ms(prediction.latency_ms)} ·{" "}
        {prediction.supports_neutral ? "supports neutral" : "binary model — no neutral class"}
      </p>
    </Card>
  );
}

export function AnalyzerPage() {
  const [text, setText] = useState(EXAMPLES.mixed);
  const modelsQuery = useQuery({
    queryKey: ["models"],
    queryFn: () => api.get<ModelOut[]>("/api/v1/models"),
    staleTime: 60_000,
  });
  // Default selection: enabled models whose weights are already local, so a
  // click never triggers a surprise multi-hundred-MB download.
  const availableModels = (modelsQuery.data ?? []).filter((m) => m.enabled && m.cached !== false);

  const mutation = useMutation({
    mutationFn: (payload: { text: string; models: string[] }) =>
      api.post<SingleAnalyzeResponse>("/api/v1/analyze/single", payload),
  });

  const modelMeta = (key: string) => modelsQuery.data?.find((m) => m.key === key);

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-5">
        <h1 className="text-xl font-bold tracking-tight text-slate-100">Single Review Analyzer</h1>
        <p className="mt-1 text-sm text-slate-400">
          Run one review through every registered model. Each model declares its own label set —
          binary models are never forced to emit a neutral class.
        </p>
      </div>

      <Card>
        <SectionTitle
          title="Review text"
          subtitle="Customer feedback, product opinion, movie review — any unstructured text."
        />
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={5}
          maxLength={20_000}
          placeholder="Paste or type a review…"
          className="w-full resize-y rounded-xl border border-[var(--color-edge)] bg-[var(--color-base)]/60 px-4 py-3 text-sm text-slate-200 outline-none transition placeholder:text-slate-600 focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/20"
        />
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap gap-2">
            {Object.entries(EXAMPLES).map(([kind, example]) => (
              <button
                key={kind}
                onClick={() => setText(example)}
                className="rounded-full bg-white/5 px-3 py-1 text-xs text-slate-400 ring-1 ring-white/10 transition hover:bg-white/10 hover:text-slate-200"
              >
                {kind} example
              </button>
            ))}
          </div>
          <div className="flex items-center gap-3">
            <span className="text-[11px] text-slate-600">{text.length.toLocaleString()} / 20,000</span>
            <Button onClick={() => mutation.mutate({ text: text.trim(), models: availableModels.map((m) => m.key) })} disabled={mutation.isPending || !text.trim()}>
              <Send className="h-4 w-4" />
              {mutation.isPending ? "Analyzing…" : "Analyze"}
            </Button>
          </div>
        </div>
        {mutation.isError && (
          <div className="mt-4">
            <ErrorState
              message={mutation.error instanceof ApiError ? mutation.error.message : "Unexpected error."}
              code={mutation.error instanceof ApiError ? mutation.error.code : undefined}
            />
          </div>
        )}
      </Card>

      <div className="mt-6">
        {mutation.isPending && (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {availableModels.map((m) => (
              <Card key={m.key}>
                <Skeleton className="h-4 w-36" />
                <Skeleton className="mt-3 h-8 w-24" />
                <Skeleton className="mt-4 h-2 w-full" />
                <Skeleton className="mt-4 h-12 w-full" />
              </Card>
            ))}
          </div>
        )}

        {mutation.isSuccess && (
          <>
            <div className="mb-3 flex items-center gap-2 text-xs text-slate-500">
              <Sparkles className="h-3.5 w-3.5 text-indigo-400" />
              {mutation.data.predictions.length} model
              {mutation.data.predictions.length === 1 ? "" : "s"} analyzed {mutation.data.text_chars} characters —
              probabilities are{" "}
              <Tooltip text="Each model's raw softmax/logistic output. Not calibrated, and not directly comparable between model families.">
                <span className="cursor-help underline decoration-dotted underline-offset-2">not calibrated</span>
              </Tooltip>{" "}
              across model families.
            </div>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {mutation.data.predictions.map((p) => (
                <ModelResultCard key={p.model_key} prediction={p} provenance={modelMeta(p.model_key)?.provenance} />
              ))}
            </div>
          </>
        )}

        {!mutation.isPending && !mutation.isSuccess && (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {availableModels.map((m) => (
              <Card key={m.key} className="opacity-50">
                <p className="text-sm font-semibold text-slate-300">{m.display_name}</p>
                <p className="mt-0.5 text-[11px] text-slate-500">{m.key}</p>
                <p className="mt-4 text-xs text-slate-600">Waiting for analysis…</p>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
