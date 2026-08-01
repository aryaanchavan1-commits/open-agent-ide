import { create } from "zustand";
import type {
  AgentInfo,
  AgentRun,
  ApprovalRequest,
  Checkpoint,
  Conversation,
  FileNode,
  GitStatus,
  Message,
  ProposedChange,
  Task,
  TestResult,
} from "@/lib/types";

export type ViewMode = "files" | "tasks" | "agents" | "git";

interface OpenFile {
  path: string;
  content: string;
  dirty: boolean;
}

interface ChatState {
  messages: Message[];
  streaming: boolean;
  statusLine: string;
  statusEmoji: string;
}

interface IdeState {
  projectId: number | null;
  conversations: Conversation[];
  activeConversation: number | null;
  chat: ChatState;
  fileTree: FileNode[];
  openFiles: OpenFile[];
  activeFile: string | null;
  view: ViewMode;
  agents: AgentInfo[];
  tasks: Task[];
  runs: AgentRun[];
  gitStatus: GitStatus | null;
  checkpoints: Checkpoint[];
  terminalLines: string[];
  testResults: TestResult[];
  approvals: ApprovalRequest[];
  proposedChanges: ProposedChange | null;
  permissionMode: string;

  setProject: (id: number) => void;
  setView: (v: ViewMode) => void;
  setConversations: (c: Conversation[]) => void;
  setActiveConversation: (id: number | null) => void;
  appendMessage: (m: Message) => void;
  setMessages: (m: Message[]) => void;
  setStreaming: (s: boolean) => void;
  setStatus: (line: string, emoji?: string) => void;
  setFileTree: (t: FileNode[]) => void;
  openFile: (path: string, content: string) => void;
  setActiveFile: (path: string | null) => void;
  updateFileContent: (path: string, content: string) => void;
  closeFile: (path: string) => void;
  setAgents: (a: AgentInfo[]) => void;
  setTasks: (t: Task[]) => void;
  updateTask: (t: Task) => void;
  setRuns: (r: AgentRun[]) => void;
  setGitStatus: (g: GitStatus | null) => void;
  setCheckpoints: (c: Checkpoint[]) => void;
  addTerminalLines: (lines: string[]) => void;
  clearTerminal: () => void;
  setTestResults: (t: TestResult[]) => void;
  addTestResult: (t: TestResult) => void;
  addApproval: (a: ApprovalRequest) => void;
  removeApproval: (id: number) => void;
  setProposedChanges: (p: ProposedChange | null) => void;
  setPermissionMode: (m: string) => void;
}

export const useIdeStore = create<IdeState>((set, get) => ({
  projectId: null,
  conversations: [],
  activeConversation: null,
  chat: { messages: [], streaming: false, statusLine: "", statusEmoji: "" },
  fileTree: [],
  openFiles: [],
  activeFile: null,
  view: "files",
  agents: [],
  tasks: [],
  runs: [],
  gitStatus: null,
  checkpoints: [],
  terminalLines: [],
  testResults: [],
  approvals: [],
  proposedChanges: null,
  permissionMode: "ask",

  setProject: (id) => set({ projectId: id }),
  setView: (v) => set({ view: v }),
  setConversations: (c) => set({ conversations: c }),
  setActiveConversation: (id) => set({ activeConversation: id }),
  appendMessage: (m) =>
    set((s) => ({ chat: { ...s.chat, messages: [...s.chat.messages, m] } })),
  setMessages: (m) => set((s) => ({ chat: { ...s.chat, messages: m } })),
  setStreaming: (v) => set((s) => ({ chat: { ...s.chat, streaming: v } })),
  setStatus: (line, emoji = "") =>
    set((s) => ({ chat: { ...s.chat, statusLine: line, statusEmoji: emoji } })),
  setFileTree: (t) => set({ fileTree: t }),
  openFile: (path, content) =>
    set((s) => {
      if (!s.openFiles.some((f) => f.path === path)) {
        return { openFiles: [...s.openFiles, { path, content, dirty: false }], activeFile: path };
      }
      return {
        openFiles: s.openFiles.map((f) => (f.path === path ? { ...f, content } : f)),
        activeFile: path,
      };
    }),
  setActiveFile: (path) => set({ activeFile: path }),
  updateFileContent: (path, content) =>
    set((s) => ({
      openFiles: s.openFiles.map((f) =>
        f.path === path ? { ...f, content, dirty: true } : f
      ),
    })),
  closeFile: (path) =>
    set((s) => {
      const remaining = s.openFiles.filter((f) => f.path !== path);
      const activeFile =
        s.activeFile === path ? remaining[remaining.length - 1]?.path || null : s.activeFile;
      return { openFiles: remaining, activeFile };
    }),
  setAgents: (a) => set({ agents: a }),
  setTasks: (t) => set({ tasks: t }),
  updateTask: (t) =>
    set((s) => ({ tasks: s.tasks.map((x) => (x.id === t.id ? t : x)) })),
  setRuns: (r) => set({ runs: r }),
  setGitStatus: (g) => set({ gitStatus: g }),
  setCheckpoints: (c) => set({ checkpoints: c }),
  addTerminalLines: (lines) =>
    set((s) => ({ terminalLines: [...s.terminalLines, ...lines].slice(-2000) })),
  clearTerminal: () => set({ terminalLines: [] }),
  setTestResults: (t) => set({ testResults: t }),
  addTestResult: (t) =>
    set((s) => ({
      testResults: [t, ...s.testResults.filter((x) => x.test_run_id !== t.test_run_id)].slice(0, 50),
    })),
  addApproval: (a) => set((s) => ({ approvals: [...s.approvals.filter((x) => x.approval_id !== a.approval_id), a] })),
  removeApproval: (id) => set((s) => ({ approvals: s.approvals.filter((a) => a.approval_id !== id) })),
  setProposedChanges: (p) => set({ proposedChanges: p }),
  setPermissionMode: (m) => set({ permissionMode: m }),
}));
