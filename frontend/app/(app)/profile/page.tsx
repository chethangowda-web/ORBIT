"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, CheckCircle2, Palette, UserCircle } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input, Select } from "@/components/ui/Field";
import { Avatar, ErrorState, PageHeader, Panel, PanelHeader, Skeleton } from "@/components/ui/Primitives";
import { ThemeSwitcher } from "@/components/ui/ThemeSwitcher";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api-client";
import { useAuth } from "@/lib/auth";
import { ROLE_LABEL } from "@/lib/constants";
import { keys } from "@/lib/hooks";
import { timezoneOptions } from "@/lib/timezones";
import type { UserRole } from "@/types";

const PREFERENCES = [
  { key: "daily_briefing", label: "Morning briefing", description: "A prioritised plan for your day, sent at 9:00.", managerOnly: false },
  { key: "overdue_alert", label: "Overdue alerts", description: "An evening reminder when assigned tasks are past due.", managerOnly: false },
  { key: "email_notifications", label: "Email notifications", description: "Email copies of assignments, updates and comments. Only sent when the server has email set up.", managerOnly: false },
  { key: "due_soon_reminder", label: "Due-tomorrow reminders", description: "A heads-up at 4:00 pm about tasks that are due the next day.", managerOnly: false },
  { key: "stale_nudge", label: "Check-ins on quiet tasks", description: "A nudge on weekdays when a task you are working on has not changed for 3 days.", managerOnly: false },
  { key: "manager_escalation", label: "Late work summary", description: "A weekday evening summary of tasks that are 3 or more days late.", managerOnly: true },
  { key: "weekly_summary", label: "Weekly team summary", description: "Team throughput digest on Monday mornings.", managerOnly: true },
] as const;

const isOn = (value: string | undefined) => !["false", "0", "off", "no"].includes((value ?? "true").toLowerCase());

function Switch({ checked, onChange, label, description, disabled }: { checked: boolean; onChange: (next: boolean) => void; label: string; description: string; disabled?: boolean }) {
  return (
    <label className="flex cursor-pointer items-start justify-between gap-4 py-3">
      <span>
        <span className="block text-[13px] font-medium text-fg">{label}</span>
        <span className="mt-0.5 block text-xs text-fg-muted">{description}</span>
      </span>
      <input type="checkbox" role="switch" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} className="peer sr-only" />
      <span aria-hidden className="relative mt-0.5 h-5 w-9 shrink-0 rounded-full border border-line bg-surface-3 transition-colors after:absolute after:left-0.5 after:top-0.5 after:h-3.5 after:w-3.5 after:rounded-full after:bg-fg-muted after:transition-transform peer-checked:border-accent-strong peer-checked:bg-accent-strong peer-checked:after:translate-x-4 peer-checked:after:bg-white peer-focus-visible:outline peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-accent peer-disabled:opacity-50" />
    </label>
  );
}

export default function ProfilePage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const { isManager, refreshProfile } = useAuth();

  const profile = useQuery({ queryKey: ["profile"], queryFn: api.auth.me });
  const prefs = useQuery({ queryKey: keys.preferences, queryFn: api.users.preferences });

  const [name, setName] = useState("");
  const [zone, setZone] = useState("");
  const zones = useMemo(() => timezoneOptions(profile.data?.timezone), [profile.data?.timezone]);
  useEffect(() => {
    if (profile.data) {
      setName(profile.data.display_name);
      setZone(profile.data.timezone);
    }
  }, [profile.data]);

  const save = useMutation({
    mutationFn: () => api.users.updateMe({ display_name: name.trim(), timezone: zone }),
    onSuccess: async () => {
      toast.success("Profile saved");
      await queryClient.invalidateQueries({ queryKey: ["profile"] });
      await refreshProfile();
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Could not save your profile."),
  });

  // The switch flips immediately from local state, then the server value takes over.
  const [pending, setPending] = useState<Record<string, boolean>>({});
  const setPref = useMutation({
    mutationFn: ({ key, on }: { key: string; on: boolean }) => api.users.updatePreferences({ [key]: on ? "true" : "false" }),
    onError: (e) => toast.error(e instanceof Error ? e.message : "Could not save that preference."),
    onSettled: async (_data, _error, { key }) => {
      await queryClient.invalidateQueries({ queryKey: keys.preferences });
      setPending((p) => {
        const next = { ...p };
        delete next[key];
        return next;
      });
    },
  });
  const toggle = (key: string, on: boolean) => {
    setPending((p) => ({ ...p, [key]: on }));
    setPref.mutate({ key, on });
  };

  if (profile.error) return <ErrorState title="Could not load your profile" error={profile.error} onRetry={() => void profile.refetch()} />;
  const me = profile.data;
  const dirty = me ? name.trim() !== me.display_name || zone !== me.timezone : false;

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <PageHeader title="Profile" description="Your account and how ORBIT contacts you." />

      <Panel>
        <PanelHeader title="Account" icon={<UserCircle className="h-4 w-4" />} />
        {!me ? (
          <Skeleton className="m-4 h-40" />
        ) : (
          <form
            className="space-y-4 p-4"
            onSubmit={(e) => {
              e.preventDefault();
              if (name.trim()) save.mutate();
            }}
          >
            <div className="flex items-center gap-3">
              <Avatar name={me.display_name} size="lg" />
              <div>
                <p className="text-[13px] font-medium text-fg">{me.email}</p>
                <Badge tone="accent" className="mt-1">{ROLE_LABEL[me.role as UserRole]}</Badge>
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <Input label="Display name" required value={name} maxLength={255} onChange={(e) => setName(e.target.value)} error={name.trim() ? null : "A name is required."} />
              <Select label="Timezone" value={zone} onChange={(e) => setZone(e.target.value)} options={zones.map((z) => ({ value: z, label: z }))} hint="Used for due dates and message timing." />
            </div>
            <div className="flex items-center gap-2 rounded-control border border-line bg-surface-2 px-3 py-2 text-xs text-fg-muted">
              <CheckCircle2 className={me.google_id ? "h-4 w-4 text-ok" : "h-4 w-4 text-fg-faint"} aria-hidden />
              {me.google_id ? "Linked to Google Chat. ORBIT can message you directly." : "Not linked to Google Chat yet. Send ORBIT a direct message in Google Chat to link your account."}
            </div>
            <div className="flex justify-end">
              <Button type="submit" variant="primary" loading={save.isPending} disabled={!dirty || !name.trim()}>
                Save changes
              </Button>
            </div>
          </form>
        )}
      </Panel>

      <Panel>
        <PanelHeader title="Appearance" description="Applies to this browser." icon={<Palette className="h-4 w-4" />} />
        <div className="p-4">
          <ThemeSwitcher />
        </div>
      </Panel>

      <Panel>
        <PanelHeader title="Notifications" description="Choose what ORBIT sends you in Google Chat and by email." icon={<Bell className="h-4 w-4" />} />
        <div className="divide-y divide-line-subtle px-4">
          {prefs.isLoading ? (
            <Skeleton className="my-4 h-24" />
          ) : (
            PREFERENCES.filter((p) => !p.managerOnly || isManager).map((p) => (
              <Switch key={p.key} label={p.label} description={p.description} checked={pending[p.key] ?? isOn(prefs.data?.[p.key])} onChange={(on) => toggle(p.key, on)} />
            ))
          )}
        </div>
      </Panel>
    </div>
  );
}
