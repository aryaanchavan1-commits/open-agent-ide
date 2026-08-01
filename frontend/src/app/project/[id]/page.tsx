"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Bot, Settings, ArrowLeft } from "lucide-react";
import { api } from "@/lib/api";
import type { Project } from "@/lib/types";
import { IdeWorkspace } from "@/components/ide/ide-workspace";
import { Button } from "@/components/ui/button";

export default function ProjectPage({ params }: { params: { id: string } }) {
  const projectId = parseInt(params.id, 10);
  const [project, setProject] = useState<Project | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<Project>(`/api/projects/${projectId}`).then(setProject).catch((e) => setError(e.message));
  }, [projectId]);

  if (error) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4">
        <div className="text-lg">Project not found</div>
        <div className="text-sm text-muted-foreground">{error}</div>
        <Link href="/">
          <Button size="sm"><ArrowLeft className="h-4 w-4" /> Back to projects</Button>
        </Link>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="flex h-full items-center justify-center">
        <Bot className="h-8 w-8 animate-pulse text-primary" />
      </div>
    );
  }

  return <IdeWorkspace project={project} />;
}
