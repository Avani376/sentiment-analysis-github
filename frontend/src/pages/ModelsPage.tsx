import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, CircleAlert, Microscope, Scale } from "../components/icons";
import { Badge, Card, EmptyState, ErrorState, SectionTitle, Skeleton, Tooltip } from "../components/ui";
import { api } from "../lib/api";
import { pct, PROVENANCE_STYLES } from "../lib/format";
import type { ModelCompareResponse, ModelOut } from "../lib/types";

export function ModelsPage() {
  const models = useQuery({
    queryKey: ["models"],
    queryFn: () => api.get<ModelOut[]>("/api/v1/models"),
    staleTime: 60_000,
  });
  const compare = useQuery({
    queryKey: ["compare"],
    queryFn: () => api.get<ModelCompareResponse>("/api/v1/models/compare"),
  });

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-xl font-bold tracking-tight text-slate-100">Model Laboratory</h1>
        <p className="mt-1 text-sm text-slate-400">
          Every model's identity, provenance and limitations — plus its evaluation record.
        </p>
      </div>

      {/* Registry */}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {models.isLoading &&
          Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-64 rounded-2xl" />)}
        {models.isError && <ErrorState message="Could not load the model registry." />}
        {(models.data ?? []).map((m) => {
          const prov = PROVENANCE_STYLES[m.provenance];
          return (
            <Card key={m.key} className="flex flex-col">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-sm font-semibold text-slate-100">{m.display_name}</p>
                  <p className="mt-0.5 font-mono text-[11px] text-slate-500">{m.key}</p>
                </div>
                <Badge className={prov.chip} title={prov.hint}>
                  {prov.name}
                </Badge>
              </div>

              <div className="mt-3 flex flex-wrap gap-1.5">
                {m.labels.map((label) => (
                  <Badge key={label} className="bg-white/5 text-slate-300 ring-1 ring-white/10">
                    {label}
                  </Badge>
                ))}
                {!m.supports_neutral && (
                  <Tooltip text="This model has no neutral class in its training data. SENTINEX never forces one.">
                    <Badge className="bg-white/5 text-slate-500 ring-1 ring-white/10">binary</Badge>
                  </Tooltip>
                )}
              </div>

              <p className="mt-3 line-clamp-4 text-xs leading-relaxed text-slate-400">
                {m.card?.description}
              </p>

              <div className="mt-3 space-y-1.5 text-[11px] text-slate-500">
                <p className="flex items-center gap-1.5">
                  {m.enabled ? (
                    m.cached === false ? (
                      <>
                        <CircleAlert className="h-3.5 w-3.5 text-amber-400" /> weights not local — first use downloads them
                      </>
                    ) : (
                      <>
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" /> cached locally, ready
                      </>
                    )
                  ) : (
                    <>
                      <CircleAlert className="h-3.5 w-3.5 text-slate-500" /> disabled by configuration
                    </>
                  )}
                </p>
                <p className="font-mono">{m.source}</p>
              </div>

              {m.card && m.card.limitations.length > 0 && (
                <details className="mt-3 border-t border-[var(--color-edge)] pt-3">
                  <summary className="cursor-pointer text-xs font-medium text-slate-400 transition hover:text-slate-200">
                    Limitations ({m.card.limitations.length})
                  </summary>
                  <ul className="mt-2 list-disc space-y-1 pl-4 text-[11px] leading-relaxed text-slate-500">
                    {m.card.limitations.map((limitation, i) => (
                      <li key={i}>{limitation}</li>
                    ))}
                  </ul>
                </details>
              )}
            </Card>
          );
        })}
      </div>

      {/* Evaluations */}
      <Card>
        <SectionTitle
          title="Evaluation records"
          subtitle="Reproduced runs and historical references are labelled separately and never merged."
        />
        {compare.isLoading ? (
          <Skeleton className="h-40 w-full" />
        ) : compare.isError ? (
          <ErrorState message="Could not load evaluation artifacts." />
        ) : (compare.data?.evaluations ?? []).length === 0 ? (
          <EmptyState
            icon={<Scale className="h-6 w-6" />}
            title="No evaluation artifacts"
            hint="Run backend/ml/train_logreg.py to produce a reproduced evaluation."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-[var(--color-edge)] text-[11px] uppercase tracking-wider text-slate-500">
                  <th className="pb-2 pr-4 font-medium">Model</th>
                  <th className="pb-2 pr-4 font-medium">Type</th>
                  <th className="pb-2 pr-4 font-medium">Accuracy</th>
                  <th className="pb-2 pr-4 font-medium">Precision</th>
                  <th className="pb-2 pr-4 font-medium">Recall</th>
                  <th className="pb-2 pr-4 font-medium">F1</th>
                  <th className="pb-2 font-medium">Dataset</th>
                </tr>
              </thead>
              <tbody>
                {(compare.data?.evaluations ?? []).map((e) => (
                  <tr key={e.artifact} className="border-b border-[var(--color-edge)]/50 last:border-0">
                    <td className="py-2.5 pr-4 font-medium text-slate-200">{e.model_key}</td>
                    <td className="py-2.5 pr-4">
                      {e.evaluation_type === "reproduced" ? (
                        <Badge className="bg-indigo-500/12 text-indigo-300 ring-1 ring-indigo-500/30">
                          <Microscope className="h-3 w-3" /> reproduced
                        </Badge>
                      ) : (
                        <Badge className="bg-amber-500/12 text-amber-300 ring-1 ring-amber-500/30" title={e.notes ?? undefined}>
                          historical reference
                        </Badge>
                      )}
                    </td>
                    <td className="py-2.5 pr-4 font-semibold text-slate-100">{pct(e.metrics.accuracy)}</td>
                    <td className="py-2.5 pr-4 text-slate-300">{pct(e.metrics.precision)}</td>
                    <td className="py-2.5 pr-4 text-slate-300">{pct(e.metrics.recall)}</td>
                    <td className="py-2.5 pr-4 text-slate-300">{pct(e.metrics.f1_weighted)}</td>
                    <td className="py-2.5 max-w-56 truncate text-[11px] text-slate-500" title={String(e.dataset.name ?? "")}>
                      {String(e.dataset.name ?? "—")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="mt-3 text-[11px] leading-relaxed text-slate-600">
          Reproduced metrics come from seeded runs on a documented held-out split; historical references are committed
          numbers whose pipeline no longer exists. See <code className="text-slate-400">IMPLEMENTATION_PLAN.md</code>,
          decision D3.
        </p>
      </Card>
    </div>
  );
}
