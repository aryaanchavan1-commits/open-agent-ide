"use client";

import { useState } from "react";
import { File, Folder, FolderOpen, Search } from "lucide-react";
import { api } from "@/lib/api";
import { useIdeStore } from "@/store/ide";
import type { FileNode } from "@/lib/types";
import { cn } from "@/lib/utils";

function extOf(name: string): string {
  const i = name.lastIndexOf(".");
  return i === -1 ? "txt" : name.slice(i + 1);
}

const EXT_COLORS: Record<string, string> = {
  py: "text-sky-400",
  ts: "text-blue-400",
  tsx: "text-blue-400",
  js: "text-yellow-400",
  jsx: "text-yellow-400",
  json: "text-amber-300",
  md: "text-violet-400",
  html: "text-orange-400",
  css: "text-pink-400",
  yml: "text-red-400",
  yaml: "text-red-400",
  sql: "text-emerald-400",
  toml: "text-teal-400",
};

function FileIcon({ name, isDir, open }: { name: string; isDir: boolean; open?: boolean }) {
  if (isDir) return open ? <FolderOpen className="h-4 w-4 text-amber-400" /> : <Folder className="h-4 w-4 text-amber-400" />;
  return <File className={cn("h-4 w-4", EXT_COLORS[extOf(name)] || "text-muted-foreground")} />;
}

function TreeNode({ node, path, depth }: { node: FileNode; path: string; depth: number }) {
  const [expanded, setExpanded] = useState(depth < 1);
  const store = useIdeStore();
  const fullPath = path ? `${path}/${node.name}` : node.name;

  const openFile = async () => {
    if (node.type === "directory") {
      setExpanded(!expanded);
      return;
    }
    const existing = store.openFiles.find((f) => f.path === fullPath);
    if (existing) {
      store.setActiveFile(fullPath);
      return;
    }
    try {
      const r = await api.get<{ content: string }>(
        `/api/projects/${store.projectId}/files/content?path=${encodeURIComponent(fullPath)}`
      );
      store.openFile(fullPath, r.content);
    } catch {
      /* ignore */
    }
  };

  return (
    <div>
      <button
        onClick={openFile}
        className={cn(
          "flex w-full items-center gap-1.5 rounded px-2 py-1 text-left text-[13px] hover:bg-secondary/60",
          store.activeFile === fullPath && node.type === "file" && "bg-secondary text-primary",
          node.type === "directory" && "font-medium text-muted-foreground"
        )}
        style={{ paddingLeft: `${8 + depth * 14}px` }}
      >
        <FileIcon name={node.name} isDir={node.type === "directory"} open={expanded} />
        <span className="truncate">{node.name}</span>
      </button>
      {node.type === "directory" && expanded && node.children && (
        <div>
          {node.children.map((c) => (
            <TreeNode key={c.name} node={c} path={fullPath} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

export function FileExplorer() {
  const store = useIdeStore();
  const [query, setQuery] = useState("");

  const filterNodes = (nodes: FileNode[]): FileNode[] => {
    if (!query) return nodes;
    const q = query.toLowerCase();
    const walk = (list: FileNode[]): FileNode[] =>
      list.flatMap((n) => {
        if (n.type === "directory") {
          const children = walk(n.children || []);
          return children.length ? [{ ...n, children }] : [];
        }
        return n.name.toLowerCase().includes(q) ? [n] : [];
      });
    return walk(nodes);
  };

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border p-2">
        <div className="flex items-center gap-2 rounded-md border border-border px-2 py-1">
          <Search className="h-3.5 w-3.5 text-muted-foreground" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter files..."
            className="w-full bg-transparent text-xs outline-none placeholder:text-muted-foreground"
          />
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-1">
        {store.fileTree.length === 0 && (
          <div className="p-4 text-xs text-muted-foreground">
            No files yet. Ask the AI in the chat to create the project.
          </div>
        )}
        {filterNodes(store.fileTree).map((n) => (
          <TreeNode key={n.name} node={n} path="" depth={0} />
        ))}
      </div>
    </div>
  );
}
