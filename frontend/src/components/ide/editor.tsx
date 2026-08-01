"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useState } from "react";
import { X, CircleDot, Save } from "lucide-react";
import { api } from "@/lib/api";
import { useIdeStore } from "@/store/ide";
import { cn } from "@/lib/utils";

const Monaco = dynamic(() => import("@monaco-editor/react").then((m) => m.default), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
      Loading editor...
    </div>
  ),
});

function languageFor(path: string): string {
  const ext = path.split(".").pop()?.toLowerCase() || "";
  const map: Record<string, string> = {
    py: "python", js: "javascript", mjs: "javascript", cjs: "javascript", jsx: "javascript",
    ts: "typescript", tsx: "typescript", json: "json", md: "markdown", html: "html",
    css: "css", yml: "yaml", yaml: "yaml", sql: "sql", toml: "ini", sh: "shell",
    ps1: "powershell", java: "java", go: "go", rs: "rust", c: "c", h: "c",
    cpp: "cpp", cs: "csharp", rb: "ruby", php: "php", dockerfile: "dockerfile",
  };
  return map[ext] || "plaintext";
}

export function EditorPanel() {
  const store = useIdeStore();
  const active = store.openFiles.find((f) => f.path === store.activeFile);
  const [saving, setSaving] = useState(false);
  const [autoSave, setAutoSave] = useState(true);

  const save = useCallback(async () => {
    if (!active) return;
    setSaving(true);
    try {
      await api.post(`/api/projects/${store.projectId}/files`, {
        path: active.path,
        content: active.content,
        overwrite: true,
      });
      store.updateFileContent(active.path, active.content);
      store.setFileTree(await api.get(`/api/projects/${store.projectId}/files/tree`));
    } catch (e) {
      store.addTerminalLines([`[save error] ${(e as Error).message}`]);
    } finally {
      setSaving(false);
    }
  }, [active, store]);

  useEffect(() => {
    if (autoSave && active?.dirty) {
      const t = setTimeout(save, 1200);
      return () => clearTimeout(t);
    }
  }, [active, autoSave, save]);

  if (!active) {
    return (
      <div className="flex flex-1 items-center justify-center bg-[#1e1e1e] text-sm text-muted-foreground">
        <div className="text-center">
          <div className="mb-2 text-lg">Arynox AI</div>
          <div>Select a file to edit, or ask the AI to build something.</div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center border-b border-border bg-[#252526] text-xs">
        <div className="flex flex-1 items-center overflow-x-auto">
          {store.openFiles.map((f) => (
            <button
              key={f.path}
              onClick={() => store.setActiveFile(f.path)}
              className={cn(
                "group flex max-w-[220px] items-center gap-1.5 border-r border-border px-3 py-2",
                f.path === store.activeFile
                  ? "bg-[#1e1e1e] text-foreground"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <CircleDot className={cn("h-2.5 w-2.5 shrink-0", f.dirty ? "text-amber-400" : "text-transparent")} />
              <span className="truncate">{f.path.split("/").pop()}</span>
              <X
                className="h-3 w-3 shrink-0 opacity-0 group-hover:opacity-70"
                onClick={(e) => {
                  e.stopPropagation();
                  store.closeFile(f.path);
                }}
              />
            </button>
          ))}
        </div>
        <button
          onClick={save}
          disabled={saving || !active.dirty}
          className="flex items-center gap-1 px-3 py-2 text-muted-foreground hover:text-foreground disabled:opacity-40"
          title="Save file"
        >
          <Save className="h-3.5 w-3.5" />
        </button>
      </div>
      <div className="min-h-0 flex-1">
        <Monaco
          key={active.path + active.content.length}
          path={active.path}
          language={languageFor(active.path)}
          value={active.content}
          theme="vs-dark"
          options={{
            fontSize: 13,
            minimap: { enabled: true },
            automaticLayout: true,
            scrollBeyondLastLine: false,
            tabSize: 2,
            wordWrap: "on",
          }}
          onChange={(value) => {
            if (value !== undefined) store.updateFileContent(active.path, value);
          }}
        />
      </div>
    </div>
  );
}
