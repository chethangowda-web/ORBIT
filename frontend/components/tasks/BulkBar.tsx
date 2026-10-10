"use client";

import React, { useState } from "react";
import { CheckCheck, Trash2, X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { CompactSelect } from "@/components/ui/Field";
import { ConfirmDialog } from "@/components/ui/Overlay";
import { useAuth } from "@/lib/auth";
import { ALL_STATUSES, PRIORITIES, PRIORITY_LABEL, STATUS_LABEL } from "@/lib/constants";
import { useBulkAction, useUsers } from "@/lib/hooks";

/** Appears above the table while rows are selected. */
export function BulkBar({ ids, onClear }: { ids: string[]; onClear: () => void }) {
  const { user, isManager } = useAuth();
  const { data: users = [] } = useUsers();
  const [confirmDelete, setConfirmDelete] = useState(false);
  const bulk = useBulkAction(() => {
    setConfirmDelete(false);
    onClear();
  });

  const assignOptions = [
    { value: "", label: "Assign to..." },
    ...(isManager
      ? users.map((u) => ({ value: u.id, label: u.id === user?.id ? `${u.display_name} (you)` : u.display_name }))
      : [{ value: user?.id ?? "", label: "Me" }]),
    { value: "none", label: "Unassigned" },
  ];

  return (
    <div
      role="region"
      aria-label="Bulk actions"
      className="mb-3 flex flex-wrap items-center gap-2 rounded-panel border border-accent/40 bg-accent/10 px-3 py-2"
    >
      <span className="num mr-1 text-xs font-semibold text-fg">{ids.length} selected</span>

      <Button size="sm" variant="primary" disabled={bulk.isPending} onClick={() => bulk.mutate({ ids, action: "complete" })}>
        <CheckCheck className="h-3.5 w-3.5" aria-hidden /> Mark done
      </Button>
      <CompactSelect
        label="Set status for selected tasks"
        value=""
        onChange={(v) => v && bulk.mutate({ ids, action: "set_status", value: v })}
        options={[{ value: "", label: "Set status..." }, ...ALL_STATUSES.map((s) => ({ value: s, label: STATUS_LABEL[s] }))]}
      />
      <CompactSelect
        label="Set priority for selected tasks"
        value=""
        onChange={(v) => v && bulk.mutate({ ids, action: "set_priority", value: v })}
        options={[{ value: "", label: "Set priority..." }, ...PRIORITIES.map((p) => ({ value: p, label: PRIORITY_LABEL[p] }))]}
      />
      <CompactSelect
        label="Assign selected tasks"
        value=""
        onChange={(v) => v && bulk.mutate({ ids, action: "assign", value: v === "none" ? "" : v })}
        options={assignOptions}
      />
      {isManager && (
        <Button size="sm" variant="danger" disabled={bulk.isPending} onClick={() => setConfirmDelete(true)}>
          <Trash2 className="h-3.5 w-3.5" aria-hidden /> Delete
        </Button>
      )}

      <Button size="sm" variant="ghost" className="ml-auto" onClick={onClear}>
        <X className="h-3.5 w-3.5" aria-hidden /> Clear selection
      </Button>

      <ConfirmDialog
        open={confirmDelete}
        title={`Delete ${ids.length} task${ids.length === 1 ? "" : "s"}?`}
        description="They will be removed from the board and lists."
        confirmLabel="Delete tasks"
        loading={bulk.isPending}
        onClose={() => setConfirmDelete(false)}
        onConfirm={() => bulk.mutate({ ids, action: "delete" })}
      />
    </div>
  );
}
