"use client";

import React, { Suspense, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, CalendarClock, Mail, Play, Users } from "lucide-react";
import { Badge, type Tone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { CompactSelect } from "@/components/ui/Field";
import { ConfirmDialog } from "@/components/ui/Overlay";
import { Pagination } from "@/components/ui/Pagination";
import { Avatar, EmptyState, ErrorState, PageHeader, Panel, PanelHeader, Skeleton } from "@/components/ui/Primitives";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api-client";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { NOTIFICATION_TYPE_LABEL, ROLE_LABEL } from "@/lib/constants";
import { formatDateTime, timeAgo } from "@/lib/format";
import { keys, useNotifications, useScheduler } from "@/lib/hooks";
import type { UserRole } from "@/types";

type TabId = "scheduler" | "notifications" | "users";

const JOBS = [
  { id: "briefing", label: "Morning briefing", confirm: "Send today's briefing to every active user who has not opted out?" },
  { id: "overdue", label: "Overdue alerts", confirm: "Send overdue-task alerts to every assignee with late work?" },
  { id: "weekly", label: "Weekly summary", confirm: "Send the weekly summary to all managers and admins?" },
] as const;

function SchedulerTab() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const { data, isLoading, error, refetch } = useScheduler(true);
  const [pending, setPending] = useState<(typeof JOBS)[number] | null>(null);

  const trigger = useMutation({
    mutationFn: (job: "briefing" | "overdue" | "weekly") => api.admin.trigger(job),
    onSuccess: (result) => {
      const summary = ["sent", "skipped", "failed"].filter((k) => k in result).map((k) => `${result[k]} ${k}`).join(", ");
      toast.success(`Job finished: ${summary || "done"}`);
      void queryClient.invalidateQueries({ queryKey: keys.notifications });
      setPending(null);
    },
    onError: (e) => {
      toast.error(e instanceof Error ? e.message : "The job failed.");
      setPending(null);
    },
  });

  if (error) return <ErrorState title="Could not load the scheduler" error={error} onRetry={() => void refetch()} />;

  return (
    <div className="space-y-4">
      <Panel>
        <PanelHeader
          title="Scheduled jobs"
          description="Cron jobs run in the product timezone and skip anyone who opted out."
          icon={<CalendarClock className="h-4 w-4" />}
          actions={data && <Badge tone={data.running ? "ok" : "warn"}>{data.running ? "Running" : "Stopped"}</Badge>}
        />
        {isLoading ? (
          <Skeleton className="m-4 h-20" />
        ) : !data || data.jobs.length === 0 ? (
          <p className="p-4 text-xs text-fg-muted">No jobs are registered. Is the scheduler enabled for this environment?</p>
        ) : (
          <ul className="divide-y divide-line-subtle">
            {data.jobs.map((job) => (
              <li key={job.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
                <div>
                  <p className="text-[13px] font-medium text-fg">{job.name}</p>
                  <p className="num text-[11px] text-fg-faint">{job.trigger}</p>
                </div>
                <p className="text-xs text-fg-muted">
                  Next run <span className="num text-fg">{job.next_run_time ? formatDateTime(job.next_run_time) : "pending"}</span>
                  <span className="ml-1 text-fg-faint">({data.timezone})</span>
                </p>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <Panel>
        <PanelHeader title="Run now" description="Sends real messages. Duplicate protection is bypassed; opt-outs are still honoured." icon={<Play className="h-4 w-4" />} />
        <div className="flex flex-wrap gap-2 p-4">
          {JOBS.map((job) => (
            <Button key={job.id} onClick={() => setPending(job)} disabled={trigger.isPending}>
              {job.label}
            </Button>
          ))}
        </div>
      </Panel>

      <ConfirmDialog
        open={pending !== null}
        title={pending ? `Run: ${pending.label}` : ""}
        description={pending?.confirm ?? ""}
        confirmLabel="Run now"
        tone="primary"
        note="Delivery results appear in the Notifications tab."
        loading={trigger.isPending}
        onClose={() => setPending(null)}
        onConfirm={() => pending && trigger.mutate(pending.id)}
      />
    </div>
  );
}

const DELIVERY_TONE: Record<string, Tone> = { sent: "ok", failed: "danger", skipped: "muted" };

function NotificationsTab() {
  const [status, setStatus] = useState("");
  const [type, setType] = useState("");
  const [page, setPage] = useState(1);
  const { data, isLoading, error, refetch } = useNotifications({ status: status || undefined, type: type || undefined, page }, true);

  return (
    <Panel>
      <PanelHeader
        title="Delivery log"
        description="Every proactive and task-event message, with its real outcome."
        icon={<Mail className="h-4 w-4" />}
        actions={
          <>
            <CompactSelect label="Delivery status" value={status} onChange={(v) => { setStatus(v); setPage(1); }} options={[{ value: "", label: "Any status" }, { value: "sent", label: "Sent" }, { value: "failed", label: "Failed" }, { value: "skipped", label: "Skipped" }]} />
            <CompactSelect label="Notification type" value={type} onChange={(v) => { setType(v); setPage(1); }} options={[{ value: "", label: "Any type" }, ...Object.entries(NOTIFICATION_TYPE_LABEL).map(([value, label]) => ({ value, label }))]} />
          </>
        }
      />
      {error ? (
        <div className="p-4"><ErrorState title="Could not load the delivery log" error={error} onRetry={() => void refetch()} /></div>
      ) : isLoading ? (
        <Skeleton className="m-4 h-40" />
      ) : !data || data.items.length === 0 ? (
        <div className="p-4"><EmptyState title="Nothing logged" description="Messages appear here once a job runs or a task is assigned." /></div>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[680px] text-left text-[12.5px]">
              <thead className="text-[11px] font-semibold uppercase tracking-[0.05em] text-fg-faint">
                <tr>
                  <th scope="col" className="px-4 py-2">When</th>
                  <th scope="col" className="px-3 py-2">Recipient</th>
                  <th scope="col" className="px-3 py-2">Type</th>
                  <th scope="col" className="px-3 py-2">Outcome</th>
                  <th scope="col" className="px-3 py-2">Detail</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line-subtle">
                {data.items.map((n) => (
                  <tr key={n.id} className="hover:bg-surface-2/60">
                    <td className="whitespace-nowrap px-4 py-2.5 text-fg-muted" title={formatDateTime(n.sent_at)}>{timeAgo(n.sent_at)}</td>
                    <td className="px-3 py-2.5 text-fg">{n.user_name}</td>
                    <td className="px-3 py-2.5 text-fg-muted">{NOTIFICATION_TYPE_LABEL[n.type] ?? n.type}</td>
                    <td className="px-3 py-2.5"><Badge tone={DELIVERY_TONE[n.status] ?? "muted"}>{n.status}</Badge></td>
                    <td className="max-w-[320px] truncate px-3 py-2.5 text-fg-muted" title={n.error_msg ?? n.message}>
                      {n.error_msg ? <span className="inline-flex items-center gap-1 text-danger"><AlertCircle className="h-3 w-3" aria-hidden />{n.error_msg}</span> : n.message.split("\n")[0]}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="px-4 pb-3"><Pagination meta={data.meta} noun="messages" onPageChange={setPage} /></div>
        </>
      )}
    </Panel>
  );
}

function UsersTab() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const { user: me } = useAuth();
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: [...keys.users, "admin"],
    queryFn: () => api.users.list({ page_size: 100 }),
    placeholderData: keepPreviousData,
  });
  const [deactivate, setDeactivate] = useState<{ id: string; name: string } | null>(null);

  const change = useMutation({
    mutationFn: ({ id, body }: { id: string; body: { role?: UserRole; is_active?: boolean } }) => api.users.adminUpdate(id, body),
    onSuccess: () => {
      toast.success("User updated");
      setDeactivate(null);
      void queryClient.invalidateQueries({ queryKey: keys.users });
    },
    onError: (e) => {
      toast.error(e instanceof Error ? e.message : "Could not update the user.");
      setDeactivate(null);
    },
  });

  if (error) return <ErrorState title="Could not load users" error={error} onRetry={() => void refetch()} />;

  return (
    <Panel>
      <PanelHeader title="Users and roles" description="Roles control what people can see and change in the dashboard and in chat." icon={<Users className="h-4 w-4" />} />
      {isLoading ? (
        <Skeleton className="m-4 h-40" />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[620px] text-left text-[12.5px]">
            <thead className="text-[11px] font-semibold uppercase tracking-[0.05em] text-fg-faint">
              <tr>
                <th scope="col" className="px-4 py-2">Person</th>
                <th scope="col" className="px-3 py-2">Role</th>
                <th scope="col" className="px-3 py-2">Status</th>
                <th scope="col" className="px-4 py-2 text-right"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line-subtle">
              {(data?.items ?? []).map((u) => {
                const isMe = u.id === me?.id;
                return (
                  <tr key={u.id} className={cn("hover:bg-surface-2/60", !u.is_active && "opacity-60")}>
                    <td className="px-4 py-2.5">
                      <span className="flex items-center gap-2.5">
                        <Avatar name={u.display_name} />
                        <span>
                          <span className="block text-fg">{u.display_name}{isMe && <span className="ml-1.5 text-[11px] text-fg-faint">(you)</span>}</span>
                          <span className="block text-[11px] text-fg-faint">{u.email}</span>
                        </span>
                      </span>
                    </td>
                    <td className="px-3 py-2.5">
                      <CompactSelect
                        label={`Role for ${u.display_name}`}
                        value={u.role}
                        onChange={(role) => change.mutate({ id: u.id, body: { role: role as UserRole } })}
                        options={(Object.keys(ROLE_LABEL) as UserRole[]).map((r) => ({ value: r, label: ROLE_LABEL[r] }))}
                        className={isMe ? "pointer-events-none opacity-50" : undefined}
                      />
                    </td>
                    <td className="px-3 py-2.5"><Badge tone={u.is_active ? "ok" : "faint"}>{u.is_active ? "Active" : "Deactivated"}</Badge></td>
                    <td className="px-4 py-2.5 text-right">
                      {u.is_active ? (
                        <Button size="sm" variant="danger" disabled={isMe} onClick={() => setDeactivate({ id: u.id, name: u.display_name })}>Deactivate</Button>
                      ) : (
                        <Button size="sm" onClick={() => change.mutate({ id: u.id, body: { is_active: true } })}>Reactivate</Button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <ConfirmDialog
        open={deactivate !== null}
        title={deactivate ? `Deactivate ${deactivate.name}?` : ""}
        description="They will be signed out and unable to log in. Their tasks stay in place."
        confirmLabel="Deactivate"
        note="You can reactivate the account at any time."
        loading={change.isPending}
        onClose={() => setDeactivate(null)}
        onConfirm={() => deactivate && change.mutate({ id: deactivate.id, body: { is_active: false } })}
      />
    </Panel>
  );
}

function AdminScreen() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const { isAdmin } = useAuth();

  const tabs: { id: TabId; label: string }[] = [
    { id: "scheduler", label: "Scheduler" },
    { id: "notifications", label: "Notifications" },
    ...(isAdmin ? [{ id: "users" as const, label: "Users" }] : []),
  ];
  const requested = params.get("tab") as TabId | null;
  const active = tabs.find((t) => t.id === requested)?.id ?? "scheduler";

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader title="Admin" description="Scheduler, delivery log and access control." />
      <div role="tablist" aria-label="Admin sections" className="mb-4 flex gap-1 border-b border-line">
        {tabs.map((t) => (
          <button
            key={t.id}
            role="tab"
            type="button"
            aria-selected={active === t.id}
            onClick={() => router.replace(`${pathname}?tab=${t.id}`, { scroll: false })}
            className={cn("-mb-px border-b-2 px-3 py-2 text-[13px] font-medium transition-colors", active === t.id ? "border-accent text-fg" : "border-transparent text-fg-muted hover:text-fg")}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div role="tabpanel">
        {active === "scheduler" && <SchedulerTab />}
        {active === "notifications" && <NotificationsTab />}
        {active === "users" && isAdmin && <UsersTab />}
      </div>
    </div>
  );
}

export default function AdminPage() {
  return (
    <Suspense fallback={null}>
      <AdminScreen />
    </Suspense>
  );
}
