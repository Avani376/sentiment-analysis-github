/** Auth gate: session check, login/register screen, shared auth context. */

import { createContext, useContext, useState, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CircleAlert, SentinexLogo } from "./icons";
import { Button } from "./ui";
import { ApiError } from "../lib/api";
import { login, logout, me, register, type UserOut } from "../lib/auth";

interface AuthContextValue {
  user: UserOut;
  logout: () => Promise<void>;
  loggingOut: boolean;
}

const AuthContext = createContext<AuthContextValue>({
  user: { id: "", username: "", display_name: null },
  logout: async () => {},
  loggingOut: false,
});

export function useAuth() {
  return useContext(AuthContext);
}

function useSession() {
  return useQuery({
    queryKey: ["me"],
    queryFn: me,
    retry: false,
    staleTime: 5 * 60_000,
  });
}

function LoginScreen({ onAuthed }: { onAuthed: () => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setError(null);
    setBusy(true);
    try {
      if (mode === "register") {
        await register(username.trim(), password, displayName.trim() || undefined);
        await login(username.trim(), password);
      } else {
        await login(username.trim(), password);
      }
      onAuthed();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Authentication failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="app-backdrop flex min-h-full items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <SentinexLogo className="h-14 w-14" />
          <div>
            <p className="text-xl font-bold tracking-tight">
              <span className="accent-gradient-text">SENTINEX</span>{" "}
              <span className="text-slate-200">AI</span>
            </p>
            <p className="mt-1 text-xs text-slate-500">
              Review Intelligence Platform — sign in to continue
            </p>
          </div>
        </div>

        <div className="card p-6">
          <div className="mb-5 flex gap-1.5 rounded-xl bg-white/5 p-1 text-sm">
            {(["login", "register"] as const).map((m) => (
              <button
                key={m}
                onClick={() => {
                  setMode(m);
                  setError(null);
                }}
                className={`flex-1 rounded-lg px-3 py-1.5 transition ${
                  mode === m
                    ? "bg-indigo-500/25 font-medium text-indigo-100"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                {m === "login" ? "Sign in" : "Create account"}
              </button>
            ))}
          </div>

          <form
            className="space-y-3"
            onSubmit={(e) => {
              e.preventDefault();
              void submit();
            }}
          >
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Username"
              autoComplete="username"
              className="w-full rounded-xl border border-[var(--color-edge)] bg-[var(--color-base)]/60 px-4 py-2.5 text-sm text-slate-200 outline-none placeholder:text-slate-600 focus:border-indigo-500/50"
            />
            {mode === "register" && (
              <input
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="Display name (optional)"
                className="w-full rounded-xl border border-[var(--color-edge)] bg-[var(--color-base)]/60 px-4 py-2.5 text-sm text-slate-200 outline-none placeholder:text-slate-600 focus:border-indigo-500/50"
              />
            )}
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={mode === "register" ? "Password (min 8 characters)" : "Password"}
              autoComplete={mode === "register" ? "new-password" : "current-password"}
              className="w-full rounded-xl border border-[var(--color-edge)] bg-[var(--color-base)]/60 px-4 py-2.5 text-sm text-slate-200 outline-none placeholder:text-slate-600 focus:border-indigo-500/50"
            />
            {error && (
              <p className="flex items-center gap-1.5 rounded-lg bg-rose-500/10 px-3 py-2 text-xs text-rose-300">
                <CircleAlert className="h-3.5 w-3.5 shrink-0" /> {error}
              </p>
            )}
            <Button type="submit" disabled={busy || !username || !password} className="w-full">
              {busy ? "Working…" : mode === "login" ? "Sign in" : "Create account & sign in"}
            </Button>
          </form>

          <p className="mt-4 text-center text-[11px] leading-relaxed text-slate-600">
            Demo authentication: registration is open and sessions last 7 days.
            Passwords are stored scrypt-hashed; sessions are HttpOnly cookies.
          </p>
        </div>
      </div>
    </div>
  );
}

export function AuthGate({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const { data: user, isLoading } = useSession();
  const [loggingOut, setLoggingOut] = useState(false);

  if (isLoading) {
    return (
      <div className="app-backdrop flex min-h-full items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <SentinexLogo className="h-12 w-12 animate-pulse" />
          <p className="text-xs text-slate-500">Restoring session…</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <LoginScreen
        onAuthed={() => {
          void queryClient.invalidateQueries();
        }}
      />
    );
  }

  const doLogout = async () => {
    setLoggingOut(true);
    try {
      await logout();
    } finally {
      setLoggingOut(false);
      queryClient.clear();
      void queryClient.invalidateQueries();
    }
  };

  return (
    <AuthContext.Provider value={{ user, logout: doLogout, loggingOut }}>{children}</AuthContext.Provider>
  );
}

