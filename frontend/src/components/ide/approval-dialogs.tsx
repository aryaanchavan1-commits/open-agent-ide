"use client";

import { useState } from "react";
import { Check, ShieldAlert, X } from "lucide-react";
import { api } from "@/lib/api";
import { useIdeStore } from "@/store/ide";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

function DiffBlock({ diff }: { diff: string }) {
  const [collapsed, setCollapsed] = useState(false);
  return (
    <div className="mb-2 rounded border border-border">
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="w-full bg-secondary/50 px-3 py-1.5 text-left font-mono text-xs text-foreground"
      >
        {collapsed ? "▸" : "▾"} {diff.split("\n")[0]?.slice(3) || "file"}
      </button>
      {!collapsed && (
        <pre className="max-h-56 overflow-auto bg-[#1e1e1e] px-3 py-2 font-mono text-[11px] leading-relaxed">
          {diff.split("\n").slice(1).map((line, i) => (
            <div
              key={i}
              className={cn(
                line.startsWith("+") && "bg-emerald-500/10 text-emerald-300",
                line.startsWith("-") && "bg-red-500/10 text-red-300",
                line.startsWith("@@") && "bg-sky-500/10 text-sky-300",
                !line.startsWith("+") && !line.startsWith("-") && !line.startsWith("@@") && "text-zinc-400"
              )}
            >
              {line || " "}
            </div>
          ))}
        </pre>
      )}
    </div>
  );
}

export function ApprovalDialogs() {
  const store = useIdeStore();
  const changes = store.proposedChanges;
  const [busy, setBusy] = useState(false);
  const [expandedCmd, setExpandedCmd] = useState<number | null>(null);

  const respond = async (id: number, decision: "approve" | "reject") => {
    setBusy(true);
    try {
      await api.post(`/api/approvals/${id}/respond`, { decision });
      if (changes && id === changes.plan_id) store.setProposedChanges(null);
      store.removeApproval(id);
    } catch {
      /* ignore */
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Dialog
        open={changes !== null}
        onOpenChange={(open) => !open && store.setProposedChanges(null)}
      >
        <DialogContent className="max-w-3xl">
          <DialogTitle>Proposed AI changes — review before applying</DialogTitle>
          <DialogDescription>{changes?.summary}</DialogDescription>
          <div className="mt-3 max-h-[50vh] overflow-y-auto">
            {changes?.files.map((f) => (
              <DiffBlock key={f.path + f.action} diff={f.diff || `${f.action}: ${f.path}`} />
            ))}
          </div>
          {changes && changes.commands.length > 0 && (
            <div className="mt-2">
              <div className="mb-1 text-xs font-medium text-muted-foreground">
                Commands to run after applying:
              </div>
              {changes.commands.map((c, i) => (
                <div key={i} className="mb-1 flex items-center gap-2 text-xs">
                  <code className="rounded bg-secondary px-2 py-0.5">{c.command}</code>
                  <span className="text-muted-foreground">{c.reason}</span>
                </div>
              ))}
            </div>
          )}
          <div className="mt-4 flex justify-end gap-2">
            <Button
              variant="outline"
              disabled={busy}
              onClick={() => changes && respond(changes.plan_id, "reject")}
            >
              <X className="h-4 w-4" /> Reject
            </Button>
            <Button disabled={busy} onClick={() => changes && respond(changes.plan_id, "approve")}>
              <Check className="h-4 w-4" /> Apply changes
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {store.approvals.length > 0 && (
        <div className="fixed bottom-4 right-[26rem] z-40 w-96">
          {store.approvals.map((a) => (
            <div key={a.approval_id} className="mb-2 rounded-lg border border-amber-500/40 bg-card p-3 shadow-2xl">
              <div className="flex items-center gap-2 text-sm font-medium text-amber-400">
                <ShieldAlert className="h-4 w-4" />
                Command approval required
              </div>
              <div className="mt-2 rounded bg-secondary px-2 py-1 font-mono text-xs">{a.command}</div>
              <div className="mt-1 text-[11px] text-muted-foreground">
                cwd: {a.cwd} · agent: {a.agent}
              </div>
              <div className="mt-1 text-[11px] text-muted-foreground">{a.reason}</div>
              {expandedCmd === a.approval_id && (
                <pre className="mt-2 max-h-32 overflow-auto rounded bg-[#1e1e1e] p-2 text-[10px] text-zinc-400">
                  Command will run in the project workspace with a {a.cwd} working directory.
                </pre>
              )}
              <div className="mt-3 flex justify-end gap-2">
                <Button size="sm" variant="outline" disabled={busy} onClick={() => respond(a.approval_id, "reject")}>
                  Reject
                </Button>
                <Button size="sm" disabled={busy} onClick={() => respond(a.approval_id, "approve")}>
                  Approve
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
