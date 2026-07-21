"use client";

/**
 * Authentication panel — register / login / session status (JWT).
 */

import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import {
  ApiError,
  fetchCurrentUser,
  loginAccount,
  logoutAccount,
  registerAccount,
} from "@/lib/api";
import {
  clearAuthSession,
  getAccessToken,
  getActiveOrganizationSlug,
  getRefreshToken,
  getStoredUser,
  setAuthSession,
} from "@/lib/auth";
import type { AuthUser } from "@/types/api";

type Mode = "login" | "register";

export function AuthPanel() {
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("demo@example.com");
  const [password, setPassword] = useState("changeme123");
  const [fullName, setFullName] = useState("Demo User");
  const [inviteToken, setInviteToken] = useState("");
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = getAccessToken();
    const stored = getStoredUser();
    if (!token || !stored) return;
    setUser(stored);
    void fetchCurrentUser()
      .then((fresh) => {
        setUser(fresh);
        setAuthSession(token, fresh, getRefreshToken());
      })
      .catch(() => {
        clearAuthSession();
        setUser(null);
      });
  }, []);

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
      setUser(result.user);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Authentication failed");
    } finally {
      setLoading(false);
    }
  }

  async function onLogout() {
    try {
      await logoutAccount(getRefreshToken());
    } catch {
      // best-effort
    }
    clearAuthSession();
    setUser(null);
    setError(null);
  }

  return (
    <section className="w-full max-w-5xl border border-zinc-200 bg-white p-6 shadow-sm">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
        Authentication
      </h2>
      <p className="mt-1 text-sm text-zinc-500">
        JWT access tokens (Bearer). Session is stored locally; RBAC comes next.
      </p>

      {user ? (
        <div className="mt-4 space-y-3 text-sm">
          <div className="border border-zinc-100 bg-zinc-50 px-4 py-3">
            <p className="font-medium text-zinc-900">
              {user.full_name || user.email}
            </p>
            <p className="mt-1 text-zinc-600">{user.email}</p>
            <p className="mt-1 text-xs text-zinc-500">
              Role: {user.role} · Org: {user.organization_slug}
            </p>
            {user.permissions?.length ? (
              <p className="mt-2 text-xs leading-relaxed text-zinc-500">
                Permissions: {user.permissions.join(", ")}
              </p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onLogout}
            className="border border-zinc-200 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50"
          >
            Sign out
          </button>
        </div>
      ) : (
        <form className="mt-4 space-y-4" onSubmit={onSubmit}>
          <div className="flex gap-2 text-sm">
            <button
              type="button"
              onClick={() => setMode("login")}
              className={
                mode === "login"
                  ? "border border-zinc-900 bg-zinc-900 px-3 py-1.5 text-white"
                  : "border border-zinc-200 px-3 py-1.5 text-zinc-700"
              }
            >
              Sign in
            </button>
            <button
              type="button"
              onClick={() => setMode("register")}
              className={
                mode === "register"
                  ? "border border-zinc-900 bg-zinc-900 px-3 py-1.5 text-white"
                  : "border border-zinc-200 px-3 py-1.5 text-zinc-700"
              }
            >
              Register
            </button>
          </div>

          {mode === "register" && (
            <label className="block text-sm">
              <span className="text-zinc-600">Full name</span>
              <input
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="mt-1 w-full border border-zinc-200 px-3 py-2 text-sm outline-none focus:border-zinc-400"
              />
            </label>
          )}

          <label className="block text-sm">
            <span className="text-zinc-600">Email</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 w-full border border-zinc-200 px-3 py-2 text-sm outline-none focus:border-zinc-400"
              required
            />
          </label>

          <label className="block text-sm">
            <span className="text-zinc-600">Password</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={8}
              className="mt-1 w-full border border-zinc-200 px-3 py-2 text-sm outline-none focus:border-zinc-400"
              required
            />
          </label>

          {mode === "register" && (
            <label className="block text-sm">
              <span className="text-zinc-600">
                Invite token (optional, join existing org)
              </span>
              <input
                value={inviteToken}
                onChange={(e) => setInviteToken(e.target.value)}
                placeholder="agi_…"
                className="mt-1 w-full border border-zinc-200 px-3 py-2 text-sm outline-none focus:border-zinc-400"
              />
            </label>
          )}

          {error && (
            <div className="border border-red-200 bg-red-50 p-3 text-sm text-red-800">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-50"
          >
            {loading
              ? "Please wait…"
              : mode === "register"
                ? "Create account"
                : "Sign in"}
          </button>
        </form>
      )}
    </section>
  );
}
