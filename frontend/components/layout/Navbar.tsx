"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  Bell,
  Building2,
  LogOut,
  Menu,
  Moon,
  Search,
  Sun,
  UserRound,
} from "lucide-react";

import { logoutAccount } from "@/lib/api";
import {
  clearAuthSession,
  getActiveOrganizationSlug,
  getRefreshToken,
  getStoredUser,
} from "@/lib/auth";
import { useTheme } from "@/components/providers/ThemeProvider";
import type { AuthUser } from "@/types/api";

export function Navbar({ onOpenMobile }: { onOpenMobile: () => void }) {
  const { theme, toggleTheme } = useTheme();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [org, setOrg] = useState("default");
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const sync = () => {
      setUser(getStoredUser());
      setOrg(getActiveOrganizationSlug());
    };
    sync();
    window.addEventListener("ai-governance-auth", sync);
    window.addEventListener("ai-governance-org", sync);
    return () => {
      window.removeEventListener("ai-governance-auth", sync);
      window.removeEventListener("ai-governance-org", sync);
    };
  }, []);

  async function onLogout() {
    try {
      await logoutAccount(getRefreshToken());
    } catch {
      // best-effort
    }
    clearAuthSession();
    window.location.href = "/login";
  }

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border bg-card/90 px-4 backdrop-blur">
      <button
        type="button"
        className="rounded-lg p-2 text-muted-foreground hover:bg-muted lg:hidden"
        aria-label="Open navigation"
        onClick={onOpenMobile}
      >
        <Menu className="h-5 w-5" />
      </button>

      <div className="hidden items-center gap-2 rounded-xl border border-border bg-muted/60 px-3 py-1.5 text-sm text-muted-foreground md:flex">
        <Building2 className="h-4 w-4" />
        <span className="font-medium text-foreground">{org}</span>
      </div>

      <label className="relative ml-auto hidden min-w-[12rem] max-w-md flex-1 sm:block">
        <span className="sr-only">Search</span>
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <input
          type="search"
          placeholder="Search modules, policies, events…"
          className="w-full rounded-xl border border-border bg-background py-2 pl-9 pr-3 text-sm text-foreground placeholder:text-muted-foreground"
        />
      </label>

      <button
        type="button"
        className="rounded-lg p-2 text-muted-foreground hover:bg-muted"
        aria-label="Notifications"
      >
        <Bell className="h-4 w-4" />
      </button>

      <button
        type="button"
        className="rounded-lg p-2 text-muted-foreground hover:bg-muted"
        aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        onClick={toggleTheme}
      >
        {theme === "dark" ? (
          <Sun className="h-4 w-4" />
        ) : (
          <Moon className="h-4 w-4" />
        )}
      </button>

      <div className="relative">
        <button
          type="button"
          className="flex items-center gap-2 rounded-xl border border-border bg-background px-2.5 py-1.5 text-sm hover:bg-muted"
          aria-expanded={menuOpen}
          aria-haspopup="menu"
          onClick={() => setMenuOpen((v) => !v)}
        >
          <UserRound className="h-4 w-4 text-muted-foreground" />
          <span className="hidden max-w-[10rem] truncate sm:inline">
            {user?.email ?? "Account"}
          </span>
          {user?.role && (
            <span className="hidden rounded-md bg-muted px-1.5 py-0.5 text-[10px] font-medium uppercase text-muted-foreground md:inline">
              {user.role}
            </span>
          )}
        </button>
        {menuOpen && (
          <div
            role="menu"
            className="absolute right-0 mt-2 w-52 rounded-xl border border-border bg-card p-1 shadow-elevated"
          >
            <Link
              href="/settings?tab=profile"
              role="menuitem"
              className="block rounded-lg px-3 py-2 text-sm hover:bg-muted"
              onClick={() => setMenuOpen(false)}
            >
              Profile
            </Link>
            <button
              type="button"
              role="menuitem"
              className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-danger hover:bg-muted"
              onClick={() => void onLogout()}
            >
              <LogOut className="h-4 w-4" />
              Sign out
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
