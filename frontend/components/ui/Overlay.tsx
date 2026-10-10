"use client";

import React, { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { cn } from "@/lib/cn";
import { IconButton } from "./Button";

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Trap keyboard focus inside `ref` while `active`, close on Escape, and restore focus
 * to the previously focused element on cleanup.
 */
export function useFocusTrap(ref: React.RefObject<HTMLElement>, active: boolean, onClose: () => void) {
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!active) return;
    const previous = document.activeElement as HTMLElement | null;
    const node = ref.current;
    const first = node?.querySelector<HTMLElement>("[data-autofocus]") ?? node?.querySelector<HTMLElement>(FOCUSABLE);
    first?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab" || !node) return;
      const items = Array.from(node.querySelectorAll<HTMLElement>(FOCUSABLE)).filter((el) => !el.closest("[hidden]"));
      if (items.length === 0) return;
      const firstEl = items[0];
      const lastEl = items[items.length - 1];
      if (event.shiftKey && document.activeElement === firstEl) {
        event.preventDefault();
        lastEl.focus();
      } else if (!event.shiftKey && document.activeElement === lastEl) {
        event.preventDefault();
        firstEl.focus();
      }
    };

    document.addEventListener("keydown", onKeyDown, true);
    const { overflow } = document.body.style;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKeyDown, true);
      document.body.style.overflow = overflow;
      previous?.focus?.();
    };
  }, [active, ref]);
}

interface OverlayProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}

function Overlay({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  variant,
}: OverlayProps & { variant: "modal" | "drawer" }) {
  const panelRef = useRef<HTMLDivElement>(null);
  useFocusTrap(panelRef, open, onClose);
  if (!open || typeof document === "undefined") return null;

  const titleId = "overlay-title";
  return createPortal(
    <div
      className={cn(
        "fixed inset-0 z-50 flex bg-black/60 animate-fade-in",
        variant === "modal" ? "items-center justify-center p-4" : "justify-end",
      )}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className={cn(
          "flex flex-col border border-line bg-surface-1",
          variant === "modal"
            ? "max-h-[90vh] w-full max-w-lg rounded-modal"
            : "h-full w-full max-w-md rounded-l-modal animate-slide-in-right",
        )}
      >
        <div className="flex items-start justify-between gap-3 border-b border-line-subtle px-5 py-4">
          <div>
            <h2 id={titleId} className="text-sm font-semibold text-fg">
              {title}
            </h2>
            {description && <p className="mt-0.5 text-xs text-fg-muted">{description}</p>}
          </div>
          <IconButton label="Close" size="sm" onClick={onClose}>
            <X className="h-4 w-4" />
          </IconButton>
        </div>
        <div className="flex-1 overflow-y-auto px-5 py-4">{children}</div>
        {footer && <div className="flex items-center justify-end gap-2 border-t border-line-subtle px-5 py-3">{footer}</div>}
      </div>
    </div>,
    document.body,
  );
}

export function Modal(props: OverlayProps) {
  return <Overlay {...props} variant="modal" />;
}

export function Drawer(props: OverlayProps) {
  return <Overlay {...props} variant="drawer" />;
}

/** Confirmation dialog for consequential actions; replaces window.confirm. */
export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  tone = "danger",
  note = "This is recorded in the task history.",
  onConfirm,
  onClose,
  loading,
}: {
  open: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  tone?: "danger" | "primary";
  note?: string;
  onConfirm: () => void;
  onClose: () => void;
  loading?: boolean;
}) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      description={description}
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            className="h-8 rounded-control px-3 text-[13px] text-fg-muted transition-colors hover:bg-surface-2 hover:text-fg"
          >
            Cancel
          </button>
          <button
            type="button"
            data-autofocus
            onClick={onConfirm}
            disabled={loading}
            className={cn(
              "h-8 rounded-control border px-3 text-[13px] font-medium transition-colors disabled:opacity-50",
              tone === "danger"
                ? "border-danger/30 bg-danger/10 text-danger hover:bg-danger/20"
                : "border-transparent bg-accent-strong text-white hover:bg-accent",
            )}
          >
            {loading ? "Working..." : confirmLabel}
          </button>
        </>
      }
    >
      {note && <p className="text-xs text-fg-muted">{note}</p>}
    </Modal>
  );
}
