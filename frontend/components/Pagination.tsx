import React from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { PaginationMeta } from "@/types";

interface PaginationProps {
  meta: PaginationMeta;
  onPageChange: (newPage: number) => void;
}

export const Pagination: React.FC<PaginationProps> = ({ meta, onPageChange }) => {
  const { page, total_pages, total } = meta;

  if (total_pages <= 1) return null;

  return (
    <div className="flex items-center justify-between px-4 py-3 border-t border-slate-800 text-xs text-slate-400">
      <div>
        Showing page <span className="text-white font-medium">{page}</span> of{" "}
        <span className="text-white font-medium">{total_pages}</span> ({total} tasks)
      </div>

      <div className="flex items-center gap-1.5">
        <button
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-800 transition-colors"
        >
          <ChevronLeft className="w-3.5 h-3.5" />
          <span>Prev</span>
        </button>

        <button
          onClick={() => onPageChange(page + 1)}
          disabled={page >= total_pages}
          className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-800 transition-colors"
        >
          <span>Next</span>
          <ChevronRight className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
};
