"use client";

/**
 * Shared state for the agent rail: open/closed, the chat transcript, and `ask()` so
 * other parts of the UI (the command palette, empty states) can talk to the agent.
 */

import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { api } from "./api-client";
import { useInvalidateTaskData, keys } from "./hooks";
import { useQueryClient } from "@tanstack/react-query";
import type { ChatExecutionMetadata, ReferencedTask } from "@/types";

export interface ChatMessage {
  id: string;
  sender: "user" | "orbit";
  text: string;
  at: string;
  referencedTasks?: ReferencedTask[];
  suggestedActions?: string[];
  metadata?: ChatExecutionMetadata;
  needsConfirmation?: boolean;
  /** True once the confirmation card has been answered, so its buttons disable. */
  resolved?: boolean;
  isError?: boolean;
}

interface AgentContextValue {
  open: boolean;
  setOpen: (open: boolean) => void;
  messages: ChatMessage[];
  sending: boolean;
  ask: (text: string, options?: { confirmed?: boolean }) => Promise<void>;
  reset: () => void;
}

const AgentContext = createContext<AgentContextValue | undefined>(undefined);

const OPEN_KEY = "orbit_agent_open";
const THREAD_KEY = "orbit_agent_thread";
const MUTATING_TOOLS = ["create_task", "complete_task", "delete_task", "update_task"];

const now = () => new Date().toISOString();
const newId = () => `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

const WELCOME: ChatMessage = {
  id: "welcome",
  sender: "orbit",
  at: now(),
  text: "I can plan your day, find overdue work, and create, update or complete tasks. Try one of these.",
  suggestedActions: ["Plan my day", "Show my pending tasks", "What are my overdue tasks?"],
};

function newThreadId(): string {
  return `web_${Math.random().toString(36).slice(2, 10)}`;
}

export function AgentProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const invalidateTasks = useInvalidateTaskData();
  const [open, setOpenState] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME]);
  const [sending, setSending] = useState(false);
  const threadRef = useRef<string>("");
  const sendingRef = useRef(false);

  // Restore the rail state and a stable thread id for this browser session.
  useEffect(() => {
    threadRef.current = window.sessionStorage.getItem(THREAD_KEY) || newThreadId();
    window.sessionStorage.setItem(THREAD_KEY, threadRef.current);
    const stored = window.localStorage.getItem(OPEN_KEY);
    // Google Chat is the main place to talk to ORBIT, so this panel stays closed until opened.
    setOpenState(stored === "1");
  }, []);

  const setOpen = useCallback((value: boolean) => {
    setOpenState(value);
    window.localStorage.setItem(OPEN_KEY, value ? "1" : "0");
  }, []);

  const ask = useCallback<AgentContextValue["ask"]>(
    async (text, options = {}) => {
      const message = text.trim();
      if (!message || sendingRef.current) return;
      sendingRef.current = true;
      setSending(true);
      setOpen(true);

      setMessages((all) => [
        ...all.map((m) => (m.needsConfirmation && !m.resolved ? { ...m, resolved: true } : m)),
        { id: newId(), sender: "user", text: message, at: now() },
      ]);

      try {
        const reply = await api.chat.query({
          message,
          thread_id: threadRef.current,
          confirmed: options.confirmed ?? false,
        });
        setMessages((all) => [
          ...all,
          {
            id: reply.message_id || newId(),
            sender: "orbit",
            text: reply.response,
            at: now(),
            referencedTasks: reply.referenced_tasks,
            suggestedActions: reply.suggested_actions,
            metadata: reply.metadata,
            needsConfirmation: reply.needs_confirmation,
          },
        ]);
        if (reply.metadata?.tool_calls_made?.some((t) => MUTATING_TOOLS.includes(t))) invalidateTasks();
        queryClient.invalidateQueries({ queryKey: keys.traces });
      } catch (error) {
        setMessages((all) => [
          ...all,
          {
            id: newId(),
            sender: "orbit",
            at: now(),
            isError: true,
            text: error instanceof Error ? error.message : "I could not reach the server.",
          },
        ]);
      } finally {
        sendingRef.current = false;
        setSending(false);
      }
    },
    [invalidateTasks, queryClient, setOpen],
  );

  const reset = useCallback(() => {
    threadRef.current = newThreadId();
    window.sessionStorage.setItem(THREAD_KEY, threadRef.current);
    setMessages([{ ...WELCOME, id: `welcome-${newId()}`, at: now(), text: "Conversation reset. What do you need?" }]);
  }, []);

  const value = useMemo(
    () => ({ open, setOpen, messages, sending, ask, reset }),
    [open, setOpen, messages, sending, ask, reset],
  );
  return <AgentContext.Provider value={value}>{children}</AgentContext.Provider>;
}

export function useAgent(): AgentContextValue {
  const ctx = useContext(AgentContext);
  if (!ctx) throw new Error("useAgent must be used within AgentProvider");
  return ctx;
}
