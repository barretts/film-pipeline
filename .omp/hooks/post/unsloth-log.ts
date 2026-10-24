import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
import { spawn } from "node:child_process";

// Passive OMP hook: audit-log every Unsloth Studio MCP call through the vetted,
// stdlib-only redactor tools/log_mcp.py (never stores secrets). Handlers return
// nothing (no block/override) and the Python write is fire-and-forget, so a tool
// call is never slowed or altered. Project-scoped: discovered at
// <cwd>/.omp/hooks/post/*.ts, so launch OMP from F:/film-pipeline.
//
// Paths default to production but are env-overridable so an offline test can point
// the log at a throwaway dir (FILM_LOG_DIR) without ever touching the truth log.
const SCRIPT = process.env.FILM_LOG_SCRIPT || "F:/film-pipeline/tools/log_mcp.py";
const PY = process.env.FILM_PY || "py";
const LOG_DIR = process.env.FILM_LOG_DIR || "F:/film-pipeline"; // log_mcp writes <LOG_DIR>/logs/
// Broad prefix (same as log_mcp.py SERVER_PREFIX): tolerant of hyphen/underscore in
// the namespaced tool name (mcp__unsloth-studio__ / mcp__unsloth_studio__).
const PREFIX = "mcp__unsloth";

// Correlate pre<->post by tool name in call order. MCP Studio calls are strictly
// sequential, so a FIFO queue per tool name yields a stable synthetic id shared by
// the matching pre and post (log_mcp.py derives duration_s from it). Avoids relying
// on a toolCallId that is documented on tool_result but not guaranteed on tool_call.
let counter = 0;
const pending = new Map<string, string[]>();
function nextId(toolName: string): string {
  const q = pending.get(toolName) ?? [];
  const id = `${toolName}#${++counter}`;
  q.push(id);
  pending.set(toolName, q);
  return id;
}
function matchId(toolName: string): string {
  const q = pending.get(toolName);
  if (q && q.length > 0) return q.shift() as string;
  return `${toolName}#orphan-${++counter}`; // unmatched result (shouldn't happen); still log
}

function fire(mode: string, payload: unknown): void {
  try {
    const child = spawn(PY, ["-3", SCRIPT, mode], {
      cwd: LOG_DIR,
      env: { ...process.env, CLAUDE_PROJECT_DIR: LOG_DIR },
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
  pi.on("tool_call", (event: { toolName: string; input?: unknown }) => {
    if (typeof event?.toolName !== "string" || !event.toolName.startsWith(PREFIX)) return;
    fire("pre", {
      tool_name: event.toolName,
      tool_use_id: nextId(event.toolName),
      cwd: LOG_DIR,
      tool_input: event.input ?? {},
    });
  });

  pi.on(
    "tool_result",
    (event: { toolName: string; input?: unknown; content?: unknown; isError?: boolean }) => {
      if (typeof event?.toolName !== "string" || !event.toolName.startsWith(PREFIX)) return;
      fire(event.isError ? "fail" : "post", {
        tool_name: event.toolName,
        tool_use_id: matchId(event.toolName),
        cwd: LOG_DIR,
        tool_input: event.input ?? {},
        tool_response: event.content ?? null,
      });
    },
  );
}
