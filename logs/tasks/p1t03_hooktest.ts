import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { pathToFileURL } from "node:url";

// Offline end-to-end regression test for .omp/hooks/post/unsloth-log.ts, run under
// Bun (OMP's runtime) against a throwaway temp log (FILM_LOG_DIR). Never touches the
// real truth log. Run: `bun logs/tasks/p1t03_hooktest.ts`.
//
// Fires the REAL surfaces MCP calls take (verified via get_state.dumpTools): the
// `write`->xd://mcp__unsloth_studio__<tool> device path, a native namespaced name,
// and the `mcp` dispatcher — plus a plain file write and a non-Studio call that MUST
// be ignored.
type HookHandler = (event: unknown) => void;
type RegisterHook = (event: string, handler: HookHandler) => void;
type HookFactory = (pi: { on: RegisterHook }) => void;

const T = fs.mkdtempSync(path.join(os.tmpdir(), "hookrun-"));
fs.mkdirSync(path.join(T, "logs"));
process.env.FILM_LOG_DIR = T;
process.env.FILM_LOG_SCRIPT = "F:/film-pipeline/tools/log_mcp.py";

// Dynamic import: the hook is a runtime-discovered OMP module (plugin-loading
// boundary), so a static import cannot work here.
const hookPath = pathToFileURL(path.resolve("F:/film-pipeline/.omp/hooks/post/unsloth-log.ts")).href;
const mod: { default: unknown } = await import(hookPath);
const factory = mod.default as HookFactory; // module entry factory; shape known from OMP contract

const H = new Map<string, HookHandler>();
factory({ on: (event, handler) => { H.set(event, handler); } });

const sleep = (ms: number): Promise<void> => {
  const { promise, resolve } = Promise.withResolvers<void>();
  setTimeout(resolve, ms);
  return promise;
};
const readLines = (): string[] => {
  const p = path.join(T, "logs", "mcp_calls.jsonl");
  return fs.existsSync(p) ? fs.readFileSync(p, "utf8").split("\n").filter(Boolean) : [];
};
const fire = async (event: string, payload: unknown, delayMs: number): Promise<void> => {
  H.get(event)?.(payload);
  await sleep(delayMs);
};

// 1) PRIMARY harness path: write to xd://mcp__ device, with a secret + UTF-8 to prove
//    redaction + UTF-8 round-trip + ok=true + pre->post duration correlation.
const devInput = { path: "xd://mcp__unsloth_studio_studio_status", content: '{"api_key":"sk-unsloth-XYZ123","note":"café × “q”"}' };
await fire("tool_call", { toolName: "write", input: devInput }, 900);
await fire("tool_result", { toolName: "write", input: devInput, content: [{ type: "text", text: '{"gpu":"15.2/16.0"}' }], isError: false }, 900);
// 2) failure via device -> ok=false
const devJob = { path: "xd://mcp__unsloth_studio_get_job", content: '{"id":"does-not-exist"}' };
await fire("tool_call", { toolName: "write", input: devJob }, 700);
await fire("tool_result", { toolName: "write", input: devJob, content: [{ type: "text", text: "job not found" }], isError: true }, 900);
// 3) native namespaced name (older-build surface) still captured
await fire("tool_call", { toolName: "mcp__unsloth_studio__list_models", input: {} }, 700);
await fire("tool_result", { toolName: "mcp__unsloth_studio__list_models", input: {}, content: [{ type: "text", text: '{"models":[]}' }], isError: false }, 900);
// 4) `mcp` dispatcher -> captured with tool from input.tool
await fire("tool_call", { toolName: "mcp", input: { server: "unsloth-studio", tool: "get_job", args: { job_id: "x" } } }, 700);
await fire("tool_result", { toolName: "mcp", input: { server: "unsloth-studio", tool: "get_job", args: { job_id: "x" } }, content: [{ type: "text", text: "ok" }], isError: false }, 900);
// 5) MUST be ignored: a plain file write, a non-Studio MCP call, and a plain bash
await fire("tool_call", { toolName: "write", input: { path: "F:/film-pipeline/notes.md", content: "hi" } }, 250);
await fire("tool_result", { toolName: "write", input: { path: "F:/film-pipeline/notes.md", content: "hi" }, content: [{ type: "text", text: "wrote" }], isError: false }, 250);
await fire("tool_call", { toolName: "mcp", input: { server: "other", tool: "x" } }, 200);
await fire("tool_result", { toolName: "mcp", input: { server: "other", tool: "x" }, content: [{ type: "text", text: "no" }], isError: false }, 200);
await fire("tool_call", { toolName: "bash", input: { command: "ls" } }, 200);
await fire("tool_result", { toolName: "bash", input: { command: "ls" }, content: [{ type: "text", text: "hi" }], isError: false }, 250);

const lines = readLines();
const all = lines.join("\n");
const results: string[] = [`LINE_COUNT=${lines.length} (expect 4)`];
lines.forEach((l, i) => results.push(`LINE${i + 1} ${l}`));
const a = (name: string, ok: boolean): void => { results.push((ok ? "OK  " : "FAIL ") + name); };
const lineFor = (tool: string): string => lines.find((l) => l.includes(`"tool": "${tool}"`)) ?? "";
a("count=4 (ignores file/other/bash)", lines.length === 4);
a("device write->studio_status tool parsed", /"tool": "studio_status"/.test(all));
a("api_key redacted", /"api_key": *"<redacted>"/.test(all));
a("no raw secret in log", !/sk-unsloth-XYZ123/.test(all));
a("utf8 note intact", all.includes("café × “q”"));
a("studio_status ok=true", /"ok": *true/.test(lineFor("studio_status")));
a("get_job device ok=false", /"ok": *false/.test(lineFor("get_job")));
a("native name list_models captured", /"tool": "list_models"/.test(all));
a("mcp dispatcher get_job(2nd) captured", (lines.filter((l) => l.includes('"tool": "get_job"')).length) === 2);
a("duration_s present", /"duration_s": *[0-9]/.test(lineFor("studio_status")));
console.log(results.join("\n"));
