export interface Project {
  id: number;
  name: string;
  slug: string;
  description: string;
  workspace_path: string;
  tech_stack: string[];
  status: string;
  permission_mode: string;
  default_model: string;
  created_at: string;
  updated_at: string;
}

export interface Conversation {
  id: number;
  project_id: number;
  title: string;
  created_at: string;
}

export interface Message {
  id: number;
  conversation_id: number;
  role: string;
  content: string;
  agent_type: string;
  meta: Record<string, unknown>;
  created_at: string;
}

export interface AgentInfo {
  id: string;
  name: string;
  description: string;
  emoji: string;
}

export interface Task {
  id: number;
  project_id: number;
  task_id: string;
  title: string;
  description: string;
  priority: string;
  dependencies: string[];
  status: string;
  agent_type: string;
  created_at: string;
  updated_at: string;
}

export interface FileNode {
  name: string;
  type: "file" | "directory";
  size?: number;
  children?: FileNode[];
}

export interface GitStatus {
  branch: string;
  entries: { status: string; path: string }[];
  dirty: boolean;
}

export interface GitCommit {
  hash: string;
  date: string;
  message: string;
}

export interface Checkpoint {
  id: number;
  project_id: number;
  name: string;
  commit_hash: string;
  message: string;
  created_at: string;
}

export interface ProposedChange {
  plan_id: number;
  summary: string;
  files: { path: string; action: string; diff: string }[];
  commands: { command: string; reason: string }[];
}

export interface ApprovalRequest {
  approval_id: number;
  command: string;
  cwd: string;
  agent: string;
  reason: string;
}

export interface TestResult {
  test_run_id: number;
  command: string;
  status: string;
  passed: number;
  failed: number;
  exit_code: number | null;
}

export interface AgentRun {
  id: number;
  project_id: number;
  agent_type: string;
  status: string;
  input_text: string;
  output_text: string;
  error: string;
  started_at: string;
  completed_at: string | null;
}

export interface ModelInfo {
  id: string;
  name: string;
  provider: string;
  local: boolean;
  size_bytes: number;
}

export interface SystemCheck {
  os: string;
  arch: string;
  cpu_cores: number;
  ram_gb: number | null;
  gpu?: string;
  recommended_model: string;
  ollama_running: boolean;
  local_models: ModelInfo[];
  ollama_error?: string;
}

export interface GithubRepo {
  full_name: string;
  private: boolean;
  default_branch: string;
  html_url: string;
}

export interface IntegrationStatus {
  github: { token_set: boolean; user: string | null };
  openai_key_set: boolean;
  openrouter_key_set: boolean;
  auto_push: boolean;
  mcp_servers: string[];
}
