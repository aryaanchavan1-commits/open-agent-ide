"use client";

import { useState } from "react";
import { Play } from "lucide-react";
import { api } from "@/lib/api";
import { useIdeStore } from "@/store/ide";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export function AgentsPanel() {
  const store = useIdeStore();
  const [running, setRunning] = useState<string | null>(null);

  const runAgent = async (agentId: string, prompt: string) => {
    setRunning(agentId);
    try {
      await api.post(`/api/projects/${store.projectId}/agents/run`, {
        agent_type: agentId,
        prompt,
      });
    } finally {
      setTimeout(() => setRunning(null), 1500);
    }
  };

  return (
    <div className="p-2">
      {store.agents.map((a) => (
        <div key={a.id} className="mb-2 rounded border border-border bg-card p-3">
          <div className="flex items-center gap-2">
            <span className="text-base">{a.emoji}</span>
            <span className="flex-1 text-[13px] font-medium">{a.name}</span>
            {store.runs.filter((r) => r.agent_type === a.id && r.status === "running").length > 0 && (
              <Badge variant="warning">
                <span className="mr-1 h-2 w-2 rounded-full bg-amber-400 animate-pulse" />running
              </Badge>
            )}
          </div>
          <div className="mt-1 text-[11px] text-muted-foreground">{a.description}</div>
          <div className="mt-2 flex gap-1">
            <Button size="xs" variant="outline" disabled={running === a.id} onClick={() => runAgent(a.id, "Run the default action for this agent on the current project")}>
              <Play className="h-3 w-3" /> Run
            </Button>
          </div>
        </div>
      ))}
    </div>
  );
}
