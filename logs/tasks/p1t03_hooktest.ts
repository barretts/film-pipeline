import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { pathToFileURL } from "node:url";

// Offline end-to-end regression for .omp/hooks/post/unsloth-log.ts (FIFO pre/post hook),
// run under Bun (OMP's runtime) against a THROWAWAY temp log via FILM_LOG_DIR. Never
// touches the real truth log. Run: `bun logs/tasks/p1t03_hooktest.ts`.
//
// Fires the surface a STANDARD OMP CLI session produces: MCP tools are AgentTools named
// `mcp__<server>__<tool>` = `mcp__unsloth-studio__<tool>` (pi docs; hook PREFIX
// "mcp__unsloth" matches hyphen OR underscore). pi's tool_result carries `input`, so the
// same input is sent on both events (that is how args get captured). A bash call is ignored.
type HookHandler = (event: unknown) => void;
type RegisterHook = (event: string, handler: HookHandler) => void;
type HookFactory = (pi: { on: RegisterHook }) => void;

const T = fs.mkdtempSync(path.join(os.tmpdir(), "hookrun-"));
fs.mkdirSync(path.join(T, "logs"));
process.env.FILM_LOG_DIR = T; // hook + log_mcp.py write <T>/logs/

const hookPath = pathToFileURL(path.resolve("F:/film-pipeline/.omp/hooks/post/unsloth-log.ts")).href;
const mod: { default: unknown } = await import(hookPath);
const factory = mod.default as HookFactory;

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

// 1) studio_status ok=true (secret + non-ASCII in input → prove redaction + UTF-8 + args)
const stName = "mcp__unsloth-studio__studio_status";
const stIn = { api_key: "sk-unsloth-XYZ123", note: "café × “q”" };
await fire("tool_call", { toolName: stName, toolCallId: "id1", input: stIn }, 900);
await fire("tool_result", { toolName: stName, toolCallId: "id1", input: stIn, content: [{ type: "text", text: '{"gpu":"15.2/16.0"}' }], isError: false }, 900);
// 2) get_job ok=false (isError) — proves fail path + a SECOND distinct pending id (FIFO)
const gjName = "mcp__unsloth-studio__get_job";
const gjIn = { job_id: "does-not-exist" };
await fire("tool_call", { toolName: gjName, toolCallId: "id2", input: gjIn }, 700);
await fire("tool_result", { toolName: gjName, toolCallId: "id2", input: gjIn, content: [{ type: "text", text: "job not found" }], isError: true }, 900);
// 3) list_models ok=true
const lmName = "mcp__unsloth-studio__list_models";
await fire("tool_call", { toolName: lmName, toolCallId: "id3", input: {} }, 700);
await fire("tool_result", { toolName: lmName, toolCallId: "id3", input: {}, content: [{ type: "text", text: '{"models":[]}' }], isError: false }, 900);
// 4) MUST be ignored: plain bash
await fire("tool_call", { toolName: "bash", toolCallId: "b1", input: { command: "ls" } }, 250);
await fire("tool_result", { toolName: "bash", toolCallId: "b1", input: {}, content: [{ type: "text", text: "hi" }], isError: false }, 250);

const lines = readLines();
const all = lines.join("\n");
const lineFor = (tool: string): string => lines.find((l) => l.includes(`"tool": "${tool}"`)) ?? "";
const a = (name: string, ok: boolean): string => (ok ? "OK  " : "FAIL ") + name;
const out = [`LINE_COUNT=${lines.length} (expect 3)`, ...lines];
out.push(a("count=3 (bash ignored)", lines.length === 3));
out.push(a("server=unsloth-studio parsed", /"server": "unsloth-studio"/.test(all)));
out.push(a("tool short names (studio_status/get_job/list_models)", /"tool": "studio_status"/.test(all) && /"tool": "get_job"/.test(all) && /"tool": "list_models"/.test(all)));
out.push(a("api_key redacted in args", /"api_key": *"<redacted>"/.test(lineFor("studio_status"))));
out.push(a("job_id captured in args", /"job_id": *"does-not-exist"/.test(lineFor("get_job"))));
out.push(a("no raw secret anywhere", !/sk-unsloth-XYZ123/.test(all)));
out.push(a("utf8 note intact in args", lineFor("studio_status").includes("café × “q”")));
out.push(a("studio_status ok=true", /"ok": *true/.test(lineFor("studio_status"))));
out.push(a("get_job ok=false", /"ok": *false/.test(lineFor("get_job"))));
out.push(a("duration_s numeric on all 3", lines.length === 3 && lines.every((l) => /"duration_s": *[0-9]/.test(l))));
out.push(a("3 distinct FIFO pending ids", new Set(lines.map((l) => /"tool_use_id": *"([^"]+)"/.exec(l)?.[1])).size === 3));
console.log(out.join("\n"));
