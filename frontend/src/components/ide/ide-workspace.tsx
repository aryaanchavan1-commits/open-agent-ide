"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Bot, Settings, ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";
import { useProjectSSE, type SSEEvent } from "@/lib/sse";
import { useIdeStore } from "@/store/ide";
import type { AgentInfo, Conversation, Message, Project, ProposedChange, Task } from "@/lib/types";
import { FileExplorer } from "./file-explorer";
import { EditorPanel } from "./editor";
import { ChatPanel } from "./chat-panel";
import { TerminalPanel } from "./terminal-panel";
import { ApprovalDialogs } from "./approval-dialogs";
import { TasksPanel } from "./tasks-panel";
import { GitPanel } from "./git-panel";
import { AgentsPanel } from "./agents-panel";
import { Badge } from "@/components/ui/badge";

const PERMISSION_LABEL: Record<string, string> = {
  safe: "Safe",
  ask: "Ask",
  auto: "Auto",
};

export function IdeWorkspace({ project }: { project: Project }) {
  const store = useIdeStore();
  const [input, setInput] = useState("");
  const [model, setModel] = useState(project.default_model);
  const lastFileChange = useRef(0);

  const refreshTree = useCallback(async () => {
    try {
      store.setFileTree(await api.get("/api/projects/" + project.id + "/files/tree"));
    } catch {
      /* ignore */
    }
  }, [project.id, store]);

  const refreshGit = useCallback(async () => {
    try {
      store.setGitStatus(await api.get("/api/projects/" + project.id + "/git/status"));
      store.setCheckpoints(await api.get("/api/projects/" + project.id + "/git/checkpoints"));
    } catch {
      /* ignore */
    }
  }, [project.id, store]);

  const refreshAll = useCallback(() => {
    api.get<Conversation[]>("/api/projects/" + project.id + "/conversations").then((c) => {
      store.setConversations(c);
      if (c.length && store.activeConversation === null) {
        const convId = c[0].id;
        store.setActiveConversation(convId);
        api.get<Message[]>(`/api/projects/${project.id}/conversations/${convId}/messages`).then((m) => {
          store.setMessages(m);
        });
      }
    });
    refreshTree();
    refreshGit();
  }, [project.id, store, refreshTree, refreshGit]);

  useEffect(() => {
    store.setProject(project.id);
    store.setPermissionMode(project.permission_mode);
    api.get<AgentInfo[]>("/api/projects/" + project.id + "/agents").then((a) => store.setAgents(a));
    api.get<Task[]>("/api/projects/" + project.id + "/tasks").then((t) => store.setTasks(t));
    api.get<{ model: string }>("/api/models/project/" + project.id).then((m) => setModel(m.model));
    refreshAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.id]);

  const onEvent = useCallback(
    (ev: SSEEvent) => {
      const d = ev.data;
      switch (ev.type) {
        case "agent.status":
          store.setStatus(String(d.message || ""), String(d.emoji || "🤖"));
          break;
        case "chat.message": {
          store.setStreaming(false);
          store.setStatus("");
          const m: Message = {
            id: Number(d.message_id || 0),
            conversation_id: Number(d.conversation_id || 0),
            role: "assistant",
            content: String(d.content || ""),
            agent_type: String(d.agent_type || ""),
            meta: {},
            created_at: new Date().toISOString(),
          };
          store.appendMessage(m);
          refreshTree();
          refreshGit();
          break;
        }
        case "conversation.started":
          refreshAll();
          break;
        case "run.failed":
          store.setStreaming(false);
          store.setStatus("❌ Agent failed: " + String(d.error || ""));
          break;
        case "run.finished":
          store.setStreaming(false);
          store.setStatus("✅ Done");
          break;
        case "command.output":
          store.addTerminalLines([String(d.line || "")]);
          break;
        case "command.start":
          store.addTerminalLines([`$ ${String(d.command || "")}`]);
          break;
        case "command.finish":
          store.addTerminalLines([
            `[exit code: ${String(d.exit_code ?? "?")}${d.killed ? " (timeout)" : ""}]`,
          ]);
          break;
        case "permission.request":
          store.addApproval({
            approval_id: Number(d.approval_id),
            command: String(d.command || ""),
            cwd: String(d.cwd || ""),
            agent: String(d.agent || ""),
            reason: String(d.reason || ""),
          });
          break;
        case "permission.response":
          store.removeApproval(Number(d.approval_id));
          break;
        case "changes.proposed":
          store.setProposedChanges({
            plan_id: Number(d.plan_id),
            summary: String(d.summary || ""),
            files: Array.isArray(d.files) ? (d.files as ProposedChange["files"]) : [],
            commands: Array.isArray(d.commands) ? (d.commands as ProposedChange["commands"]) : [],
          });
          break;
        case "changes.applied":
        case "changes.response":
        case "changes.rejected":
          store.setProposedChanges(null);
          refreshTree();
          refreshGit();
          break;
        case "file.changed":
          lastFileChange.current = Date.now();
          refreshTree();
          break;
        case "test.result":
          store.addTestResult({
            test_run_id: Number(d.test_run_id),
            command: String(d.command || ""),
            status: String(d.status || ""),
            passed: Number(d.passed || 0),
            failed: Number(d.failed || 0),
            exit_code: d.exit_code !== null && d.exit_code !== undefined ? Number(d.exit_code) : null,
          });
          break;
        case "plan.created":
          api.get<Task[]>("/api/projects/" + project.id + "/tasks").then((t) => store.setTasks(t));
          break;
        case "model.pull":
          store.addTerminalLines([
            `[model] ${String(d.model || "")}: ${String(d.status || "")}`,
          ]);
          break;
        default:
          break;
      }
    },
    [store, refreshTree, refreshGit, refreshAll]
  );

  useProjectSSE(project.id, onEvent);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || store.chat.streaming) return;
    setInput("");
    store.appendMessage({
      id: -Date.now(),
      conversation_id: store.activeConversation || 0,
      role: "user",
      content: text,
      agent_type: "user",
      meta: {},
      created_at: new Date().toISOString(),
    });
    store.setStreaming(true);
    try {
      await api.post("/api/projects/" + project.id + "/chat", {
        message: text,
        conversation_id: store.activeConversation,
      });
    } catch (e) {
      store.setStreaming(false);
      store.setStatus("❌ " + (e as Error).message);
    }
  };

  const runCommand = async (command: string) => {
    store.addTerminalLines([`> ${command}`]);
    try {
      await api.post("/api/projects/" + project.id + "/execute", {
        command,
        reason: "Manual command from terminal",
      });
    } catch (e) {
      store.addTerminalLines([`[error] ${(e as Error).message}`]);
    }
  };

  return (
    <div className="flex h-full flex-col bg-background">
      <header className="flex h-12 items-center justify-between border-b border-border px-3">
        <div className="flex items-center gap-3">
          <Link href="/" className="text-muted-foreground hover:text-foreground">
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary/20">
            <Bot className="h-4 w-4 text-primary" />
          </div>
          <span className="text-sm font-semibold">{project.name}</span>
          <span className="text-xs text-muted-foreground">/ {project.slug}</span>
        </div>
        <div className="flex items-center gap-3">
          <Badge variant="outline">
            <ShieldCheck className="mr-1 h-3 w-3" />
            {PERMISSION_LABEL[store.permissionMode] || store.permissionMode}
          </Badge>
          <Badge variant="secondary">{model}</Badge>
          <Link href="/settings">
            <Settings className="h-4 w-4 text-muted-foreground hover:text-foreground" />
          </Link>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <aside className="flex w-60 shrink-0 flex-col border-r border-border">
          <div className="flex border-b border-border text-xs">
            {(
              [
                ["files", "Files"],
                ["tasks", "Tasks"],
                ["agents", "Agents"],
                ["git", "Git"],
              ] as const
            ).map(([key, label]) => (
              <button
                key={key}
                onClick={() => store.setView(key)}
                className={`flex-1 py-2.5 transition-colors ${
                  store.view === key
                    ? "border-b-2 border-primary text-foreground"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="flex-1 overflow-y-auto">
            {store.view === "files" && <FileExplorer />}
            {store.view === "tasks" && <TasksPanel />}
            {store.view === "agents" && <AgentsPanel />}
            {store.view === "git" && <GitPanel />}
          </div>
        </aside>

        <main className="flex min-w-0 flex-1 flex-col">
          <EditorPanel />
          <TerminalPanel onCommand={runCommand} />
        </main>

        <aside className="flex w-96 shrink-0 flex-col border-l border-border">
          <ChatPanel
            input={input}
            setInput={setInput}
            onSend={sendMessage}
            project={project}
          />
        </aside>
      </div>

      <ApprovalDialogs />
    </div>
  );
}
