import { useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, FileUp, Search, Database } from "../components/icons";
import { Badge, Button, Card, EmptyState, ErrorState, SectionTitle, Skeleton } from "../components/ui";
import { useToast } from "../components/Toast";
import { api, ApiError } from "../lib/api";
import { bytes, dateTime, labelStyle } from "../lib/format";
import type { DatasetCreatedResponse, DatasetOut, ReviewPage } from "../lib/types";

function UploadPanel() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");

  const mutation = useMutation({
    mutationFn: (form: FormData) => api.postForm<DatasetCreatedResponse>("/api/v1/datasets/upload", form),
    onSuccess: (dataset) => {
      toast(
        "success",
        `Imported "${dataset.name}": ${dataset.stats.valid_rows}/${dataset.stats.row_count} rows kept (${dataset.stats.duplicate_rows} duplicates dropped).`,
      );
      setFile(null);
      setName("");
      void queryClient.invalidateQueries({ queryKey: ["datasets"] });
    },
    onError: (error) => {
      toast("error", error instanceof ApiError ? error.message : "Upload failed.");
    },
  });

  const submit = () => {
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    if (name.trim()) form.append("name", name.trim());
    mutation.mutate(form);
  };

  return (
    <Card>
      <SectionTitle
        title="Import a CSV"
        subtitle="Columns are auto-detected and always reported back — text, label, id and timestamp."
      />
      <div className="flex flex-wrap items-center gap-3">
        <label className="inline-flex cursor-pointer items-center gap-2 rounded-xl bg-white/5 px-4 py-2 text-sm text-slate-200 ring-1 ring-white/10 transition hover:bg-white/10">
          <FileUp className="h-4 w-4" />
          {file ? file.name : "Choose CSV…"}
          <input
            type="file"
            accept=".csv"
            className="hidden"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </label>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Dataset name (optional)"
          className="w-56 rounded-xl border border-[var(--color-edge)] bg-[var(--color-base)]/60 px-3 py-2 text-sm text-slate-200 outline-none placeholder:text-slate-600 focus:border-indigo-500/50"
        />
        <Button onClick={submit} disabled={!file || mutation.isPending}>
          {mutation.isPending ? "Importing…" : "Import"}
        </Button>
        {file && (
          <span className="text-xs text-slate-500">
            {bytes(file.size)} · max 10 MB
          </span>
        )}
      </div>
      {file && (
        <p className="mt-2 text-[11px] text-slate-600">
          Synchronous import; rows beyond the 100,000-row ingest limit are rejected with a clear error.
        </p>
      )}
    </Card>
  );
}

