/** Shared analysis-shell: dataset picker + page scaffolding for analysis pages. */

import { useQuery } from "@tanstack/react-query";
import { Database } from "./icons";
import { api } from "../lib/api";
import type { DatasetOut } from "../lib/types";

export function useDatasets() {
  return useQuery({ queryKey: ["datasets"], queryFn: () => api.get<DatasetOut[]>("/api/v1/datasets") });
}

export function DatasetSelect({
  datasets,
  activeId,
  onSelect,
}: {
  datasets: DatasetOut[] | undefined;
  activeId: string;
  onSelect: (id: string) => void;
}) {
  if (!datasets || datasets.length === 0) return null;
  return (
    <select
      value={activeId}
      onChange={(e) => onSelect(e.target.value)}
      className="rounded-xl border border-[var(--color-edge)] bg-[var(--color-panel-2)] px-3 py-2 text-sm text-slate-200 outline-none focus:border-indigo-500/50"
    >
      {datasets.map((d) => (
        <option key={d.id} value={d.id}>
          {d.name} ({d.stats.valid_rows} reviews)
        </option>
      ))}
    </select>
  );
}

export function NoDatasetState() {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-slate-700/60 px-6 py-12 text-center">
      <Database className="h-6 w-6 text-slate-500" />
      <p className="text-sm font-medium text-slate-300">No datasets yet</p>
      <p className="max-w-md text-xs text-slate-500">
        Import a CSV in the Review Explorer first — analysis modules work on imported datasets.
      </p>
    </div>
  );
}

export function PageHeader({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div className="mb-5">
      <h1 className="text-xl font-bold tracking-tight text-slate-100">{title}</h1>
      <p className="mt-1 text-sm text-slate-400">{subtitle}</p>
    </div>
  );
}
