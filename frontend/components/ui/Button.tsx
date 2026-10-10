import React from "react";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/cn";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-accent-strong text-white hover:bg-accent border border-transparent",
  secondary: "bg-surface-2 text-fg hover:bg-surface-3 border border-line",
  ghost: "bg-transparent text-fg-muted hover:text-fg hover:bg-surface-2 border border-transparent",
  danger: "bg-danger/10 text-danger hover:bg-danger/20 border border-danger/30",
};

const SIZES: Record<Size, string> = {
  sm: "h-7 px-2.5 text-xs gap-1.5",
  md: "h-8 px-3 text-[13px] gap-2",
};

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "secondary", size = "md", loading = false, disabled, className, children, type = "button", ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(
        "inline-flex select-none items-center justify-center whitespace-nowrap rounded-control font-medium transition-colors",
        "disabled:cursor-not-allowed disabled:opacity-50",
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
      {...rest}
    >
      {loading && <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />}
      {children}
    </button>
  );
});

export interface IconButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  label: string;
  size?: Size;
  tone?: "default" | "danger" | "ok";
}

/** Icon-only button. `label` is required so it always has an accessible name. */
export const IconButton = React.forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  { label, size = "md", tone = "default", className, children, type = "button", ...rest },
  ref,
) {
  const toneClass = {
    default: "text-fg-muted hover:text-fg hover:bg-surface-2",
    danger: "text-fg-muted hover:text-danger hover:bg-danger/10",
    ok: "text-fg-muted hover:text-ok hover:bg-ok/10",
  }[tone];
  return (
    <button
      ref={ref}
      type={type}
      aria-label={label}
      title={label}
      className={cn(
        "inline-flex items-center justify-center rounded-control transition-colors disabled:cursor-not-allowed disabled:opacity-50",
        size === "sm" ? "h-7 w-7" : "h-8 w-8",
        toneClass,
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  );
});
