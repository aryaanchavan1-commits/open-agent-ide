"use client";

import { CheckCircle2, Circle, Loader2, MinusCircle, Play } from "lucide-react";
import { api } from "@/lib/api";
import { useIdeStore } from "@/store/ide";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const STATUS_STYLE: Record<string, { icon: React.ReactNode; cls: string }> = {
  pending: { icon: <Circle className="h-3.5 w-3.5" />, cls: "text-zinc-500" },
  in_progress: { icon: <Loader2 className="h-3.5 w-3.5 spinner" />, cls: "text-sky-400" },
  completed: { icon: <CheckCircle2 className="h-3.5 w-3.5" />, cls: "text-emerald-400" },
  failed: { icon: <MinusCircle className="h-3.5 w-3.5" />, cls: "text-red-400" },
};

const PRIORITY_COLOR: Record<string, "danger" | "warning" | "secondary"> = {
  high: "danger",
  medium: "warning",
  low: "secondary",
};

export function TasksPanel() {
  const store = useIdeStore();

  const runTask = async (taskId: string) => {
    await api.post(`/api/projects/${store.projectId}/agents/run`, {
      agent_type: "coder",
      prompt: `Implement the task ${taskId}`,
      task_id: taskId,
    });
  };

  return (
    <div className="p-2">
      {store.tasks.length === 0 && (
        <div className="p-4 text-xs text-muted-foreground">
          No tasks yet. Ask the Planner to analyze the project:{" "}
          <button
            className="text-primary hover:underline"
            onClick={() => {
              /* chat is in right panel */
            }}
          >
            "Plan this project"
          </button>
        </div>
      )}
      {store.tasks.map((t) => {
        const st = STATUS_STYLE[t.status] || STATUS_STYLE.pending;
        return (
          <div key={t.id} className="mb-2 rounded border border-border bg-card p-2.5">
            <div className="flex items-center gap-2">
              <span className={st.cls}>{st.icon}</span>
              <span className="flex-1 text-[13px] font-medium">{t.task_id}</span>
              <Badge variant={PRIORITY_COLOR[t.priority] || "secondary"}>{t.priority}</Badge>
            </div>
            <div className="mt-1 pl-6 text-[13px] text-foreground">{t.title}</div>
            <div className="mt-1 line-clamp-2 pl-6 text-[11px] text-muted-foreground">
              {t.description}
            </div>
            <div className="mt-2 flex items-center justify-between pl-6">
              <span className="text-[10px] text-muted-foreground">
                {t.dependencies.length ? `depends on: ${t.dependencies.join(", ")}` : "no dependencies"}
              </span>
              {(t.status === "pending" || t.status === "failed") && (
                <Button
                  size="xs"
                  variant="outline"
                  className={cn(t.status === "failed" && "border-red-500/40 text-red-400")}
                  onClick={() => runTask(t.task_id)}
                >
                  <Play className="h-3 w-3" /> {t.status === "failed" ? "Retry" : "Run"}
                </Button>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
