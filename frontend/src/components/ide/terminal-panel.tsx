"use client";

import { useEffect, useRef, useState } from "react";
import { Terminal as TerminalIcon, Trash2, ChevronDown, ChevronRight, FlaskConical } from "lucide-react";
import { useIdeStore } from "@/store/ide";
import { cn } from "@/lib/utils";

type Tab = "terminal" | "tests";

export function TerminalPanel({ onCommand }: { onCommand: (cmd: string) => void }) {
  const store = useIdeStore();
  const [tab, setTab] = useState<Tab>("terminal");
  const [cmd, setCmd] = useState("");
  const [collapsed, setCollapsed] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [store.terminalLines, store.testResults]);

  const run = () => {
    if (!cmd.trim()) return;
    onCommand(cmd.trim());
    setCmd("");
  };

  return (
    <div className="flex h-48 shrink-0 flex-col border-t border-border bg-[#1e1e1e]">
      <div className="flex items-center justify-between border-b border-border bg-[#252526] px-3 py-1.5">
        <div className="flex items-center gap-1 text-xs">
          <button
            onClick={() => { setTab("terminal"); setCollapsed(false); }}
            className={cn(
              "flex items-center gap-1 rounded px-2 py-1",
              tab === "terminal" ? "bg-secondary text-foreground" : "text-muted-foreground hover:text-foreground"
            )}
          >
            <TerminalIcon className="h-3.5 w-3.5" /> Terminal
          </button>
          <button
            onClick={() => { setTab("tests"); setCollapsed(false); }}
            className={cn(
              "flex items-center gap-1 rounded px-2 py-1",
              tab === "tests" ? "bg-secondary text-foreground" : "text-muted-foreground hover:text-foreground"
            )}
          >
            <FlaskConical className="h-3.5 w-3.5" /> Test Results
          </button>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => store.clearTerminal()}
            className="text-muted-foreground hover:text-foreground"
            title="Clear terminal"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="text-muted-foreground hover:text-foreground"
          >
            {collapsed ? <ChevronUpIcon /> : <ChevronDown className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {!collapsed && (
        <>
          {tab === "terminal" && (
            <div className="flex min-h-0 flex-1 flex-col">
              <div ref={scrollRef} className="flex-1 overflow-y-auto px-3 py-2 font-mono text-xs leading-relaxed text-zinc-300">
                {store.terminalLines.length === 0 && (
                  <div className="text-zinc-600">No output yet. Run a command or ask the AI to run tests.</div>
                )}
                {store.terminalLines.map((line, i) => (
                  <div key={i} className={cn(line.startsWith("[") && "text-zinc-500")}>{line}</div>
                ))}
              </div>
              <div className="flex items-center gap-2 border-t border-border px-3 py-1.5">
                <span className="font-mono text-xs text-emerald-400">❯</span>
                <input
                  value={cmd}
                  onChange={(e) => setCmd(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && run()}
                  placeholder="Run a command in the project workspace (e.g. pytest, npm test)..."
                  className="w-full bg-transparent font-mono text-xs outline-none placeholder:text-zinc-600"
                />
              </div>
            </div>
          )}
          {tab === "tests" && (
            <div className="flex-1 overflow-y-auto px-3 py-2">
              {store.testResults.length === 0 && (
                <div className="text-xs text-zinc-600">No test runs yet.</div>
              )}
              {store.testResults.map((t) => (
                <div key={t.test_run_id} className="mb-2 rounded border border-border p-2 text-xs">
                  <div className="flex items-center gap-2">
                    <span
                      className={cn(
                        "h-2 w-2 rounded-full",
                        t.status === "passed" ? "bg-emerald-400" : t.status === "failed" ? "bg-red-400" : "bg-amber-400"
                      )}
                    />
                    <span className="font-mono">{t.command}</span>
                    <span className={cn(t.status === "passed" ? "text-emerald-400" : "text-red-400")}>
                      {t.passed} passed, {t.failed} failed
                    </span>
                    {t.exit_code !== null && <span className="text-zinc-500">exit {t.exit_code}</span>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function ChevronUpIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="m18 15-6-6-6 6" />
    </svg>
  );
}
