/** Small formatting helpers shared across pages. */

export function pct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

export function ms(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  if (value >= 1000) return `${(value / 1000).toFixed(2)} s`;
  return `${value.toFixed(value < 10 ? 2 : 0)} ms`;
}

export function bytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(2)} MB`;
}

export function dateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export const LABEL_STYLES: Record<string, { chip: string; bar: string; dot: string; name: string }> = {
  positive: {
    chip: "bg-emerald-500/12 text-emerald-300 ring-1 ring-emerald-500/30",
    bar: "bg-emerald-500",
    dot: "bg-emerald-400",
    name: "Positive",
  },
  negative: {
    chip: "bg-rose-500/12 text-rose-300 ring-1 ring-rose-500/30",
    bar: "bg-rose-500",
    dot: "bg-rose-400",
    name: "Negative",
  },
  neutral: {
    chip: "bg-amber-500/12 text-amber-300 ring-1 ring-amber-500/30",
    bar: "bg-amber-500",
    dot: "bg-amber-400",
    name: "Neutral",
  },
};

export function labelStyle(label: string | null | undefined) {
  return LABEL_STYLES[label ?? ""] ?? {
    chip: "bg-slate-500/12 text-slate-300 ring-1 ring-slate-500/30",
    bar: "bg-slate-500",
    dot: "bg-slate-400",
    name: label ? String(label) : "—",
  };
}

export const PROVENANCE_STYLES: Record<string, { chip: string; name: string; hint: string }> = {
  trained_in_repo: {
    chip: "bg-indigo-500/12 text-indigo-300 ring-1 ring-indigo-500/30",
    name: "Trained in-repo",
    hint: "Reproducible training script + documented split",
  },
  legacy_artifact: {
    chip: "bg-amber-500/12 text-amber-300 ring-1 ring-amber-500/30",
    name: "Legacy artifact",
    hint: "Historical artifact; provenance unverified",
  },
  pretrained_checkpoint: {
    chip: "bg-violet-500/12 text-violet-300 ring-1 ring-violet-500/30",
    name: "Pretrained",
    hint: "Public checkpoint, not fine-tuned by this project",
  },
};
