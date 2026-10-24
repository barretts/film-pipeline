import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { pathToFileURL } from "node:url";

// Offline end-to-end regression test for .omp/hooks/post/unsloth-log.ts, run under
// Bun (OMP's runtime) against a throwaway temp log (FILM_LOG_DIR). Never touches the
// real truth log. Run: `bun logs/tasks/p1t03_hooktest.ts`.
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

const secret = { api_key: "sk-unsloth-XYZ123", note: "café × “q”" };

// 1) success: tool/server parse, redaction, UTF-8, ok=true, pre->post duration
await fire("tool_call", { toolName: "mcp__unsloth_studio__studio_status", input: secret }, 900);
await fire("tool_result", { toolName: "mcp__unsloth_studio__studio_status", input: secret, content: [{ type: "text", text: '{"gpu":"15.2/16.0"}' }], isError: false }, 900);
// 2) failure -> ok=false
await fire("tool_call", { toolName: "mcp__unsloth_studio__get_job", input: { job_id: "does-not-exist" } }, 700);
await fire("tool_result", { toolName: "mcp__unsloth_studio__get_job", input: { job_id: "does-not-exist" }, content: [{ type: "text", text: "job not found" }], isError: true }, 900);
// 3) non-unsloth -> ignored
await fire("tool_call", { toolName: "bash", input: { command: "ls" } }, 250);
await fire("tool_result", { toolName: "bash", input: { command: "ls" }, content: [{ type: "text", text: "hi" }], isError: false }, 250);

const lines = readLines();
const all = lines.join("\n");
const results: string[] = [`LINE_COUNT=${lines.length} (expect 2)`];
lines.forEach((l, i) => results.push(`LINE${i + 1} ${l}`));
const a = (name: string, ok: boolean): void => { results.push((ok ? "OK  " : "FAIL ") + name); };
a("count=2", lines.length === 2);
a("tool=studio_status", /"tool": *"studio_status"/.test(all));
a("server=unsloth_studio", /"server": *"unsloth_studio"/.test(all));
a("api_key redacted", /"api_key": *"<redacted>"/.test(all));
a("no raw secret in log", !/sk-unsloth-XYZ123/.test(all));
a("utf8 note intact", all.includes("café × “q”"));
a("studio_status ok=true", /"tool": *"studio_status"/.test(lines[0] ?? "") && /"ok": *true/.test(lines[0] ?? ""));
a("get_job ok=false", /"tool": *"get_job"/.test(lines[1] ?? "") && /"ok": *false/.test(lines[1] ?? ""));
a("duration_s present", /"duration_s": *[0-9]/.test(lines[0] ?? ""));
console.log(results.join("\n"));
