"use client";

import { useEffect, useRef, useState } from "react";
import { Bot, Send, User, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import { useIdeStore } from "@/store/ide";
import type { Message, Project } from "@/lib/types";
import { cn } from "@/lib/utils";

const AGENT_EMOJI: Record<string, string> = {
  planner: "🧠",
  product_manager: "📋",
  architect: "🏗️",
  coder: "💻",
  tester: "🧪",
  debugger: "🐛",
  reviewer: "🔍",
  documentation: "📝",
  orchestrator: "🤖",
};

function SuggestionButton({ text, onClick }: { text: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="rounded-full border border-border px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:border-primary hover:text-foreground"
    >
      {text}
    </button>
  );
}

export function ChatPanel({
  input,
  setInput,
  onSend,
  project,
}: {
  input: string;
  setInput: (v: string) => void;
  onSend: () => void;
  project: Project;
}) {
  const store = useIdeStore();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [selectedConv, setSelectedConv] = useState<number | null>(null);
  const [loadingConv, setLoadingConv] = useState(false);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [store.chat.messages, store.chat.statusLine]);

  useEffect(() => {
    if (selectedConv !== null) {
      setLoadingConv(true);
      api
        .get<Message[]>(`/api/projects/${project.id}/conversations/${selectedConv}/messages`)
        .then((m) => store.setMessages(m))
        .finally(() => setLoadingConv(false));
    }
  }, [selectedConv, project.id, store]);

  const newConversation = () => {
    setSelectedConv(null);
    setConversationId(null);
    store.setActiveConversation(null);
    store.setMessages([]);
  };

  const send = () => {
    onSend();
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border px-3 py-2">
        <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          AI Assistant
        </div>
        <div className="flex items-center gap-1">
          <select
            value={selectedConv === null ? "" : String(selectedConv)}
            onChange={(e) => {
              if (e.target.value === "") newConversation();
              else setSelectedConv(Number(e.target.value));
            }}
            className="max-w-[130px] rounded border border-border bg-transparent px-1.5 py-1 text-[11px] outline-none"
          >
            <option value="">New chat</option>
            {store.conversations.map((c) => (
              <option key={c.id} value={c.id}>
                {c.title.slice(0, 26)}
              </option>
            ))}
          </select>
          <button
            onClick={newConversation}
            className="rounded p-1 text-muted-foreground hover:bg-secondary hover:text-foreground"
            title="New conversation"
          >
            <RefreshCw className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto p-3">
        {store.chat.messages.length === 0 && !loadingConv && (
          <div className="flex flex-col gap-2 text-xs">
            <div className="mb-1 text-muted-foreground">
              Describe what you want. Example:{" "}
              <span className="text-foreground">"Create a FastAPI backend for a pharmacy inventory system"</span>
            </div>
            <SuggestionButton
              text="📋 Plan: Create a FastAPI pharmacy inventory backend"
              onClick={() => {
                setInput("Plan a FastAPI backend for a pharmacy inventory system with products, stock levels and low-stock alerts");
              }}
            />
            <SuggestionButton
              text="💻 Add barcode scanning"
              onClick={() => setInput("Add barcode scanning support to the project")}
            />
            <SuggestionButton
              text="🧪 Run tests"
              onClick={() => setInput("Run the project tests and report results")}
            />
            <SuggestionButton
              text="🐛 Debug the last error"
              onClick={() => setInput("Debug the last error that occurred in this project")}
            />
          </div>
        )}
        {store.chat.messages.map((m) => (
          <div
            key={m.id}
            className={cn("mb-3 flex gap-2", m.role === "user" ? "justify-end" : "justify-start")}
          >
            {m.role !== "user" && (
              <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-primary/15">
                <span className="text-xs">{AGENT_EMOJI[m.agent_type] || "🤖"}</span>
              </div>
            )}
            <div
              className={cn(
                "max-w-[85%] whitespace-pre-wrap rounded-lg px-3 py-2 text-[13px] leading-relaxed",
                m.role === "user"
                  ? "rounded-br-sm bg-primary text-primary-foreground"
                  : "rounded-bl-sm bg-secondary text-secondary-foreground"
              )}
            >
              {m.content}
            </div>
            {m.role === "user" && (
              <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-secondary">
                <User className="h-3.5 w-3.5 text-muted-foreground" />
              </div>
            )}
          </div>
        ))}
        {store.chat.streaming && (
          <div className="mb-3 flex items-center gap-2 text-[13px] text-muted-foreground">
            <span className="h-3 w-3 spinner rounded-full border-2 border-primary border-t-transparent" />
            {store.chat.statusEmoji} {store.chat.statusLine || "Working..."}
          </div>
        )}
        {store.chat.statusEmoji === "" && store.chat.statusLine && !store.chat.streaming && (
          <div className="mb-3 text-[13px] text-muted-foreground">
            {store.chat.statusEmoji} {store.chat.statusLine}
          </div>
        )}
      </div>

      <div className="border-t border-border p-3">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          placeholder={`Ask Arynox about "${project.name}"...`}
          rows={3}
          className="w-full resize-none rounded-md border border-border bg-transparent px-3 py-2 text-[13px] outline-none placeholder:text-muted-foreground focus:border-primary"
        />
        <div className="mt-2 flex justify-end">
          <button
            onClick={send}
            disabled={!input.trim() || store.chat.streaming}
            className="flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-40"
          >
            <Send className="h-3.5 w-3.5" /> Send
          </button>
        </div>
      </div>
    </div>
  );
}
