"use client";

import React, { useState, useRef, useEffect } from "react";
import {
  Bot,
  Send,
  Sparkles,
  Loader2,
  X,
  Minimize2,
  Maximize2,
  RotateCcw,
  ShieldAlert,
} from "lucide-react";
import { api } from "@/lib/api-client";
import { ChatExecutionMetadata, ChatQueryResponse, ReferencedTask } from "@/types";

interface Message {
  id: string;
  sender: "user" | "orbit";
  text: string;
  timestamp: string;
  referencedTasks?: ReferencedTask[];
  suggestedActions?: string[];
  metadata?: ChatExecutionMetadata;
  needsConfirmation?: boolean;
  referencedTaskId?: string | null;
}

interface AskOrbitProps {
  onTaskUpdated?: () => void;
}

export const AskOrbit: React.FC<AskOrbitProps> = ({ onTaskUpdated }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [inputMessage, setInputMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [threadId, setThreadId] = useState<string>(() => "web_" + Math.random().toString(36).substring(2, 9));
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "initial-welcome",
      sender: "orbit",
      text: "Hi! I am ORBIT, your AI Task Orchestrator.\nAsk me to plan your day, find overdue tasks, create tasks, or complete existing work.",
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      suggestedActions: [
        "Plan my day",
        "Show my pending tasks",
        "What are my overdue tasks?",
      ],
    },
  ]);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    if (isOpen && !isMinimized) {
      scrollToBottom();
    }
  }, [messages, isOpen, isMinimized]);

  const handleSendMessage = async (textToSend?: string, isConfirmation: boolean = false) => {
    const text = (textToSend ?? inputMessage).trim();
    if (!text || isLoading) return;

    setInputMessage("");

    const userMessage: Message = {
      id: "user-" + Date.now(),
      sender: "user",
      text,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const response: ChatQueryResponse = await api.chat.query({
        message: text,
        thread_id: threadId,
        confirmed: isConfirmation,
      });

      const assistantMessage: Message = {
        id: response.message_id || "orbit-" + Date.now(),
        sender: "orbit",
        text: response.response,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        referencedTasks: response.referenced_tasks || [],
        suggestedActions: response.suggested_actions || [],
        metadata: response.metadata,
        needsConfirmation: response.needs_confirmation,
        referencedTaskId: response.referenced_task_id,
      };

      setMessages((prev) => [...prev, assistantMessage]);

      // If action modified tasks, trigger parent dashboard refresh
      if (
        response.metadata?.tool_calls_made?.some((t) =>
          ["create_task", "complete_task", "delete_task", "update_task"].includes(t)
        )
      ) {
        onTaskUpdated?.();
      }
    } catch (err: any) {
      const errorText = err?.message || "Failed to reach ORBIT AI. Please check your network.";
      const errorMsg: Message = {
        id: "err-" + Date.now(),
        sender: "orbit",
        text: `Error: ${errorText}`,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleResetThread = () => {
    const newThread = "web_" + Math.random().toString(36).substring(2, 9);
    setThreadId(newThread);
    setMessages([
      {
        id: "welcome-" + Date.now(),
        sender: "orbit",
        text: "Conversation thread reset. How can I help you today?",
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        suggestedActions: [
          "Plan my day",
          "Show my pending tasks",
          "What are my overdue tasks?",
        ],
      },
    ]);
  };

  return (
    <>
      {/* Floating launcher trigger button */}
      {!isOpen && (
        <button
          onClick={() => {
            setIsOpen(true);
            setIsMinimized(false);
          }}
          className="fixed bottom-6 right-6 z-50 flex items-center gap-2 px-3.5 py-2.5 rounded-md bg-slate-900 border border-slate-700/80 hover:border-blue-500/60 text-slate-100 text-xs font-semibold shadow-lg transition-all"
          id="ask-orbit-launcher"
        >
          <Bot className="w-4 h-4 text-blue-400" />
          <span>Ask ORBIT</span>
          <span className="text-[9px] uppercase font-bold px-1.5 py-0.2 rounded bg-blue-950 text-blue-300 border border-blue-800/60">
            AI
          </span>
        </button>
      )}

      {/* Main Ask ORBIT Drawer / Floating Window */}
      {isOpen && (
        <div
          className={`fixed right-6 z-50 transition-all duration-200 shadow-2xl rounded-lg border border-slate-800 bg-slate-950 flex flex-col overflow-hidden ${
            isMinimized
              ? "bottom-6 w-80 h-12"
              : "bottom-6 w-[420px] max-w-[calc(100vw-2rem)] h-[600px] max-h-[calc(100vh-4rem)]"
          }`}
          id="ask-orbit-container"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-3.5 py-2.5 bg-slate-900 border-b border-slate-800">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-md bg-slate-800 border border-slate-700 flex items-center justify-center text-blue-400">
                <Bot className="w-4 h-4" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-xs font-bold text-slate-100 tracking-tight">Ask ORBIT</h3>
                  <span className="text-[9px] font-semibold uppercase px-1.5 py-0.2 rounded bg-emerald-950/70 text-emerald-400 border border-emerald-800/50">
                    Active
                  </span>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-1 text-slate-400">
              <button
                onClick={handleResetThread}
                title="Reset conversation"
                className="p-1 hover:text-white hover:bg-slate-800 rounded-md transition-colors"
              >
                <RotateCcw className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => setIsMinimized(!isMinimized)}
                title={isMinimized ? "Maximize" : "Minimize"}
                className="p-1 hover:text-white hover:bg-slate-800 rounded-md transition-colors"
              >
                {isMinimized ? <Maximize2 className="w-3.5 h-3.5" /> : <Minimize2 className="w-3.5 h-3.5" />}
              </button>
              <button
                onClick={() => setIsOpen(false)}
                title="Close"
                className="p-1 hover:text-rose-400 hover:bg-slate-800 rounded-md transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {!isMinimized && (
            <>
              {/* Message History */}
              <div className="flex-1 overflow-y-auto p-3.5 space-y-3.5 text-xs">
                {messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`flex flex-col ${msg.sender === "user" ? "items-end" : "items-start"}`}
                  >
                    <div
                      className={`max-w-[88%] rounded-md px-3 py-2 leading-relaxed whitespace-pre-wrap ${
                        msg.sender === "user"
                          ? "bg-blue-600 text-white"
                          : "bg-slate-900 border border-slate-800 text-slate-200"
                      }`}
                    >
                      {/* Active Agent Badge */}
                      {msg.sender === "orbit" && msg.metadata?.active_agent && (
                        <div className="flex items-center gap-1 mb-1 text-[10px] text-blue-400 font-semibold border-b border-slate-800/80 pb-1">
                          <Sparkles className="w-3 h-3" />
                          <span>Routed: {msg.metadata.active_agent.replace("_", " ")}</span>
                        </div>
                      )}

                      <p>{msg.text}</p>

                      {/* Confirmation Required Box */}
                      {msg.needsConfirmation && (
                        <div className="mt-2.5 p-2.5 rounded-md bg-amber-950/40 border border-amber-500/30 text-amber-200">
                          <div className="flex items-center gap-1.5 font-semibold text-xs text-amber-400 mb-1.5">
                            <ShieldAlert className="w-4 h-4" />
                            <span>Action Approval Required</span>
                          </div>
                          <p className="text-[11px] text-amber-300/90 mb-2">
                            This operation modifies or deletes task data. Please confirm:
                          </p>
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => handleSendMessage("yes", true)}
                              disabled={isLoading}
                              className="px-3 py-1 rounded-md bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold text-xs transition-colors"
                            >
                              Confirm
                            </button>
                            <button
                              onClick={() => handleSendMessage("cancel", false)}
                              disabled={isLoading}
                              className="px-3 py-1 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs transition-colors"
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      )}

                      {/* Referenced Tasks Cards */}
                      {msg.referencedTasks && msg.referencedTasks.length > 0 && (
                        <div className="mt-2 space-y-1.5 border-t border-slate-800 pt-1.5">
                          <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">
                            Referenced Tasks
                          </span>
                          {msg.referencedTasks.map((t) => (
                            <div
                              key={t.id}
                              className="p-2 rounded-md bg-slate-950 border border-slate-800 flex items-center justify-between gap-2"
                            >
                              <div className="truncate">
                                <span className="font-semibold text-slate-200 block truncate text-[11px]">{t.title}</span>
                                {t.due_date && (
                                  <span className="text-[10px] text-slate-400">Due: {t.due_date}</span>
                                )}
                              </div>
                              {t.priority && (
                                <span className="text-[9px] px-1.5 py-0.5 rounded-md font-bold uppercase bg-slate-800 text-blue-300 border border-blue-500/20">
                                  {t.priority}
                                </span>
                              )}
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Real Agent Execution Trace Inspector */}
                      {msg.sender === "orbit" && msg.metadata && (
                        <div className="mt-2 pt-1.5 border-t border-slate-800/80 text-[10px]">
                          <details className="group">
                            <summary className="cursor-pointer text-slate-400 hover:text-blue-300 flex items-center justify-between font-mono list-none">
                              <span className="flex items-center gap-1">
                                <Sparkles className="w-3 h-3 text-blue-400" />
                                <span>Trace: {msg.metadata.agents_invoked?.join(" → ") || msg.metadata.active_agent || "supervisor"}</span>
                              </span>
                              <span className="text-slate-500 font-sans">
                                {msg.metadata.total_duration_ms ? `${msg.metadata.total_duration_ms}ms` : ""} ▾
                              </span>
                            </summary>
                            <div className="mt-1.5 space-y-1 pl-2 border-l border-blue-500/30 font-mono text-[9px] text-slate-400">
                              {msg.metadata.request_id && (
                                <div><span className="text-slate-500">Request:</span> {msg.metadata.request_id.substring(0, 8)}...</div>
                              )}
                              {msg.metadata.status && (
                                <div><span className="text-slate-500">Status:</span> <span className={msg.metadata.status === "SUCCESS" ? "text-emerald-400" : "text-amber-400"}>{msg.metadata.status}</span></div>
                              )}
                              {msg.metadata.tool_calls_made && msg.metadata.tool_calls_made.length > 0 && (
                                <div><span className="text-slate-500">Tools:</span> {msg.metadata.tool_calls_made.join(", ")}</div>
                              )}
                              {msg.metadata.node_durations_ms && Object.keys(msg.metadata.node_durations_ms).length > 0 && (
                                <div>
                                  <span className="text-slate-500">Timings:</span>{" "}
                                  {Object.entries(msg.metadata.node_durations_ms).map(([node, ms]) => `${node}: ${ms}ms`).join(" | ")}
                                </div>
                              )}
                            </div>
                          </details>
                        </div>
                      )}
                    </div>

                    <span className="text-[9px] text-slate-500 mt-0.5 px-1">{msg.timestamp}</span>

                    {/* Suggested Actions Chips */}
                    {msg.sender === "orbit" && msg.suggestedActions && msg.suggestedActions.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1.5 max-w-[90%]">
                        {msg.suggestedActions.map((action, idx) => (
                          <button
                            key={idx}
                            onClick={() => handleSendMessage(action)}
                            disabled={isLoading}
                            className="px-2.5 py-1 rounded-md bg-slate-900 hover:bg-slate-800 border border-slate-800 hover:border-blue-500/40 text-slate-300 hover:text-blue-200 text-[10px] transition-colors"
                          >
                            {action}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                ))}

                {isLoading && (
                  <div className="flex items-center gap-2 text-blue-400 text-xs py-2 px-3 rounded-md bg-slate-900 border border-slate-800 max-w-[80%]">
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>ORBIT is coordinating tools...</span>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>

              {/* Input Form */}
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleSendMessage();
                }}
                className="p-2.5 bg-slate-900 border-t border-slate-800 flex items-center gap-2"
              >
                <input
                  type="text"
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  placeholder="Ask ORBIT (e.g., 'Plan my day', 'Show overdue tasks')..."
                  disabled={isLoading}
                  className="flex-1 bg-slate-950 border border-slate-800 rounded-md px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
                />
                <button
                  type="submit"
                  disabled={isLoading || !inputMessage.trim()}
                  className="p-2 rounded-md bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white transition-colors"
                >
                  <Send className="w-3.5 h-3.5" />
                </button>
              </form>
            </>
          )}
        </div>
      )}
    </>
  );
};
