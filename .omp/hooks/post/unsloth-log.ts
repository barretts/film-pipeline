import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
import { spawn } from "node:child_process";

// Passive OMP hook: log every Unsloth Studio MCP call through the vetted redactor
// tools/log_mcp.py (stdlib-only, never stores secrets). Never blocks or alters a
// tool call: handlers return nothing; the Python write is fire-and-forget.
const ROOT = "F:/film-pipeline";
const SCRIPT = "F:/film-pipeline/tools/log_mcp.py";
// Match the broad prefix (same as log_mcp.py SERVER_PREFIX) so hyphen vs underscore in
// the namespaced tool name (mcp__unsloth-studio__ / mcp__unsloth_studio__) is irrelevant.
const PREFIX = "mcp__unsloth";

function fire(mode: string, payload: unknown): void {
  try {
    const child = spawn("py", ["-3", SCRIPT, mode], {
      cwd: ROOT,
      env: { ...process.env, CLAUDE_PROJECT_DIR: ROOT },
      windowsHide: true,
      stdio: ["pipe", "ignore", "ignore"],
    });
    child.on("error", () => {}); // never break a tool call
    child.stdin.end(JSON.stringify(payload)); // UTF-8 bytes
  } catch {
    /* logging must be invisible to the agent */
  }
}

export default function (pi: ExtensionAPI): void {
  pi.on("tool_call", (event: { toolName: string; toolCallId: string; input?: unknown }) => {
    if (!event.toolName.startsWith(PREFIX)) return;
    fire("pre", {
      tool_name: event.toolName,
      tool_use_id: event.toolCallId,
      cwd: ROOT,
      tool_input: event.input ?? {},
    });
  });

  pi.on("tool_result", (event: { toolName: string; toolCallId: string; input?: unknown; content?: unknown; isError?: boolean }) => {
    if (!event.toolName.startsWith(PREFIX)) return;
    fire(event.isError ? "fail" : "post", {
      tool_name: event.toolName,
      tool_use_id: event.toolCallId,
      cwd: ROOT,
      tool_input: event.input ?? {},
      tool_response: event.content ?? null,
    });
  });
}
