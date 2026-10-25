import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
import { spawn } from "node:child_process";

// Passive OMP hook: audit-log every Unsloth Studio MCP call through the vetted,
// stdlib-only redactor tools/log_mcp.py (never stores secrets). Handlers return
// nothing (no block/override) and the Python write is fire-and-forget, so a tool
// call is never slowed or altered. Project-scoped: discovered at
// <cwd>/.omp/hooks/post/*.ts, so launch OMP from F:/film-pipeline.
//
// HOW MCP CALLS SURFACE (verified against a live session's get_state.dumpTools):
// there is NO native `mcp__unsloth_studio__<tool>` tool. An MCP call is made by the
// model through one of:
//   (A) the `write` tool to an xd:// MCP device, e.g. path "xd://mcp__unsloth_studio_studio_status";
//   (B) an `mcp` dispatcher tool whose input names the server + tool;
//   (C) a directly namespaced tool name (older builds) that starts with "mcp__unsloth".
// A plain file write or a non-Studio call must NEVER be logged. The filter below
// covers all three and rejects everything else.
//
// Paths default to production but are env-overridable so an offline test can point
// the log at a throwaway dir (FILM_LOG_DIR) without ever touching the truth log.
const SCRIPT = process.env.FILM_LOG_SCRIPT || "F:/film-pipeline/tools/log_mcp.py";
const PY = process.env.FILM_PY || "py";
const LOG_DIR = process.env.FILM_LOG_DIR || "F:/film-pipeline"; // log_mcp writes <LOG_DIR>/logs/

type UnknownRecord = Record<string, unknown>;
function asRecord(value: unknown): UnknownRecord {
  return typeof value === "object" && value !== null ? (value as UnknownRecord) : {};
}
function asString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

// Resolve an Unsloth Studio tool from an event, or return "" when the call is not a
// Studio MCP call (plain file writes, other servers/tools, non-mcp tools).
function studioToolFromEvent(toolName: string, input: unknown): string {
  const rec = asRecord(input);
  // (C) native namespaced tool name: mcp__unsloth[_-]studio[__]<tool>
  if (/^mcp__unsloth[_-]studio/i.test(toolName)) return toolName.replace(/^mcp__unsloth[_-]studio[_-]*/i, "");
  // (A) `write`/`read` to an xd:// (or mcp://) Studio device path
  if (toolName === "write" || toolName === "read" || toolName === "edit") {
    return studioToolFromPath(asString(rec.path));
  }
  // (B) `mcp` dispatcher: server names unsloth + a tool field
  if (/^mcp$/i.test(toolName)) {
    const server = (asString(rec.server) || asString(rec.serverName) || asString(rec.name)).toLowerCase();
    if (server.includes("unsloth")) {
      return asString(rec.tool) || asString(rec.toolName) || asString(rec.method) || "unknown";
    }
  }
  // any input carrying an unsloth device path
  const fromPath = studioToolFromPath(asString(rec.path) || asString(rec.uri) || asString(rec.url));
  return fromPath;
}
function studioToolFromPath(path: string): string {
  if (!path) return "";
  const m = /^(?:xd:\/\/mcp__|mcp:\/\/)unsloth[_-]studio[_/]+(.+)$/i.exec(path);
  if (!m) return "";
  return m[1] ?? "";
}

// Correlate pre<->post by tool name in call order. MCP Studio calls are strictly
// sequential, so a FIFO queue per tool name yields a stable synthetic id shared by
// the matching pre and post (log_mcp.py derives duration_s from it). Avoids relying
// on a toolCallId that is documented on tool_result but not guaranteed on tool_call.
let counter = 0;
const pending = new Map<string, string[]>();
function nextId(studioTool: string): string {
  const q = pending.get(studioTool) ?? [];
  const id = `mcp__unsloth_studio__${studioTool}#${++counter}`;
  q.push(id);
  pending.set(studioTool, q);
  return id;
}
function matchId(studioTool: string): string {
  const q = pending.get(studioTool);
  if (q && q.length > 0) return q.shift() as string;
  return `mcp__unsloth_studio__${studioTool}#orphan-${++counter}`; // unmatched result (shouldn't happen); still log
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

// Log the MCP args minus the harness routing wrapper (path) so the record is clean.
function cleanArgs(input: unknown): unknown {
  const rec = asRecord(input);
  const out: UnknownRecord = {};
  for (const [k, v] of Object.entries(rec)) {
    if (k === "path" || k === "server" || k === "serverName") continue;
    out[k] = v;
  }
  return out;
}

export default function (pi: ExtensionAPI): void {
  pi.on("tool_call", (event: { toolName?: string; input?: unknown }) => {
    const tool = studioToolFromEvent(asString(event?.toolName), event?.input);
    if (!tool) return;
    fire("pre", {
      tool_name: `mcp__unsloth_studio__${tool}`,
      tool_use_id: nextId(tool),
      cwd: LOG_DIR,
      tool_input: cleanArgs(event?.input),
    });
  });

  pi.on("tool_result", (event: { toolName?: string; input?: unknown; content?: unknown; isError?: boolean }) => {
    const tool = studioToolFromEvent(asString(event?.toolName), event?.input);
    if (!tool) return;
    fire(event.isError ? "fail" : "post", {
      tool_name: `mcp__unsloth_studio__${tool}`,
      tool_use_id: matchId(tool),
      cwd: LOG_DIR,
      tool_input: cleanArgs(event?.input),
      tool_response: event.content ?? null,
    });
  });
}
