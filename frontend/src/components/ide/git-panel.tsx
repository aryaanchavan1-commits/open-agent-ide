"use client";

import { useState } from "react";
import { GitBranch, GitCommitHorizontal, GitCommitVertical, History, Plus, Upload } from "lucide-react";
import { api } from "@/lib/api";
import { useIdeStore } from "@/store/ide";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { GithubRepo } from "@/lib/types";

export function GitPanel() {
  const store = useIdeStore();
  const [commitMsg, setCommitMsg] = useState("");
  const [branchName, setBranchName] = useState("");
  const [busy, setBusy] = useState(false);
  const [branches, setBranches] = useState<string[]>([]);
  const [commits, setCommits] = useState<{ hash: string; date: string; message: string }[]>([]);
  const [checkpointName, setCheckpointName] = useState("");
  const [repos, setRepos] = useState<GithubRepo[]>([]);
  const [repo, setRepo] = useState("");
  const [pushStatus, setPushStatus] = useState<string | null>(null);
  const [githubUser, setGithubUser] = useState<string | null>(null);

  const refresh = async () => {
    try {
      store.setGitStatus(await api.get(`/api/projects/${store.projectId}/git/status`));
      store.setCheckpoints(await api.get(`/api/projects/${store.projectId}/git/checkpoints`));
      const b = await api.get<{ branches: string[] }>(`/api/projects/${store.projectId}/git/branches`);
      setBranches(b.branches);
      const l = await api.get<{ commits: { hash: string; date: string; message: string }[] }>(
        `/api/projects/${store.projectId}/git/log`
      );
      setCommits(l.commits);
    } catch {
      /* ignore */
    }
  };

  const loadRepos = async () => {
    setPushStatus(null);
    try {
      const r = await api.get<{ repos: GithubRepo[] }>("/api/integrations/github/repos");
      setRepos(r.repos);
      if (r.repos.length > 0) setRepo(r.repos[0].full_name);
      const s = await api.get<{ github: { user: string | null } }>("/api/integrations/status");
      setGithubUser(s.github.user);
    } catch (e) {
      setPushStatus(`❌ ${(e as Error).message}`);
    }
  };

  const push = async () => {
    setBusy(true);
    setPushStatus(null);
    try {
      const r = await api.post<{ ok: boolean; repo: string; branch: string }>(
        "/api/integrations/github/push",
        { project_id: store.projectId, repo, create_if_missing: false, branch: "main" }
      );
      setPushStatus(`✅ Pushed to ${r.repo} (${r.branch})`);
    } catch (e) {
      setPushStatus(`❌ ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    try {
      await fn();
      await refresh();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-3 p-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-[13px] font-medium">
          <GitBranch className="h-4 w-4 text-primary" />
          {store.gitStatus?.branch || "loading..."}
          {store.gitStatus?.dirty && <Badge variant="warning">dirty</Badge>}
        </div>
        <Button size="xs" variant="ghost" onClick={refresh}>refresh</Button>
      </div>

      <div>
        <div className="mb-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          Changes
        </div>
        <div className="rounded border border-border">
          {store.gitStatus?.entries.length === 0 && (
            <div className="p-2 text-[11px] text-muted-foreground">Working tree clean</div>
          )}
          {store.gitStatus?.entries.map((e, i) => (
            <div key={i} className="flex items-center gap-2 border-b border-border px-2 py-1.5 text-xs last:border-0">
              <Badge variant={e.status.includes("?") ? "secondary" : e.status.includes("D") ? "danger" : "success"}>
                {e.status.trim()}
              </Badge>
              <span className="truncate">{e.path}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="flex gap-1.5">
        <input
          value={commitMsg}
          onChange={(e) => setCommitMsg(e.target.value)}
          placeholder="Commit message..."
          className="flex-1 rounded border border-border bg-transparent px-2 py-1.5 text-xs outline-none"
        />
        <Button
          size="sm"
          disabled={busy || !commitMsg.trim()}
          onClick={() => act(() => api.post(`/api/projects/${store.projectId}/git/commit`, { message: commitMsg }))}
        >
          <GitCommitHorizontal className="h-3.5 w-3.5" /> Commit
        </Button>
      </div>

      <div>
        <div className="mb-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          Branches
        </div>
        <div className="mb-1.5 flex gap-1.5">
          <input
            value={branchName}
            onChange={(e) => setBranchName(e.target.value)}
            placeholder="New branch name..."
            className="flex-1 rounded border border-border bg-transparent px-2 py-1.5 text-xs outline-none"
          />
          <Button
            size="sm"
            variant="outline"
            disabled={busy || !branchName.trim()}
            onClick={() => act(() => api.post(`/api/projects/${store.projectId}/git/branches`, { name: branchName }))}
          >
            <Plus className="h-3.5 w-3.5" /> Create
          </Button>
        </div>
        <div className="flex flex-wrap gap-1">
          {branches.map((b) => (
            <button
              key={b}
              onClick={() => act(() => api.post(`/api/projects/${store.projectId}/git/checkout?branch=${encodeURIComponent(b)}`))}
              className="rounded-full border border-border px-2 py-0.5 text-[11px] hover:border-primary"
            >
              {b}
            </button>
          ))}
        </div>
      </div>

      <div>
        <div className="mb-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          Checkpoints
        </div>
        <div className="mb-1.5 flex gap-1.5">
          <input
            value={checkpointName}
            onChange={(e) => setCheckpointName(e.target.value)}
            placeholder="Checkpoint name..."
            className="flex-1 rounded border border-border bg-transparent px-2 py-1.5 text-xs outline-none"
          />
          <Button
            size="sm"
            variant="outline"
            disabled={busy}
            onClick={() =>
              act(() =>
                api.post(`/api/projects/${store.projectId}/git/checkpoints`, {
                  name: checkpointName || undefined,
                  message: checkpointName || "AI checkpoint",
                })
              )
            }
          >
            <History className="h-3.5 w-3.5" /> Save
          </Button>
        </div>
        {store.checkpoints.map((c) => (
          <div key={c.id} className="mb-1 flex items-center gap-2 rounded border border-border px-2 py-1.5 text-xs">
            <GitCommitVertical className="h-3.5 w-3.5 text-amber-400" />
            <span className="flex-1 truncate">{c.name}</span>
            <button
              className="text-primary hover:underline"
              onClick={() => {
                if (confirm(`Restore checkpoint '${c.name}'? Uncommitted work will be lost.`)) {
                  act(() => api.post(`/api/projects/${store.projectId}/git/checkpoints/${c.id}/restore`));
                }
              }}
            >
              restore
            </button>
          </div>
        ))}
      </div>

      <div>
        <div className="mb-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          Push to GitHub
        </div>
        <div className="mb-1.5 flex gap-1.5">
          <select
            value={repo}
            onChange={(e) => setRepo(e.target.value)}
            className="flex-1 rounded border border-border bg-transparent px-2 py-1.5 text-xs outline-none"
          >
            {repos.length === 0 && <option value="">{githubUser ? `No repos — create one on github.com as ${githubUser}` : "Connect GitHub in Settings first"}</option>}
            {repos.map((r) => (
              <option key={r.full_name} value={r.full_name}>{r.full_name}</option>
            ))}
          </select>
          <Button size="sm" variant="outline" disabled={busy} onClick={loadRepos}>repos</Button>
          <Button size="sm" disabled={busy || !repo} onClick={push}>
            <Upload className="h-3.5 w-3.5" /> Push
          </Button>
        </div>
        {pushStatus && <div className="text-[11px]">{pushStatus}</div>}
      </div>

      {commits.length > 0 && (
        <div>
          <div className="mb-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            History
          </div>
          {commits.map((c) => (
            <div key={c.hash} className="flex items-center gap-2 text-[11px] text-muted-foreground">
              <span className="font-mono text-primary">{c.hash.slice(0, 7)}</span>
              <span className="truncate">{c.message}</span>
              <span className="ml-auto shrink-0">{c.date}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
