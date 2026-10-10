import React from "react";
import Link from "next/link";
import { AlertTriangle, Inbox } from "lucide-react";
import { cn } from "@/lib/cn";
import { initials } from "@/lib/format";
import { Button } from "./Button";

export function Panel({
  className,
  children,
  as: Tag = "section",
  ...rest
}: React.HTMLAttributes<HTMLElement> & { as?: React.ElementType }) {
  return (
    <Tag className={cn("rounded-panel border border-line bg-surface-1", className)} {...rest}>
      {children}
    </Tag>
  );
}

export function PanelHeader({
  title,
  description,
  actions,
  icon,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
  icon?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-line-subtle px-4 py-3">
      <div className="flex min-w-0 items-center gap-2.5">
        {icon && <span className="text-fg-faint">{icon}</span>}
        <div className="min-w-0">
          <h2 className="section-label">{title}</h2>
          {description && <p className="mt-0.5 truncate text-xs text-fg-muted">{description}</p>}
        </div>
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn("animate-pulse rounded-control bg-surface-3/70", className)} />;
}

export function EmptyState({
  title,
  description,
  action,
  icon,
  className,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
  icon?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-panel border border-dashed border-line px-6 py-10 text-center",
        className,
      )}
    >
      <span className="mb-2 text-fg-faint">{icon ?? <Inbox className="h-5 w-5" aria-hidden />}</span>
      <p className="text-[13px] font-medium text-fg">{title}</p>
      {description && <p className="mt-1 max-w-sm text-xs text-fg-muted">{description}</p>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}

export function ErrorState({
  title = "Could not load this",
  error,
  onRetry,
  className,
}: {
  title?: string;
  error?: unknown;
  onRetry?: () => void;
  className?: string;
}) {
  const message = error instanceof Error ? error.message : typeof error === "string" ? error : undefined;
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center justify-center rounded-panel border border-danger/30 bg-danger/5 px-6 py-8 text-center",
        className,
      )}
    >
      <AlertTriangle className="mb-2 h-5 w-5 text-danger" aria-hidden />
      <p className="text-[13px] font-medium text-fg">{title}</p>
      {message && <p className="mt-1 max-w-md text-xs text-fg-muted">{message}</p>}
      {onRetry && (
        <Button size="sm" className="mt-3" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}

export function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="inline-flex h-5 min-w-[20px] items-center justify-center rounded border border-line bg-surface-2 px-1 font-mono text-[10px] text-fg-muted">
      {children}
    </kbd>
  );
}

export function Avatar({
  name,
  size = "md",
  className,
}: {
  name?: string | null;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const sizes = { sm: "h-5 w-5 text-[9px]", md: "h-6 w-6 text-[10px]", lg: "h-9 w-9 text-xs" };
  return (
    <span
      aria-hidden
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-control border border-line bg-surface-3 font-semibold text-accent",
        sizes[size],
        className,
      )}
    >
      {initials(name)}
    </span>
  );
}

export function MetricTile({
  label,
  value,
  tone = "default",
  hint,
  loading,
  href,
}: {
  label: string;
  value: React.ReactNode;
  tone?: "default" | "info" | "ok" | "danger" | "warn";
  hint?: string;
  loading?: boolean;
  href?: string;
}) {
  const toneClass = { default: "text-fg", info: "text-info", ok: "text-ok", danger: "text-danger", warn: "text-warn" }[tone];
  const body = (
    <>
      <p className="section-label">{label}</p>
      {loading ? (
        <Skeleton className="mt-2 h-7 w-14" />
      ) : (
        <p className={cn("num mt-1 text-2xl font-semibold leading-none", toneClass)}>{value}</p>
      )}
      {hint && <p className="mt-1.5 truncate text-[11px] text-fg-faint">{hint}</p>}
    </>
  );
  const classes = "block rounded-panel border border-line bg-surface-1 px-4 py-3";
  if (href) {
    return (
      <Link href={href} className={cn(classes, "transition-colors hover:border-fg-faint")}>
        {body}
      </Link>
    );
  }
  return <div className={classes}>{body}</div>;
}

/** Page container: consistent title row and padding for every screen. */
export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-lg font-semibold leading-tight text-fg">{title}</h1>
        {description && <p className="mt-0.5 text-xs text-fg-muted">{description}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}
