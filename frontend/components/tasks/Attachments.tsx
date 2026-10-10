"use client";

import React, { useRef, useState } from "react";
import { Download, FileText, Paperclip, Trash2, Upload } from "lucide-react";
import { Button, IconButton } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/Overlay";
import { ErrorState, Panel, PanelHeader, Skeleton } from "@/components/ui/Primitives";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api-client";
import { useAuth } from "@/lib/auth";
import { formatBytes, timeAgo } from "@/lib/format";
import { useAttachments, useDeleteAttachment, useUploadAttachment } from "@/lib/hooks";
import type { TaskAttachment } from "@/types";

/** Mirrors the server's limits so people get instant feedback; the server remains the authority. */
export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
export const ALLOWED_EXTENSIONS = [
  "pdf", "png", "jpg", "jpeg", "gif", "webp", "txt", "md", "log", "csv", "json",
  "doc", "docx", "xls", "xlsx", "ppt", "pptx", "zip",
];

export function checkFile(file: Pick<File, "name" | "size">): string | null {
  const ext = file.name.includes(".") ? file.name.split(".").pop()!.toLowerCase() : "";
  if (!ALLOWED_EXTENSIONS.includes(ext)) return `"${file.name}" is not an allowed file type.`;
  if (file.size === 0) return `"${file.name}" is empty.`;
  if (file.size > MAX_UPLOAD_BYTES) return `"${file.name}" is larger than ${MAX_UPLOAD_BYTES / 1024 / 1024} MB.`;
  return null;
}

export function Attachments({ taskId, canEdit }: { taskId: string; canEdit: boolean }) {
  const { user, isManager } = useAuth();
  const toast = useToast();
  const { data: files = [], isLoading, error, refetch } = useAttachments(taskId);
  const upload = useUploadAttachment(taskId);
  const remove = useDeleteAttachment(taskId);
  const inputRef = useRef<HTMLInputElement>(null);
  const [toDelete, setToDelete] = useState<TaskAttachment | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);

  const onPick = async (list: FileList | null) => {
    const picked = Array.from(list ?? []);
    if (inputRef.current) inputRef.current.value = "";
    for (const file of picked) {
      const problem = checkFile(file);
      if (problem) {
        toast.error(problem);
        continue;
      }
      await upload.mutateAsync(file).catch(() => undefined); // the hook already toasts the error
    }
  };

  const download = async (file: TaskAttachment) => {
    setDownloading(file.id);
    try {
      const blob = await api.tasks.downloadAttachment(taskId, file.id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = file.filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 10_000);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Download failed.");
    } finally {
      setDownloading(null);
    }
  };

  return (
    <Panel>
      <PanelHeader
        title="Attachments"
        description={`Up to ${MAX_UPLOAD_BYTES / 1024 / 1024} MB each. Documents, images, spreadsheets and zip files.`}
        icon={<Paperclip className="h-4 w-4" />}
        actions={
          canEdit ? (
            <>
              <input
                ref={inputRef}
                type="file"
                multiple
                hidden
                aria-label="Choose files to attach"
                accept={ALLOWED_EXTENSIONS.map((e) => `.${e}`).join(",")}
                onChange={(e) => void onPick(e.target.files)}
              />
              <Button size="sm" loading={upload.isPending} onClick={() => inputRef.current?.click()}>
                <Upload className="h-3.5 w-3.5" aria-hidden /> Attach file
              </Button>
            </>
          ) : undefined
        }
      />
      <div className="p-5">
        {error ? (
          <ErrorState title="Could not load attachments" error={error} onRetry={() => void refetch()} />
        ) : isLoading ? (
          <Skeleton className="h-10 w-full" />
        ) : files.length === 0 ? (
          <p className="text-xs text-fg-muted">No files attached.</p>
        ) : (
          <ul className="divide-y divide-line-subtle">
            {files.map((f) => {
              const canDelete = f.uploader?.id === user?.id || isManager;
              return (
                <li key={f.id} className="flex items-center gap-3 py-2">
                  <FileText className="h-4 w-4 shrink-0 text-fg-faint" aria-hidden />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[13px] text-fg" title={f.filename}>{f.filename}</p>
                    <p className="num text-[11px] text-fg-faint">
                      {formatBytes(f.size_bytes)} · {f.uploader?.display_name ?? "Former member"} · {timeAgo(f.created_at)}
                    </p>
                  </div>
                  <IconButton label={`Download ${f.filename}`} size="sm" disabled={downloading === f.id} onClick={() => void download(f)}>
                    <Download className="h-3.5 w-3.5" />
                  </IconButton>
                  {canDelete && (
                    <IconButton label={`Remove ${f.filename}`} size="sm" tone="danger" onClick={() => setToDelete(f)}>
                      <Trash2 className="h-3.5 w-3.5" />
                    </IconButton>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <ConfirmDialog
        open={toDelete !== null}
        title="Remove this file?"
        description={toDelete ? `"${toDelete.filename}" will be deleted for everyone.` : ""}
        confirmLabel="Remove file"
        note="Removed files cannot be restored."
        loading={remove.isPending}
        onClose={() => setToDelete(null)}
        onConfirm={() => toDelete && remove.mutate(toDelete.id, { onSuccess: () => setToDelete(null) })}
      />
    </Panel>
  );
}
