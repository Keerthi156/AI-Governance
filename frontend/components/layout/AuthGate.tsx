"use client";

import { useEffect, useState, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";

import { getAccessToken } from "@/lib/auth";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";

export function AuthGate({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const token = getAccessToken();
    if (!token) {
      const next = encodeURIComponent(pathname || "/dashboard");
      router.replace(`/login?next=${next}`);
      if (!cancelled) setChecking(false);
      return () => {
        cancelled = true;
      };
    }
    if (!cancelled) {
      setReady(true);
      setChecking(false);
    }
    return () => {
      cancelled = true;
    };
  }, [pathname, router]);

  if (!ready) {
    if (!checking && !getAccessToken()) {
      return (
        <div className="mx-auto max-w-md py-24 text-center text-sm text-muted-foreground">
          Redirecting to sign in…
        </div>
      );
    }
    return (
      <div className="mx-auto max-w-3xl py-16">
        <LoadingSkeleton rows={4} />
      </div>
    );
  }

  return <>{children}</>;
}
