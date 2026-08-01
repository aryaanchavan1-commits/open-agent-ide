"use client";

export const dynamic = "force-dynamic";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Bot, FolderPlus, FolderOpen, Settings, Boxes, Cpu } from "lucide-react";
import { api } from "@/lib/api";
import type { Project, SystemCheck } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input, Textarea } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { fmtBytes } from "@/lib/utils";

export default function HomePage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [sys, setSys] = useState<SystemCheck | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [tech, setTech] = useState("");
  const [creating, setCreating] = useState(false);
  const [open, setOpen] = useState(false);

  const load = async () => {
    try {
      setProjects(await api.get<Project[]>("/api/projects"));
      setSys(await api.get<SystemCheck>("/api/models/system-check"));
    } catch {
      /* backend not up */
    }
  };

  useEffect(() => {
    load();
  }, []);

  const create = async () => {
    if (!name.trim()) return;
    setCreating(true);
    try {
      const p = await api.post<Project>("/api/projects", {
        name: name.trim(),
        description,
        tech_stack: tech.split(",").map((t) => t.trim()).filter(Boolean),
      });
      window.location.href = `/project/${p.id}`;
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="flex h-full flex-col">
      <header className="flex h-14 items-center justify-between border-b border-border px-6">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/20">
            <Bot className="h-5 w-5 text-primary" />
          </div>
          <div>
            <div className="text-sm font-semibold">Arynox AI</div>
            <div className="text-[11px] text-muted-foreground">Local AI software engineering platform</div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Badge variant={sys?.ollama_running ? "success" : "outline"}>
            <Cpu className="mr-1 h-3 w-3" />
            {sys?.ollama_running ? "Ollama online" : "Ollama offline"}
          </Badge>
          <Link href="/settings">
            <Button variant="ghost" size="sm">
              <Settings className="h-4 w-4" /> Settings
            </Button>
          </Link>
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button size="sm">
                <FolderPlus className="h-4 w-4" /> New Project
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogTitle>Create a new project</DialogTitle>
              <DialogDescription>
                Describe the application you want to build. AI agents will plan, code, test and debug it.
              </DialogDescription>
              <div className="mt-4 flex flex-col gap-3">
                <Input placeholder="Project name" value={name} onChange={(e) => setName(e.target.value)} />
                <Textarea
                  placeholder="Describe the application... e.g. 'A FastAPI backend for a pharmacy inventory system with barcode scanning and low-stock alerts.'"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={5}
                />
                <Input
                  placeholder="Tech stack (comma separated, optional)"
                  value={tech}
                  onChange={(e) => setTech(e.target.value)}
                />
                <Button onClick={create} disabled={creating || !name.trim()}>
                  {creating ? "Creating..." : "Create project"}
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </header>

      <main className="flex-1 overflow-y-auto p-8">
        <div className="mx-auto max-w-5xl">
          <div className="mb-6 rounded-lg border border-border bg-card p-5">
            <div className="flex items-center gap-2 text-lg font-semibold">
              <Boxes className="h-5 w-5 text-primary" /> Your projects
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              {sys?.ollama_running
                ? `Local models: ${sys.local_models.map((m) => m.name).join(", ") || "none installed yet"} — recommended: ${sys.recommended_model}`
                : "Start Ollama to use local models (auto-downloads if missing), or configure an API provider in Settings."}
            </p>
          </div>

          {projects.length === 0 ? (
            <div className="flex flex-col items-center gap-4 rounded-lg border border-dashed border-border p-16 text-center">
              <FolderOpen className="h-12 w-12 text-muted-foreground" />
              <div className="text-lg font-medium">No projects yet</div>
              <div className="max-w-sm text-sm text-muted-foreground">
                Create your first project and let the Arynox agents build it for you — from planning to tests.
              </div>
              <Button onClick={() => setOpen(true)}>
                <FolderPlus className="h-4 w-4" /> Create your first project
              </Button>
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {projects.map((p) => (
                <Link
                  key={p.id}
                  href={`/project/${p.id}`}
                  className="group rounded-lg border border-border bg-card p-4 transition-colors hover:border-primary/50"
                >
                  <div className="flex items-start justify-between">
                    <div className="font-medium group-hover:text-primary">{p.name}</div>
                    <Badge variant={p.status === "planned" ? "warning" : "secondary"}>{p.status}</Badge>
                  </div>
                  <div className="mt-2 line-clamp-3 text-sm text-muted-foreground">
                    {p.description || "No description"}
                  </div>
                  <div className="mt-3 flex flex-wrap gap-1">
                    {p.tech_stack.slice(0, 4).map((t) => (
                      <Badge key={t} variant="outline">{t}</Badge>
                    ))}
                  </div>
                  <div className="mt-3 text-[11px] text-muted-foreground">
                    Model: {p.default_model}
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
