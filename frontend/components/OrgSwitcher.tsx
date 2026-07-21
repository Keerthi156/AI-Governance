"use client";

/**
 * Active organization switcher + membership management.
 */

import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";

import {
  ApiError,
  addOrganizationMember,
  createOrganization,
  createOrganizationInvite,
  fetchOrganizationInvites,
  fetchOrganizationMembers,
  fetchOrganizations,
  removeOrganizationMember,
  revokeOrganizationInvite,
} from "@/lib/api";
import {
  getAccessToken,
  getActiveOrganizationSlug,
  getStoredUser,
  setActiveOrganizationSlug,
} from "@/lib/auth";
import type {
  AuthUser,
  Organization,
  OrganizationInvite,
  OrganizationMember,
} from "@/types/api";

export function OrgSwitcher() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [orgs, setOrgs] = useState<Organization[]>([]);
  const [members, setMembers] = useState<OrganizationMember[]>([]);
  const [invites, setInvites] = useState<OrganizationInvite[]>([]);
  const [activeSlug, setActiveSlug] = useState("default");
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [memberEmail, setMemberEmail] = useState("");
  const [memberRole, setMemberRole] = useState("member");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("member");
  const [lastInviteToken, setLastInviteToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const canRead = Boolean(user?.permissions?.includes("organizations:read"));
  const canManage = Boolean(user?.permissions?.includes("organizations:manage"));
  const canManageMembers =
    canManage ||
    members.some(
      (m) => m.user_id === user?.id && m.membership_role === "admin",
    );

  const loadMembers = useCallback(async (orgSlug: string) => {
    if (!getAccessToken()) {
      setMembers([]);
      setInvites([]);
      return;
    }
    try {
      setMembers(await fetchOrganizationMembers(orgSlug));
    } catch {
      setMembers([]);
    }
    try {
      setInvites(await fetchOrganizationInvites(orgSlug));
    } catch {
      setInvites([]);
    }
  }, []);

  const load = useCallback(async () => {
    const stored = getStoredUser();
    setUser(stored);
    const current = getActiveOrganizationSlug();
    setActiveSlug(current);
    if (!getAccessToken() || !stored?.permissions?.includes("organizations:read")) {
      setOrgs([]);
      setMembers([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const rows = await fetchOrganizations();
      setOrgs(rows);
      if (rows.length > 0 && !rows.some((o) => o.slug === current)) {
        setActiveOrganizationSlug(rows[0].slug);
        setActiveSlug(rows[0].slug);
        await loadMembers(rows[0].slug);
      } else {
        await loadMembers(current);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load organizations");
    } finally {
      setLoading(false);
    }
  }, [loadMembers]);

  useEffect(() => {
    void load();
    const onAuth = () => void load();
    window.addEventListener("ai-governance-auth", onAuth);
    window.addEventListener("ai-governance-org", onAuth);
    window.addEventListener("storage", onAuth);
    return () => {
      window.removeEventListener("ai-governance-auth", onAuth);
      window.removeEventListener("ai-governance-org", onAuth);
      window.removeEventListener("storage", onAuth);
    };
  }, [load]);

  function onSelect(slugValue: string) {
    setActiveOrganizationSlug(slugValue);
    setActiveSlug(slugValue);
    setMessage(`Active organization: ${slugValue}`);
    void loadMembers(slugValue);
  }

  async function onCreate(event: FormEvent) {
    event.preventDefault();
    if (!canManage || !name.trim() || !slug.trim()) return;
    setError(null);
    setMessage(null);
    try {
      const created = await createOrganization({
        name: name.trim(),
        slug: slug.trim().toLowerCase(),
      });
      setOrgs((prev) =>
        [...prev.filter((o) => o.id !== created.id), created].sort((a, b) =>
          a.slug.localeCompare(b.slug),
        ),
      );
      setActiveOrganizationSlug(created.slug);
      setActiveSlug(created.slug);
      setName("");
      setSlug("");
      setMessage(`Created and selected “${created.name}”`);
      await loadMembers(created.slug);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Create failed");
    }
  }

  async function onAddMember(event: FormEvent) {
    event.preventDefault();
    if (!canManageMembers || !memberEmail.trim()) return;
    setError(null);
    setMessage(null);
    try {
      const added = await addOrganizationMember(activeSlug, {
        email: memberEmail.trim(),
        role: memberRole,
      });
      setMembers((prev) =>
        [...prev.filter((m) => m.user_id !== added.user_id), added].sort((a, b) =>
          a.email.localeCompare(b.email),
        ),
      );
      setMemberEmail("");
      setMessage(`Added ${added.email} to ${activeSlug}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Add member failed");
    }
  }

  async function onRemoveMember(userId: string, email: string) {
    if (!canManageMembers) return;
    setError(null);
    try {
      await removeOrganizationMember(activeSlug, userId);
      setMembers((prev) => prev.filter((m) => m.user_id !== userId));
      setMessage(`Removed ${email} from ${activeSlug}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Remove failed");
    }
  }

  async function onCreateInvite(event: FormEvent) {
    event.preventDefault();
    if (!canManageMembers) return;
    setError(null);
    setMessage(null);
    setLastInviteToken(null);
    try {
      const created = await createOrganizationInvite(activeSlug, {
        email: inviteEmail.trim() || null,
        role: inviteRole,
        expires_in_hours: 72,
      });
      setInvites((prev) => [created, ...prev]);
      setInviteEmail("");
      if (created.token) {
        setLastInviteToken(created.token);
        setMessage(`Invite created — copy token now (shown once)`);
      } else {
        setMessage("Invite created");
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Invite failed");
    }
  }

  async function onRevokeInvite(inviteId: string) {
    if (!canManageMembers) return;
    try {
      await revokeOrganizationInvite(activeSlug, inviteId);
      setInvites((prev) => prev.filter((i) => i.id !== inviteId));
      setMessage("Invite revoked");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Revoke failed");
    }
  }

  if (!getAccessToken()) {
    return null;
  }

  return (
    <section className="w-full max-w-5xl border border-zinc-200 bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Organization
          </h2>
          <p className="mt-1 text-sm text-zinc-500">
            Switch among orgs you belong to. Home org (JWT/RBAC):{" "}
            <span className="font-medium text-zinc-700">
              {user?.organization_slug ?? "—"}
            </span>
          </p>
        </div>
        <button
          type="button"
          onClick={() => void load()}
          className="border border-zinc-200 px-3 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-50"
        >
          Refresh
        </button>
      </div>

      {!canRead && (
        <p className="mt-4 text-sm text-zinc-600">
          Sign in again to refresh permissions for organization switching.
        </p>
      )}

      {error && (
        <div className="mt-4 border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          {error}
        </div>
      )}
      {message && (
        <div className="mt-4 border border-zinc-200 bg-zinc-50 p-3 text-sm text-zinc-700">
          {message}
        </div>
      )}

      {canRead && (
        <label className="mt-4 block text-sm">
          <span className="text-zinc-600">Active organization</span>
          <select
            value={activeSlug}
            onChange={(e) => onSelect(e.target.value)}
            disabled={loading || orgs.length === 0}
            className="mt-1 w-full border border-zinc-200 px-3 py-2 text-sm"
          >
            {orgs.length === 0 ? (
              <option value={activeSlug}>{activeSlug}</option>
            ) : (
              <>
                {!orgs.some((o) => o.slug === activeSlug) && (
                  <option value={activeSlug}>{activeSlug}</option>
                )}
                {orgs.map((org) => (
                  <option key={org.id} value={org.slug}>
                    {org.name} ({org.slug})
                  </option>
                ))}
              </>
            )}
          </select>
        </label>
      )}

      {canManage && (
        <form className="mt-4 flex flex-wrap items-end gap-2" onSubmit={onCreate}>
          <label className="min-w-[10rem] flex-1 text-sm">
            <span className="text-zinc-600">Name</span>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-1 w-full border border-zinc-200 px-3 py-2 text-sm"
              required
            />
          </label>
          <label className="min-w-[10rem] flex-1 text-sm">
            <span className="text-zinc-600">Slug</span>
            <input
              value={slug}
              onChange={(e) => setSlug(e.target.value.toLowerCase())}
              placeholder="acme-corp"
              pattern="^[a-z0-9]+(?:-[a-z0-9]+)*$"
              className="mt-1 w-full border border-zinc-200 px-3 py-2 text-sm"
              required
            />
          </label>
          <button
            type="submit"
            className="border border-zinc-900 bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800"
          >
            Create org
          </button>
        </form>
      )}

      {canRead && (
        <div className="mt-6">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
            Members · {activeSlug}
          </h3>
          {members.length === 0 ? (
            <p className="mt-2 text-sm text-zinc-600">No members loaded.</p>
          ) : (
            <ul className="mt-3 space-y-2">
              {members.map((m) => (
                <li
                  key={m.id}
                  className="flex flex-wrap items-center justify-between gap-2 border border-zinc-100 bg-zinc-50 px-3 py-2 text-sm"
                >
                  <div>
                    <span className="font-medium text-zinc-900">{m.email}</span>
                    <span className="ml-2 text-xs text-zinc-500">
                      {m.membership_role}
                      {m.full_name ? ` · ${m.full_name}` : ""}
                    </span>
                  </div>
                  {canManageMembers && m.user_id !== user?.id && (
                    <button
                      type="button"
                      onClick={() => void onRemoveMember(m.user_id, m.email)}
                      className="border border-zinc-200 px-2 py-1 text-xs hover:bg-white"
                    >
                      Remove
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}

          {canManageMembers && (
            <form
              className="mt-3 flex flex-wrap items-end gap-2"
              onSubmit={onAddMember}
            >
              <label className="min-w-[12rem] flex-1 text-sm">
                <span className="text-zinc-600">Add member by email</span>
                <input
                  type="email"
                  value={memberEmail}
                  onChange={(e) => setMemberEmail(e.target.value)}
                  placeholder="user@example.com"
                  className="mt-1 w-full border border-zinc-200 px-3 py-2 text-sm"
                  required
                />
              </label>
              <label className="text-sm">
                <span className="text-zinc-600">Role</span>
                <select
                  value={memberRole}
                  onChange={(e) => setMemberRole(e.target.value)}
                  className="mt-1 block border border-zinc-200 px-3 py-2 text-sm"
                >
                  <option value="viewer">viewer</option>
                  <option value="member">member</option>
                  <option value="admin">admin</option>
                </select>
              </label>
              <button
                type="submit"
                className="border border-zinc-200 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50"
              >
                Add member
              </button>
            </form>
          )}

          {canManageMembers && (
            <form
              className="mt-4 flex flex-wrap items-end gap-2"
              onSubmit={onCreateInvite}
            >
              <label className="min-w-[12rem] flex-1 text-sm">
                <span className="text-zinc-600">
                  Invite email (optional lock)
                </span>
                <input
                  type="email"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  placeholder="optional@example.com"
                  className="mt-1 w-full border border-zinc-200 px-3 py-2 text-sm"
                />
              </label>
              <label className="text-sm">
                <span className="text-zinc-600">Invite role</span>
                <select
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value)}
                  className="mt-1 block border border-zinc-200 px-3 py-2 text-sm"
                >
                  <option value="viewer">viewer</option>
                  <option value="member">member</option>
                  <option value="admin">admin</option>
                </select>
              </label>
              <button
                type="submit"
                className="border border-zinc-900 bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800"
              >
                Create invite
              </button>
            </form>
          )}

          {lastInviteToken && (
            <div className="mt-3 break-all border border-zinc-200 bg-zinc-50 p-3 text-xs text-zinc-800">
              Token (copy now): {lastInviteToken}
            </div>
          )}

          {canManageMembers && invites.length > 0 && (
            <ul className="mt-3 space-y-1 text-xs text-zinc-600">
              {invites.slice(0, 8).map((inv) => (
                <li
                  key={inv.id}
                  className="flex flex-wrap items-center justify-between gap-2 border border-zinc-100 px-2 py-1.5"
                >
                  <span>
                    …{inv.token_hint} · {inv.role} ·{" "}
                    {inv.email ?? "open"} ·{" "}
                    {inv.accepted_at
                      ? "accepted"
                      : inv.revoked_at
                        ? "revoked"
                        : `expires ${new Date(inv.expires_at).toLocaleString()}`}
                  </span>
                  {!inv.accepted_at && !inv.revoked_at && (
                    <button
                      type="button"
                      onClick={() => void onRevokeInvite(inv.id)}
                      className="border border-zinc-200 px-2 py-0.5 hover:bg-white"
                    >
                      Revoke
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}
