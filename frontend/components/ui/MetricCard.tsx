import type { ReactNode } from "react";

export function MetricCard({
  label,
  value,
  hint,
  icon,
  tone = "default",
}: {
  label: string;
  value: string;
  hint?: string;
  icon?: ReactNode;
  tone?: "default" | "success" | "warning" | "danger";
}) {
  const toneRing =
    tone === "success"
      ? "ring-success/20"
      : tone === "warning"
        ? "ring-warning/20"
        : tone === "danger"
          ? "ring-danger/20"
          : "ring-transparent";

  return (
    <div
      className={`rounded-2xl border border-border bg-card p-4 shadow-card ring-1 ${toneRing} animate-fade-in`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {label}
          </p>
          <p className="mt-2 text-2xl font-semibold tracking-tight text-foreground">
            {value}
          </p>
          {hint && (
            <p className="mt-1 text-xs text-muted-foreground">{hint}</p>
          )}
        </div>
        {icon && (
          <div className="rounded-xl bg-muted p-2.5 text-primary">{icon}</div>
        )}
      </div>
    </div>
  );
}
