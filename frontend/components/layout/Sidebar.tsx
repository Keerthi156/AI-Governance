"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronLeft, ChevronRight, ShieldCheck, X } from "lucide-react";

import { useAuthz } from "@/hooks/useAuthz";
import { getNavigationForRole } from "@/lib/navigation";

export function Sidebar({
  collapsed,
  onToggleCollapse,
  mobileOpen,
  onCloseMobile,
}: {
  collapsed: boolean;
  onToggleCollapse: () => void;
  mobileOpen: boolean;
  onCloseMobile: () => void;
}) {
  const pathname = usePathname();
  const { role } = useAuthz();
  const navigation = getNavigationForRole(role);

  const nav = (
    <nav className="flex h-full flex-col" aria-label="Primary">
      <div className="flex h-14 items-center justify-between border-b border-sidebar-border px-4">
        <Link
          href="/dashboard"
          className="flex items-center gap-2 font-semibold text-foreground"
          onClick={onCloseMobile}
        >
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <ShieldCheck className="h-4 w-4" />
          </span>
          {!collapsed && (
            <span className="truncate text-sm tracking-tight">AI Governance</span>
          )}
        </Link>
        <button
          type="button"
          className="rounded-md p-1 text-muted-foreground hover:bg-muted lg:hidden"
          aria-label="Close menu"
          onClick={onCloseMobile}
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-2 py-3">
        <ul className="space-y-0.5">
          {navigation.map((item) => {
            const active =
              pathname === item.href || pathname.startsWith(`${item.href}/`);
            const Icon = item.icon;
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  onClick={onCloseMobile}
                  aria-current={active ? "page" : undefined}
                  title={item.label}
                  className={`flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition ${
                    active
                      ? "bg-sidebar-active font-medium text-primary"
                      : "text-sidebar-foreground hover:bg-muted"
                  } ${collapsed ? "justify-center px-2" : ""}`}
                >
                  <Icon className="h-4 w-4 shrink-0" aria-hidden />
                  {!collapsed && <span className="truncate">{item.label}</span>}
                </Link>
              </li>
            );
          })}
        </ul>
      </div>

      <div className="hidden border-t border-sidebar-border p-2 lg:block">
        <button
          type="button"
          onClick={onToggleCollapse}
          className="flex w-full items-center justify-center gap-2 rounded-xl px-3 py-2 text-xs text-muted-foreground hover:bg-muted"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <>
              <ChevronLeft className="h-4 w-4" />
              Collapse
            </>
          )}
        </button>
      </div>
    </nav>
  );

  return (
    <>
      <aside
        className={`fixed inset-y-0 left-0 z-40 hidden border-r border-sidebar-border bg-sidebar transition-all duration-200 lg:flex lg:flex-col ${
          collapsed ? "w-[4.25rem]" : "w-64"
        }`}
      >
        {nav}
      </aside>

      <div
        className={`fixed inset-0 z-50 lg:hidden ${mobileOpen ? "" : "pointer-events-none"}`}
      >
        <button
          type="button"
          aria-label="Close navigation overlay"
          className={`absolute inset-0 bg-slate-950/40 transition ${
            mobileOpen ? "opacity-100" : "opacity-0"
          }`}
          onClick={onCloseMobile}
        />
        <aside
          className={`absolute inset-y-0 left-0 w-72 border-r border-sidebar-border bg-sidebar shadow-elevated transition-transform duration-200 ${
            mobileOpen ? "translate-x-0" : "-translate-x-full"
          }`}
        >
          {nav}
        </aside>
      </div>
    </>
  );
}
