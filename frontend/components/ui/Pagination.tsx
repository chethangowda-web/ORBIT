import React from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "./Button";
import type { PaginationMeta } from "@/types";

export function Pagination({
  meta,
  noun = "items",
  onPageChange,
}: {
  meta: PaginationMeta;
  noun?: string;
  onPageChange: (page: number) => void;
}) {
  if (meta.total === 0) return null;
  const first = (meta.page - 1) * meta.page_size + 1;
  const last = Math.min(meta.page * meta.page_size, meta.total);
  return (
    <nav aria-label="Pagination" className="flex items-center justify-between pt-3 text-xs text-fg-muted">
      <p>
        <span className="num text-fg">
          {first}-{last}
        </span>{" "}
        of <span className="num text-fg">{meta.total}</span> {noun}
      </p>
      {meta.total_pages > 1 && (
        <div className="flex items-center gap-1.5">
          <Button size="sm" disabled={meta.page <= 1} onClick={() => onPageChange(meta.page - 1)}>
            <ChevronLeft className="h-3.5 w-3.5" aria-hidden />
            Previous
          </Button>
          <span className="num px-1">
            {meta.page} / {meta.total_pages}
          </span>
          <Button size="sm" disabled={meta.page >= meta.total_pages} onClick={() => onPageChange(meta.page + 1)}>
            Next
            <ChevronRight className="h-3.5 w-3.5" aria-hidden />
          </Button>
        </div>
      )}
    </nav>
  );
}