export function ExplorerPage() {
  const [datasetId, setDatasetId] = useState<string>("");
  const [q, setQ] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [label, setLabel] = useState<"" | "positive" | "negative">("");
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const datasets = useQuery({
    queryKey: ["datasets"],
    queryFn: () => api.get<DatasetOut[]>("/api/v1/datasets"),
  });

  const activeDataset = datasetId || datasets.data?.[0]?.id || "";

  const reviews = useQuery({
    queryKey: ["reviews", activeDataset, q, label, page],
    queryFn: () =>
      api.get<ReviewPage>(
        `/api/v1/datasets/${activeDataset}/reviews?page=${page}&page_size=${pageSize}` +
          (q ? `&q=${encodeURIComponent(q)}` : "") +
          (label ? `&label=${label}` : ""),
      ),
    enabled: Boolean(activeDataset),
    placeholderData: keepPreviousData,
  });

  const submitSearch = () => {
    setPage(1);
    setQ(searchInput.trim());
  };

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-xl font-bold tracking-tight text-slate-100">Review Explorer</h1>
        <p className="mt-1 text-sm text-slate-400">
          Search and filter imported reviews; ground-truth labels come from your CSV, not from a model.
        </p>
      </div>

      <UploadPanel />

      <Card>
        <SectionTitle title="Browse reviews" subtitle="Full-text search, label filter, pagination." />
        {datasets.isLoading ? (
          <Skeleton className="h-10 w-64" />
        ) : (datasets.data ?? []).length === 0 ? (
          <EmptyState
            icon={<Database className="h-6 w-6" />}
            title="No datasets imported yet"
            hint="Import a CSV above and it will appear here."
          />
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-3">
              <select
                value={activeDataset}
                onChange={(e) => {
                  setDatasetId(e.target.value);
                  setPage(1);
                }}
                className="rounded-xl border border-[var(--color-edge)] bg-[var(--color-panel-2)] px-3 py-2 text-sm text-slate-200 outline-none focus:border-indigo-500/50"
              >
                {(datasets.data ?? []).map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} ({d.stats.valid_rows} reviews)
                  </option>
                ))}
              </select>

              <div className="flex items-center gap-2">
                <div className="relative">
                  <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
                  <input
                    value={searchInput}
                    onChange={(e) => setSearchInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && submitSearch()}
                    placeholder="Search review text…"
                    className="w-64 rounded-xl border border-[var(--color-edge)] bg-[var(--color-base)]/60 py-2 pl-9 pr-3 text-sm text-slate-200 outline-none placeholder:text-slate-600 focus:border-indigo-500/50"
                  />
                </div>
                <Button variant="ghost" onClick={submitSearch}>
                  Search
                </Button>
              </div>

              <div className="flex gap-1.5">
                {(["", "positive", "negative"] as const).map((value) => (
                  <button
                    key={value || "all"}
                    onClick={() => {
                      setLabel(value);
                      setPage(1);
                    }}
                    className={`rounded-full px-3 py-1 text-xs transition ${
                      label === value
                        ? "bg-indigo-500/20 text-indigo-200 ring-1 ring-indigo-500/40"
                        : "bg-white/5 text-slate-400 ring-1 ring-white/10 hover:bg-white/10"
                    }`}
                  >
                    {value === "" ? "All labels" : labelStyle(value).name}
                  </button>
                ))}
              </div>
            </div>

            {reviews.isLoading ? (
              <div className="mt-4 space-y-2">
                {Array.from({ length: 6 }).map((_, i) => (
                  <Skeleton key={i} className="h-14 w-full" />
                ))}
              </div>
            ) : reviews.isError ? (
              <div className="mt-4">
                <ErrorState
                  message={reviews.error instanceof ApiError ? reviews.error.message : "Could not load reviews."}
                />
              </div>
            ) : (reviews.data?.items ?? []).length === 0 ? (
              <div className="mt-4">
                <EmptyState title="No reviews match" hint="Try a different search term or clear the label filter." />
              </div>
            ) : (
              <>
                <div className="mt-4 space-y-2">
                  {reviews.data?.items.map((review) => {
                    const style = labelStyle(review.label);
                    return (
                      <div key={review.id} className="rounded-xl bg-white/[0.03] px-4 py-3 transition hover:bg-white/[0.05]">
                        <div className="flex items-start justify-between gap-4">
                          <p className="min-w-0 flex-1 text-sm leading-relaxed text-slate-300">
                            {review.text.length > 320 ? `${review.text.slice(0, 320)}…` : review.text}
                          </p>
                          <Badge className={`${style.chip} shrink-0`} title={review.raw_label ? `CSV value: ${review.raw_label}` : "No ground-truth label"}>
                            {style.name}
                          </Badge>
                        </div>
                        <p className="mt-1.5 flex items-center gap-3 text-[11px] text-slate-600">
                          {review.external_id && <span>id: {review.external_id}</span>}
                          {review.review_timestamp && <span>{dateTime(review.review_timestamp)}</span>}
                          <span className="font-mono">#{review.id}</span>
                        </p>
                      </div>
                    );
                  })}
                </div>

                <div className="mt-4 flex items-center justify-between text-xs text-slate-500">
                  <span>
                    {reviews.data ? `${(reviews.data.total).toLocaleString()} matching reviews` : "…"}
                  </span>
                  <div className="flex items-center gap-2">
                    <Button variant="ghost" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={(reviews.data?.page ?? 1) <= 1} className="px-2.5 py-1.5">
                      <ChevronLeft className="h-4 w-4" />
                    </Button>
                    <span>
                      page {reviews.data?.page ?? 1} / {reviews.data?.pages ?? 1}
                    </span>
                    <Button
                      variant="ghost"
                      onClick={() => setPage((p) => ((reviews.data?.pages ?? 1) > p ? p + 1 : p))}
                      disabled={(reviews.data?.pages ?? 1) <= (reviews.data?.page ?? 1)}
                      className="px-2.5 py-1.5"
                    >
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </>
            )}
          </>
        )}
      </Card>
    </div>
  );
}
