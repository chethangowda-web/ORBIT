import React, { useId } from "react";
import { cn } from "@/lib/cn";

const CONTROL_BASE =
  "rounded-control border border-line bg-surface-2 px-3 text-[13px] text-fg placeholder:text-fg-faint " +
  "transition-colors hover:border-fg-faint focus:border-accent focus:outline-none disabled:opacity-50";
const CONTROL = `w-full ${CONTROL_BASE}`;

interface FieldShellProps {
  label: string;
  hint?: string;
  error?: string | null;
  required?: boolean;
  className?: string;
  children: (props: { id: string; describedBy: string | undefined; invalid: boolean }) => React.ReactNode;
}

/** Label + control + hint/error wiring so every input is accessible by default. */
function FieldShell({ label, hint, error, required, className, children }: FieldShellProps) {
  const id = useId();
  const messageId = `${id}-msg`;
  const describedBy = error || hint ? messageId : undefined;
  return (
    <div className={cn("space-y-1", className)}>
      <label htmlFor={id} className="block text-xs font-medium text-fg-muted">
        {label}
        {required && <span className="text-danger"> *</span>}
      </label>
      {children({ id, describedBy, invalid: Boolean(error) })}
      {(error || hint) && (
        <p id={messageId} className={cn("text-[11px]", error ? "text-danger" : "text-fg-faint")}>
          {error || hint}
        </p>
      )}
    </div>
  );
}

type BaseProps = Omit<FieldShellProps, "children">;

export const Input = React.forwardRef<
  HTMLInputElement,
  BaseProps & Omit<React.InputHTMLAttributes<HTMLInputElement>, "className"> & { inputClassName?: string }
>(function Input({ label, hint, error, className, inputClassName, required, ...rest }, ref) {
  return (
    <FieldShell label={label} hint={hint} error={error} required={required} className={className}>
      {({ id, describedBy, invalid }) => (
        <input
          ref={ref}
          id={id}
          aria-describedby={describedBy}
          aria-invalid={invalid || undefined}
          required={required}
          className={cn(CONTROL, "h-8", invalid && "border-danger", inputClassName)}
          {...rest}
        />
      )}
    </FieldShell>
  );
});

export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  BaseProps & Omit<React.TextareaHTMLAttributes<HTMLTextAreaElement>, "className">
>(function Textarea({ label, hint, error, className, required, ...rest }, ref) {
  return (
    <FieldShell label={label} hint={hint} error={error} required={required} className={className}>
      {({ id, describedBy, invalid }) => (
        <textarea
          ref={ref}
          id={id}
          aria-describedby={describedBy}
          aria-invalid={invalid || undefined}
          required={required}
          className={cn(CONTROL, "py-2", invalid && "border-danger")}
          {...rest}
        />
      )}
    </FieldShell>
  );
});

export interface SelectOption {
  value: string;
  label: string;
}

export const Select = React.forwardRef<
  HTMLSelectElement,
  BaseProps &
    Omit<React.SelectHTMLAttributes<HTMLSelectElement>, "className"> & {
      options: SelectOption[];
      selectClassName?: string;
    }
>(function Select({ label, hint, error, className, selectClassName, options, required, ...rest }, ref) {
  return (
    <FieldShell label={label} hint={hint} error={error} required={required} className={className}>
      {({ id, describedBy, invalid }) => (
        <select
          ref={ref}
          id={id}
          aria-describedby={describedBy}
          aria-invalid={invalid || undefined}
          required={required}
          className={cn(CONTROL, "h-8 pr-7", invalid && "border-danger", selectClassName)}
          {...rest}
        >
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      )}
    </FieldShell>
  );
});

/** Compact select for toolbars, where the label is visually hidden but still announced. */
export function CompactSelect({
  label,
  value,
  onChange,
  options,
  className,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: SelectOption[];
  className?: string;
}) {
  return (
    <select
      aria-label={label}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={cn(CONTROL_BASE, "h-8 w-auto pr-7", className)}
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}
