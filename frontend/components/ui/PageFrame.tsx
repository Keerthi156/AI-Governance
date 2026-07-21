"use client";

import Link from "next/link";
import type { ReactNode } from "react";

export function PageFrame({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={`feature-host animate-fade-in ${className}`}>{children}</div>
  );
}

export function QuickActionLink({
  href,
  children,
}: {
  href: string;
  children: ReactNode;
}) {
  return (
    <Link
      href={href}
      className="inline-flex items-center justify-center rounded-xl border border-border bg-card px-4 py-2 text-sm font-medium text-foreground shadow-card transition hover:border-primary hover:text-primary"
    >
      {children}
    </Link>
  );
}
