"use client";

import React, { useState } from "react";
import { MessageSquare, Trash2 } from "lucide-react";
import { Button, IconButton } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/Overlay";
import { Avatar, ErrorState, Panel, PanelHeader, Skeleton } from "@/components/ui/Primitives";
import { useAuth } from "@/lib/auth";
import { formatDateTime, timeAgo } from "@/lib/format";
import { useAddComment, useComments, useDeleteComment } from "@/lib/hooks";
import type { TaskComment } from "@/types";

const MAX_LENGTH = 2000;

export function Comments({ taskId }: { taskId: string }) {
  const { user, isManager } = useAuth();
  const { data: comments = [], isLoading, error, refetch } = useComments(taskId);
  const add = useAddComment(taskId);
  const remove = useDeleteComment(taskId);
  const [draft, setDraft] = useState("");
  const [toDelete, setToDelete] = useState<TaskComment | null>(null);

  const trimmed = draft.trim();
  const submit = () => {
    if (!trimmed || add.isPending) return;
    add.mutate(trimmed, { onSuccess: () => setDraft("") });
  };

  return (
    <Panel>
      <PanelHeader
        title="Comments"
        description="The assignee and creator are notified in Google Chat."
        icon={<MessageSquare className="h-4 w-4" />}
      />
      <div className="space-y-4 p-5">
        {error ? (
          <ErrorState title="Could not load comments" error={error} onRetry={() => void refetch()} />
        ) : isLoading ? (
          <Skeleton className="h-12 w-full" />
        ) : comments.length === 0 ? (
          <p className="text-xs text-fg-muted">No comments yet. Start the discussion below.</p>
        ) : (
          <ul className="space-y-4">
            {comments.map((c) => {
              const canDelete = c.author?.id === user?.id || isManager;
              return (
                <li key={c.id} className="flex gap-3">
                  <Avatar name={c.author?.display_name} />
                  <div className="min-w-0 flex-1">
                    <p className="flex items-center gap-2 text-xs">
                      <span className="font-medium text-fg">{c.author?.display_name ?? "Former member"}</span>
                      <time dateTime={c.created_at} title={formatDateTime(c.created_at)} className="text-fg-faint">
                        {timeAgo(c.created_at)}
                      </time>
                      {canDelete && (
                        <IconButton label="Delete comment" size="sm" tone="danger" className="ml-auto" onClick={() => setToDelete(c)}>
                          <Trash2 className="h-3.5 w-3.5" />
                        </IconButton>
                      )}
                    </p>
                    {/* Plain text only: React escapes it, whitespace is preserved. */}
                    <p className="mt-0.5 whitespace-pre-wrap break-words text-[13px] leading-relaxed text-fg-muted">{c.body}</p>
                  </div>
                </li>
              );
            })}
          </ul>
        )}

        <form
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
          className="space-y-2 border-t border-line-subtle pt-4"
        >
          <label htmlFor="new-comment" className="text-xs font-medium text-fg-muted">
            Add a comment
          </label>
          <textarea
            id="new-comment"
            rows={3}
            maxLength={MAX_LENGTH}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
                e.preventDefault();
                submit();
              }
            }}
            placeholder="Write an update, question or decision"
            className="w-full rounded-control border border-line bg-surface-2 px-3 py-2 text-[13px] text-fg placeholder:text-fg-faint transition-colors hover:border-fg-faint focus:border-accent focus:outline-none"
          />
          <div className="flex items-center justify-between">
            <span className="num text-[11px] text-fg-faint">
              {draft.length > MAX_LENGTH - 200 ? `${draft.length}/${MAX_LENGTH}` : "Ctrl+Enter to send"}
            </span>
            <Button type="submit" variant="primary" size="sm" loading={add.isPending} disabled={!trimmed}>
              Comment
            </Button>
          </div>
        </form>
      </div>

      <ConfirmDialog
        open={toDelete !== null}
        title="Delete this comment?"
        description="It will be removed for everyone."
        confirmLabel="Delete comment"
        note="Comments cannot be restored."
        loading={remove.isPending}
        onClose={() => setToDelete(null)}
        onConfirm={() => toDelete && remove.mutate(toDelete.id, { onSuccess: () => setToDelete(null) })}
      />
    </Panel>
  );
}
