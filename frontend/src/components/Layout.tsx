/** App shell: sidebar navigation + top bar with live backend status. */

import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  Boxes,
  Gauge,
  ListFilter,
  MessageSquareText,
  Microscope,
  SentinexLogo,
} from "./icons";
import type { Health } from "../lib/types";
import { api } from "../lib/api";

const NAV = [
  { to: "/", label: "Overview", icon: Gauge, end: true },
  { to: "/analyze", label: "Analyze Review", icon: MessageSquareText, end: false },
  { to: "/explorer", label: "Review Explorer", icon: ListFilter, end: false },
  { to: "/models", label: "Model Laboratory", icon: Microscope, end: false },
];

function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: () => api.get<Health>("/health"),
    refetchInterval: 30_000,
  });
}

function Sidebar({ healthy }: { healthy: boolean | undefined }) {
  return (
    <aside className="flex h-full w-60 shrink-0 flex-col border-r border-[var(--color-edge)] bg-[var(--color-panel)]/60 backdrop-blur">
      <div className="flex items-center gap-3 px-5 pb-6 pt-6">
        <SentinexLogo className="h-9 w-9" />
        <div>
          <p className="text-sm font-bold tracking-tight">
            <span className="accent-gradient-text">SENTINEX</span> <span className="text-slate-200">AI</span>
          </p>
          <p className="text-[10px] uppercase tracking-[0.14em] text-slate-500">Review Intelligence</p>
        </div>
      </div>

      <nav className="flex flex-1 flex-col gap-1 px-3">
        {NAV.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition ${
                isActive
                  ? "bg-gradient-to-r from-indigo-500/15 to-violet-500/10 font-medium text-indigo-200 ring-1 ring-indigo-500/25"
                  : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
              }`
            }
          >
            <Icon className="h-4.5 w-4.5" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-[var(--color-edge)] px-5 py-4">
        <div className="flex items-center gap-2 text-xs">
          <span
            className={`h-2 w-2 rounded-full ${healthy === undefined ? "animate-pulse bg-amber-400" : healthy ? "bg-emerald-400" : "bg-rose-400"}`}
          />
          <span className="text-slate-500">
            Backend {healthy === undefined ? "connecting…" : healthy ? "online" : "offline"}
          </span>
        </div>
        <p className="mt-2 flex items-center gap-1.5 text-[10px] text-slate-600">
          <Activity className="h-3 w-3" /> v0.2.0 · local deployment
        </p>
      </div>
    </aside>
  );
}

export function Layout() {
  const { data: health } = useHealth();
  const location = useLocation();
  const current = NAV.find((n) => (n.end ? n.to === location.pathname : location.pathname.startsWith(n.to)));
  // undefined = still connecting; true/false = definite state.
  const healthy = health ? health.database === "ok" : undefined;

  return (
    <div className="app-backdrop flex h-full">
      <Sidebar healthy={healthy} />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 items-center justify-between border-b border-[var(--color-edge)] px-6">
          <h1 className="text-sm font-medium text-slate-300">{current?.label ?? "SENTINEX AI"}</h1>
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <Boxes className="h-3.5 w-3.5" />
            {health ? `${health.registered_models} models registered` : "…"}
          </div>
        </header>
        <main className="flex-1 overflow-y-auto px-6 py-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
