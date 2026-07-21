"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ShieldCheck } from "lucide-react";

import { ApiError, loginAccount, registerAccount } from "@/lib/api";
import {
  getAccessToken,
  getActiveOrganizationSlug,
  setAuthSession,
} from "@/lib/auth";
import { useTheme } from "@/components/providers/ThemeProvider";

type Mode = "login" | "register";

const DEMO_ACCOUNTS = [
  {
    role: "Admin",
    email: "demo@example.com",
    password: "changeme123",
    note: "Full access",
  },
  {
    role: "Member",
    email: "member@example.com",
    password: "changeme123",
    note: "Limited access",
  },
  {
    role: "Viewer",
    email: "viewer@example.com",
    password: "changeme123",
    note: "Read-only",
  },
] as const;

export default function LoginClient() {
  const router = useRouter();
  const params = useSearchParams();
  const { theme, toggleTheme } = useTheme();
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("demo@example.com");
  const [password, setPassword] = useState("changeme123");
  const [fullName, setFullName] = useState("Demo User");
  const [inviteToken, setInviteToken] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function fillDemoAccount(account: (typeof DEMO_ACCOUNTS)[number]) {
    setMode("login");
    setEmail(account.email);
    setPassword(account.password);
    setError(null);
  }

  useEffect(() => {
    if (getAccessToken()) {
      router.replace(params.get("next") || "/dashboard");
    }
  }, [params, router]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const result =
        mode === "register"
          ? await registerAccount({
              email,
              password,
              full_name: fullName || null,
              organization_slug: getActiveOrganizationSlug(),
              invite_token: inviteToken.trim() || null,
            })
          : await loginAccount({ email, password });
      setAuthSession(
        result.access_token,
        result.user,
        result.refresh_token ?? null,
      );
      router.replace(params.get("next") || "/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Authentication failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4 py-12">
      <div className="w-full max-w-md animate-fade-in">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-card">
            <ShieldCheck className="h-6 w-6" />
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">AI Governance</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Enterprise multi-LLM platform for Fortune-grade teams
          </p>
        </div>

        <div className="rounded-2xl border border-border bg-card p-6 shadow-elevated">
          <div className="mb-4 flex gap-2">
            <button
              type="button"
              onClick={() => setMode("login")}
              className={`flex-1 rounded-xl px-3 py-2 text-sm font-medium ${
                mode === "login"
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground"
              }`}
            >
              Sign in
            </button>
            <button
              type="button"
              onClick={() => setMode("register")}
              className={`flex-1 rounded-xl px-3 py-2 text-sm font-medium ${
                mode === "register"
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground"
              }`}
            >
              Register
            </button>
          </div>

          <form className="space-y-3" onSubmit={onSubmit}>
            {mode === "register" && (
              <label className="block text-sm">
                <span className="text-muted-foreground">Full name</span>
                <input
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="mt-1 w-full rounded-xl border border-border bg-background px-3 py-2"
                />
              </label>
            )}
            <label className="block text-sm">
              <span className="text-muted-foreground">Email</span>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="mt-1 w-full rounded-xl border border-border bg-background px-3 py-2"
              />
            </label>
            <label className="block text-sm">
              <span className="text-muted-foreground">Password</span>
              <input
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="mt-1 w-full rounded-xl border border-border bg-background px-3 py-2"
              />
            </label>
            {mode === "register" && (
              <>
                <p className="rounded-xl border border-border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
                  New accounts join as <span className="font-medium text-foreground">Member</span>{" "}
                  (not full admin). Use an invite token only if an admin assigned you a higher role.
                </p>
                <label className="block text-sm">
                  <span className="text-muted-foreground">
                    Invite token (optional)
                  </span>
                  <input
                    value={inviteToken}
                    onChange={(e) => setInviteToken(e.target.value)}
                    placeholder="agi_…"
                    className="mt-1 w-full rounded-xl border border-border bg-background px-3 py-2"
                  />
                </label>
              </>
            )}
            {error && (
              <div className="rounded-xl border border-danger/30 bg-danger/10 p-3 text-sm text-danger">
                {error}
              </div>
            )}
            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-xl bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground hover:bg-accent disabled:opacity-60"
            >
              {loading
                ? "Please wait…"
                : mode === "login"
                  ? "Sign in"
                  : "Create member account"}
            </button>
          </form>
        </div>

        <div className="mt-4 rounded-2xl border border-dashed border-border bg-card/60 p-4 text-left shadow-card">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Demo test accounts
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            Click a row to fill the sign-in form. Password for all:{" "}
            <code className="rounded bg-muted px-1 py-0.5 text-[11px]">changeme123</code>
          </p>
          <ul className="mt-3 space-y-2">
            {DEMO_ACCOUNTS.map((account) => (
              <li key={account.email}>
                <button
                  type="button"
                  onClick={() => fillDemoAccount(account)}
                  className="flex w-full items-center justify-between gap-2 rounded-xl border border-border bg-background px-3 py-2 text-left text-xs transition hover:border-primary/40 hover:bg-muted/50"
                >
                  <span>
                    <span className="font-medium text-foreground">{account.role}</span>
                    <span className="mt-0.5 block font-mono text-[11px] text-muted-foreground">
                      {account.email}
                    </span>
                  </span>
                  <span className="shrink-0 text-[11px] text-muted-foreground">
                    {account.note}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>

        <div className="mt-4 flex justify-center">
          <button
            type="button"
            onClick={toggleTheme}
            className="text-xs text-muted-foreground hover:text-foreground"
          >
            Switch to {theme === "dark" ? "light" : "dark"} mode
          </button>
        </div>
      </div>
    </main>
  );
}
