"use client";

export const dynamic = "force-dynamic";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Bot,
  Cloud,
  Cpu,
  Download,
  GitBranch,
  KeyRound,
  RefreshCw,
  Server,
} from "lucide-react";
import { api, sseUrl } from "@/lib/api";
import type { IntegrationStatus, ModelInfo, SystemCheck } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { fmtBytes } from "@/lib/utils";

export default function SettingsPage() {
  const [sys, setSys] = useState<SystemCheck | null>(null);
  const [current, setCurrent] = useState<{ provider: string; model: string } | null>(null);
  const [providerModels, setProviderModels] = useState<ModelInfo[]>([]);
  const [provider, setProvider] = useState("ollama");
  const [pullModel, setPullModel] = useState("");
  const [pulling, setPulling] = useState(false);
  const [pullLog, setPullLog] = useState<string[]>([]);
  const [modelSettings, setModelSettings] = useState<{
    ai_provider: string;
    ai_model: string;
    ollama_base_url: string;
    openai_base_url: string;
    openai_key_set: boolean;
    openrouter_key_set: boolean;
  } | null>(null);
  const [testing, setTesting] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<string | null>(null);
  const [integ, setInteg] = useState<IntegrationStatus | null>(null);
  const [ghToken, setGhToken] = useState("");
  const [ghStatus, setGhStatus] = useState<string | null>(null);
  const [ghBusy, setGhBusy] = useState(false);
  const [openaiKey, setOpenaiKey] = useState("");
  const [openrouterKey, setOpenrouterKey] = useState("");
  const [keysStatus, setKeysStatus] = useState<string | null>(null);
  const [mcpJson, setMcpJson] = useState("{}");
  const [mcpStatus, setMcpStatus] = useState<string | null>(null);
  const [mcpBusy, setMcpBusy] = useState(false);

  const load = async () => {
    setSys(await api.get<SystemCheck>("/api/models/system-check"));
    setCurrent(await api.get("/api/models/current"));
    setModelSettings(await api.get("/api/models/settings"));
    const m = await api.get<{ models: ModelInfo[] }>(`/api/models/available?provider=ollama`);
    if (provider === "ollama") setProviderModels(m.models);
  };

  const loadIntegrations = async () => {
    const s = await api.get<IntegrationStatus>("/api/integrations/status");
    setInteg(s);
    try {
      const m = await api.get<{ servers: string }>("/api/integrations/mcp");
      setMcpJson(m.servers);
    } catch {
      /* ignore */
    }
  };

  useEffect(() => {
    load().catch(() => setSys(null));
    loadIntegrations().catch(() => setInteg(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadProvider = async (p: string) => {
    setProvider(p);
    const m = await api.get<{ models: ModelInfo[] }>(`/api/models/available?provider=${p}`);
    setProviderModels(m.models);
  };

  const pull = async () => {
    if (!pullModel.trim()) return;
    setPulling(true);
    setPullLog([]);
    setTestResult(null);
    const es = new EventSource(sseUrl(0));
    const onPull = (e: MessageEvent) => {
      try {
        const d = JSON.parse((e as unknown as { data: string }).data);
        if (d.model === pullModel.trim()) {
          setPullLog((l) => [...l, `[model] ${d.status || ""}`]);
        }
      } catch {
        /* ignore */
      }
    };
    es.onmessage = onPull;
    try {
      await api.post("/api/models/pull", { model: pullModel.trim() });
      setPullLog((l) => [...l, "✅ Model ready"]);
      await loadProvider("ollama");
      await load();
    } catch (e) {
      setPullLog((l) => [...l, `❌ ${(e as Error).message}`]);
    } finally {
      es.close();
      setPulling(false);
    }
  };

  const testModel = async (model: string) => {
    setTesting(model);
    setTestResult(null);
    try {
      const r = await api.post<{ ok: boolean; response?: string; error?: string }>(
        `/api/models/test?model=${encodeURIComponent(model)}&provider=${provider}`
      );
      if (r.ok) {
        setTestResult(`✅ Model responded: "${r.response}"`);
      } else {
        setTestResult(`❌ ${r.error || "model failed to respond"}`);
      }
    } catch (e) {
      setTestResult(`❌ ${(e as Error).message}`);
    } finally {
      setTesting(null);
    }
  };

  const downloadRecommended = async () => {
    if (!sys?.recommended_model) return;
    setPullModel(sys.recommended_model);
    await new Promise((r) => setTimeout(r, 200));
    pull();
  };

  const testGithub = async (save = false) => {
    if (!ghToken.trim()) return;
    setGhBusy(true);
    setGhStatus(null);
    try {
      await api.post("/api/integrations/github/test", { token: ghToken.trim() });
      if (save) {
        const r = await api.post<{ ok: boolean; user: string }>("/api/integrations/github/save", {
          token: ghToken.trim(),
        });
        setGhStatus(`✅ Token valid — connected as ${r.user}`);
      } else {
        setGhStatus("✅ Token is valid");
      }
      await loadIntegrations();
    } catch (e) {
      setGhStatus(`❌ ${(e as Error).message}`);
    } finally {
      setGhBusy(false);
    }
  };

  const saveKeys = async () => {
    setKeysStatus(null);
    try {
      await api.post("/api/integrations/keys", {
        openai_api_key: openaiKey.trim() || undefined,
        openrouter_api_key: openrouterKey.trim() || undefined,
      });
      setKeysStatus("✅ Keys saved — provider connections refreshed");
      setOpenaiKey("");
      setOpenrouterKey("");
      await loadIntegrations();
    } catch (e) {
      setKeysStatus(`❌ ${(e as Error).message}`);
    }
  };

  const saveMcp = async () => {
    setMcpBusy(true);
    setMcpStatus(null);
    try {
      const r = await api.post<{ ok: boolean; connected: string[] }>("/api/integrations/mcp", {
        servers: mcpJson,
      });
      setMcpStatus(
        r.connected.length > 0
          ? `✅ MCP connected: ${r.connected.join(", ")}`
          : "✅ MCP config saved (no servers connected — check the JSON)"
      );
      await loadIntegrations();
    } catch (e) {
      setMcpStatus(`❌ ${(e as Error).message}`);
    } finally {
      setMcpBusy(false);
    }
  };

  const toggleAutoPush = async (enabled: boolean) => {
    await api.post("/api/integrations/auto-push", { enabled });
    setInteg((i) => (i ? { ...i, auto_push: enabled } : i));
  };

  return (
    <div className="flex h-full flex-col">
      <header className="flex h-14 items-center gap-3 border-b border-border px-6">
        <Link href="/" className="text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/20">
            <Bot className="h-5 w-5 text-primary" />
          </div>
          <span className="text-sm font-semibold">Settings</span>
        </div>
        <div className="ml-auto text-xs text-muted-foreground">
          {current ? `${current.provider} / ${current.model}` : ""}
        </div>
      </header>

      <main className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto flex max-w-4xl flex-col gap-6">
          <section className="rounded-lg border border-border bg-card p-5">
            <div className="flex items-center gap-2 text-lg font-semibold">
              <Cpu className="h-5 w-5 text-primary" /> System detection
            </div>
            {sys ? (
              <div className="mt-3 grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
                <div className="rounded border border-border p-3">
                  <div className="text-[11px] text-muted-foreground">OS</div>
                  <div className="mt-0.5 font-medium">{sys.os} {sys.arch}</div>
                </div>
                <div className="rounded border border-border p-3">
                  <div className="text-[11px] text-muted-foreground">RAM</div>
                  <div className="mt-0.5 font-medium">{sys.ram_gb ? `${sys.ram_gb} GB` : "unknown"}</div>
                </div>
                <div className="rounded border border-border p-3">
                  <div className="text-[11px] text-muted-foreground">GPU</div>
                  <div className="mt-0.5 truncate font-medium" title={sys.gpu || ""}>{sys.gpu?.split(",")[0] || "none"}</div>
                </div>
                <div className="rounded border border-border p-3">
                  <div className="text-[11px] text-muted-foreground">Recommended model</div>
                  <div className="mt-0.5 font-medium text-primary">{sys.recommended_model}</div>
                </div>
              </div>
            ) : (
              <div className="mt-2 text-sm text-muted-foreground">Detecting system...</div>
            )}
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <Badge variant={sys?.ollama_running ? "success" : "outline"}>
                Ollama: {sys?.ollama_running ? "running" : "offline"}
              </Badge>
              {!sys?.ollama_running && (
                <span className="text-xs text-muted-foreground">
                  Start it with: <code className="rounded bg-secondary px-1">ollama serve</code>
                </span>
              )}
              {sys?.ollama_running && sys?.local_models.length === 0 && (
                <Button size="sm" onClick={downloadRecommended} disabled={pulling}>
                  <Download className="h-4 w-4" />
                  Download recommended model ({sys.recommended_model})
                </Button>
              )}
              <Button size="sm" variant="outline" onClick={load}>
                <RefreshCw className="h-4 w-4" /> Re-detect
              </Button>
            </div>
          </section>

          <section className="rounded-lg border border-border bg-card p-5">
            <div className="text-lg font-semibold">Models</div>
            <div className="mt-3 flex gap-2">
              {[
                ["ollama", "Local (Ollama)"],
                ["openai", "OpenAI-compatible"],
                ["openrouter", "OpenRouter"],
              ].map(([id, label]) => (
                <Button
                  key={id}
                  size="sm"
                  variant={provider === id ? "default" : "outline"}
                  onClick={() => loadProvider(id)}
                >
                  {label}
                </Button>
              ))}
            </div>
            <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
              {providerModels.map((m) => (
                <div key={m.id} className="flex items-center gap-2 rounded border border-border px-3 py-2 text-sm">
                  <span className="flex-1 truncate font-mono">{m.id}</span>
                  {m.local && <span className="text-[10px] text-muted-foreground">{fmtBytes(m.size_bytes)}</span>}
                  {current?.model === m.id && <Badge variant="success">active</Badge>}
                  <Button
                    size="xs"
                    variant="outline"
                    disabled={testing === m.id}
                    onClick={() => testModel(m.id)}
                  >
                    {testing === m.id ? "Testing..." : "Test"}
                  </Button>
                </div>
              ))}
              {providerModels.length === 0 && (
                <div className="text-xs text-muted-foreground">
                  {provider === "ollama"
                    ? "No local models yet — download one below."
                    : "No models listed. Check your API key in backend/.env."}
                </div>
              )}
            </div>
            <div className="mt-4 flex gap-2">
              <input
                value={pullModel}
                onChange={(e) => setPullModel(e.target.value)}
                placeholder="Model name to download, e.g. qwen2.5-coder:7b"
                className="flex-1 rounded-md border border-input bg-transparent px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              />
              <Button onClick={pull} disabled={pulling || !pullModel.trim()}>
                <Download className="h-4 w-4" /> {pulling ? "Downloading..." : "Download"}
              </Button>
            </div>
            {pullLog.length > 0 && (
              <pre className="mt-2 max-h-40 overflow-auto rounded bg-[#1e1e1e] p-2 font-mono text-[11px] text-zinc-400">
                {pullLog.join("\n")}
              </pre>
            )}
            {testResult && (
              <div className="mt-2 text-xs">{testResult}</div>
            )}
          </section>

          <section className="rounded-lg border border-border bg-card p-5">
            <div className="text-lg font-semibold">Integrations</div>
            <div className="mt-3 grid grid-cols-1 gap-6 md:grid-cols-2">
              <div className="space-y-3">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <GitBranch className="h-4 w-4 text-primary" /> GitHub
                  <Badge variant={integ?.github.token_set ? "success" : "outline"}>
                    {integ?.github.token_set ? `connected: ${integ.github.user}` : "no token"}
                  </Badge>
                </div>
                <input
                  type="password"
                  value={ghToken}
                  onChange={(e) => setGhToken(e.target.value)}
                  placeholder="GitHub Personal Access Token (PAT)"
                  className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                />
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" disabled={ghBusy || !ghToken.trim()} onClick={() => testGithub(false)}>
                    Test token
                  </Button>
                  <Button size="sm" disabled={ghBusy || !ghToken.trim()} onClick={() => testGithub(true)}>
                    Save & connect
                  </Button>
                </div>
                {ghStatus && <div className="text-xs">{ghStatus}</div>}
                <div className="text-[11px] text-muted-foreground">
                  Create one at github.com → Settings → Developer settings → Personal access tokens
                  (scope: <code>repo</code>).
                </div>
              </div>

              <div className="space-y-3">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <KeyRound className="h-4 w-4 text-primary" /> API keys
                  <Badge variant={integ?.openai_key_set ? "success" : "outline"}>
                    OpenAI {integ?.openai_key_set ? "set" : "not set"}
                  </Badge>
                  <Badge variant={integ?.openrouter_key_set ? "success" : "outline"}>
                    OpenRouter {integ?.openrouter_key_set ? "set" : "not set"}
                  </Badge>
                </div>
                <input
                  type="password"
                  value={openaiKey}
                  onChange={(e) => setOpenaiKey(e.target.value)}
                  placeholder="OpenAI / OpenAI-compatible API key"
                  className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                />
                <input
                  type="password"
                  value={openrouterKey}
                  onChange={(e) => setOpenrouterKey(e.target.value)}
                  placeholder="OpenRouter API key"
                  className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                />
                <Button size="sm" onClick={saveKeys}>Save keys</Button>
                {keysStatus && <div className="text-xs">{keysStatus}</div>}
                <div className="text-[11px] text-muted-foreground">
                  Stored locally in the app database — no .env editing needed. Switch providers in
                  the Models section above.
                </div>
              </div>

              <div className="space-y-3 md:col-span-2">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <Server className="h-4 w-4 text-primary" /> MCP servers
                  <Badge variant="outline">{integ?.mcp_servers.length ? `${integ.mcp_servers.length} tool(s)` : "none"}</Badge>
                </div>
                <textarea
                  value={mcpJson}
                  onChange={(e) => setMcpJson(e.target.value)}
                  rows={4}
                  spellCheck={false}
                  placeholder={'{"filesystem": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "C:/projects"]}}'}
                  className="w-full rounded-md border border-input bg-[#1e1e1e] px-3 py-2 font-mono text-xs text-zinc-300 outline-none focus:ring-2 focus:ring-ring"
                />
                <div className="flex items-center gap-2">
                  <Button size="sm" disabled={mcpBusy} onClick={saveMcp}>Save & connect</Button>
                  <span className="text-[11px] text-muted-foreground">
                    JSON object of servers — each needs <code>command</code>+<code>args</code> or <code>url</code>.
                  </span>
                </div>
                {mcpStatus && <div className="text-xs">{mcpStatus}</div>}
              </div>

              <div className="flex items-center gap-2 md:col-span-2">
                <label className="flex cursor-pointer items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={integ?.auto_push ?? false}
                    onChange={(e) => toggleAutoPush(e.target.checked)}
                    className="h-4 w-4 accent-primary"
                  />
                  <Cloud className="h-4 w-4 text-primary" /> Auto-push workspace to GitHub after every agent run
                </label>
                <span className="text-[11px] text-muted-foreground">
                  (requires a connected GitHub token)
                </span>
              </div>
            </div>
          </section>

          <section className="rounded-lg border border-border bg-card p-5">
            <div className="text-lg font-semibold">Configuration</div>
            <div className="mt-3 space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">AI provider (AI_PROVIDER)</span>
                <code className="font-mono">{modelSettings?.ai_provider}</code>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Default model (AI_MODEL)</span>
                <code className="font-mono">{modelSettings?.ai_model}</code>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Ollama base URL</span>
                <code className="font-mono">{modelSettings?.ollama_base_url}</code>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">OpenAI-compatible endpoint</span>
                <code className="font-mono">{modelSettings?.openai_base_url}</code>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">OpenAI key configured</span>
                <Badge variant={modelSettings?.openai_key_set ? "success" : "outline"}>
                  {modelSettings?.openai_key_set ? "yes" : "no"}
                </Badge>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">OpenRouter key configured</span>
                <Badge variant={modelSettings?.openrouter_key_set ? "success" : "outline"}>
                  {modelSettings?.openrouter_key_set ? "yes" : "no"}
                </Badge>
              </div>
            </div>
            <div className="mt-3 text-xs text-muted-foreground">
              Configure API keys and the default provider in <code className="rounded bg-secondary px-1">backend/.env</code>{" "}
              (see <code className="rounded bg-secondary px-1">backend/.env.example</code>).
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
