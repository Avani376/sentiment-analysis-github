/** Minimal dependency-free UI kit styled for the SENTINEX dark theme. */

import type { ReactNode } from "react";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`card p-5 ${className}`}>{children}</div>;
}

export function SectionTitle({
  title,
  subtitle,
  right,
}: {
  title: string;
  subtitle?: string;
  right?: ReactNode;
}) {
  return (
    <div className="mb-4 flex items-start justify-between gap-4">
      <div>
        <h2 className="text-base font-semibold tracking-tight text-slate-100">{title}</h2>
        {subtitle && <p className="mt-0.5 text-sm text-slate-400">{subtitle}</p>}
      </div>
      {right}
    </div>
  );
}

export function Badge({
  children,
  className = "",
  title,
}: {
  children: ReactNode;
  className?: string;
  title?: string;
}) {
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${className}`}
    >
      {children}
    </span>
  );
}

export function Button({
  children,
  onClick,
  variant = "primary",
  disabled = false,
  type = "button",
  className = "",
}: {
  children: ReactNode;
  onClick?: () => void;
  variant?: "primary" | "ghost" | "danger";
  disabled?: boolean;
  type?: "button" | "submit";
  className?: string;
}) {
  const styles = {
    primary:
      "accent-gradient text-white shadow-lg shadow-indigo-950/40 hover:opacity-90 active:opacity-80",
    ghost:
      "bg-white/5 text-slate-200 ring-1 ring-white/10 hover:bg-white/10 active:bg-white/15",
    danger: "bg-rose-500/10 text-rose-300 ring-1 ring-rose-500/30 hover:bg-rose-500/20",
  }[variant];
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-40 ${styles} ${className}`}
    >
      {children}
    </button>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} aria-hidden="true" />;
}

export function EmptyState({
  icon,
  title,
  hint,
  action,
}: {
  icon?: ReactNode;
  title: string;
  hint?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-slate-700/60 px-6 py-12 text-center">
      {icon && <div className="text-slate-500">{icon}</div>}
      <p className="text-sm font-medium text-slate-300">{title}</p>
      {hint && <p className="max-w-md text-xs leading-relaxed text-slate-500">{hint}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

export function ErrorState({ message, code }: { message: string; code?: string }) {
  return (
    <div className="rounded-xl border border-rose-500/25 bg-rose-500/5 px-5 py-4">
      <p className="text-sm font-medium text-rose-300">
        Something went wrong{code ? ` — ${code}` : ""}
      </p>
      <p className="mt-1 text-xs leading-relaxed text-rose-200/70">{message}</p>
    </div>
  );
}

export function Stat({
  label,
  value,
  sub,
  accentClass = "text-slate-100",
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  accentClass?: string;
}) {
  return (
    <Card className="flex flex-col gap-1">
      <p className="text-[11px] font-medium uppercase tracking-wider text-slate-500">{label}</p>
      <p className={`text-2xl font-semibold tracking-tight ${accentClass}`}>{value}</p>
      {sub && <p className="text-xs text-slate-500">{sub}</p>}
    </Card>
  );
}

export function ConfidenceBar({
  fractions,
  heightClass = "h-2",
}: {
  fractions: { key: string; value: number; bar: string }[];
  heightClass?: string;
}) {
  return (
    <div className={`flex w-full overflow-hidden rounded-full bg-slate-800/70 ${heightClass}`}>
      {fractions.map((f) => (
        <div
          key={f.key}
          className={f.bar}
          style={{ width: `${Math.max(f.value * 100, f.value > 0 ? 1.5 : 0)}%` }}
        />
      ))}
    </div>
  );
}

export function Tooltip({ text, children }: { text: string; children: ReactNode }) {
  return (
    <span className="group relative inline-flex cursor-help items-center">
      {children}
      <span className="pointer-events-none absolute bottom-full left-1/2 z-30 mb-2 hidden w-56 -translate-x-1/2 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-xs leading-relaxed text-slate-300 shadow-xl group-hover:block">
        {text}
      </span>
    </span>
  );
}
