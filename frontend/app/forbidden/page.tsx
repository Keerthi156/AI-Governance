"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { ShieldOff } from "lucide-react";

function ForbiddenBody() {
  const params = useSearchParams();
  const from = params.get("from");

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-md animate-fade-in rounded-2xl border border-border bg-card p-8 text-center shadow-elevated">
        <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-danger/10 text-danger">
          <ShieldOff className="h-7 w-7" aria-hidden />
        </div>
        <p className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          403
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-foreground">
          Access Denied
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          You don&apos;t have permission to access this module.
          {from ? (
            <>
              {" "}
              (<span className="font-mono text-xs">{from}</span>)
            </>
          ) : null}
        </p>
        <Link
          href="/dashboard"
          className="mt-6 inline-flex rounded-xl bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground hover:bg-accent"
        >
          Return to Dashboard
        </Link>
      </div>
    </main>
  );
}

export default function ForbiddenPage() {
  return (
    <Suspense fallback={null}>
      <ForbiddenBody />
    </Suspense>
  );
}
