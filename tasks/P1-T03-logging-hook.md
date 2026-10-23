# P1-T03 · MCP logging hook (the truth log)

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT (+ human review and restart) | P1-T02 | none | 20 min | — |

**Goal:** every Unsloth MCP call is appended automatically to `logs/mcp_calls.jsonl`, with full cleaned payloads in `logs/mcp_raw/`, and no secrets stored.

**Read first:** the docstring of `tools/log_mcp.py`; `templates/claude-settings.json`.

## Steps
1. **[HUMAN]** Review the two files. They run on every Unsloth MCP call. They only read the hook input and append to `logs/`; they make no network calls. Reply "approved". Any later change to either file needs a fresh ✋ approval (CONTEXT §3.7).
2. **Install the settings.**
   - If `.claude/settings.json` doesn't exist:
     ```bash
     mkdir -p .claude && cp templates/claude-settings.json .claude/settings.json
     ```
   - Otherwise, merge in the `env` and `hooks` keys and keep the existing entries.
3. **Check Python.** Run `py -3 --version`. If that fails, change `"command": "py"` to `"python"` in `.claude/settings.json` and remove the `"-3"` arguments.
4. **Offline test**, in a temp folder so the real log stays clean. It includes non-ASCII text and a fake key:
   ```bash
   mkdir -p /tmp/hooktest && printf '%s' '{"tool_name":"mcp__unsloth__selftest","tool_use_id":"t1","tool_input":{"api_key":"sk-unsloth-TEST","max_tokens":64,"note":"café × “q”"},"tool_response":{"ok":true}}' \
     | CLAUDE_PROJECT_DIR=/tmp/hooktest py -3 tools/log_mcp.py post && tail -n 1 /tmp/hooktest/logs/mcp_calls.jsonl
   ```
   Expect all of these in the output:
   - `"tool": "selftest"`
   - `"api_key": "<redacted>"`
   - `"max_tokens": 64`
   - the note decoded correctly
   - `"ok": true`
5. **Restart.** Write a handoff ("next: step 6"). Then ask the human **[HUMAN]** to exit Claude Code, start `claude` again, and run `/hooks`. Three hooks with matcher `mcp__unsloth.*` should be listed.
6. **Live test.** Call `studio_status`, then:
   ```bash
   tail -n 1 logs/mcp_calls.jsonl
   ```
   This is the one allowed direct read (CONTEXT §9). Expect `"tool": "studio_status"`, `"ok": true` and a numeric `duration_s`.
7. **Failure test.** Call `get_job` with id `does-not-exist`. The new line should have `"ok": false`.
8. **Secret check.** Scan only the logs the hook writes:
   ```bash
   grep -lE "sk-unsloth-[A-Za-z0-9]" logs/mcp_calls.jsonl logs/mcp_raw/* || echo "no keys in logs"
   ```

## Outputs
- `.claude/settings.json`
- `logs/mcp_calls.jsonl` with ≥ 2 real lines
- `logs/mcp_raw/`

## Done when
- [ ] The offline test passed: key redacted, `max_tokens` kept, non-ASCII intact.
- [ ] The live success line and the live failure line were both logged correctly.
- [ ] The secret check prints "no keys in logs".
- [ ] `logs/hook_errors.log` is absent or empty. **Check it at the start of every later session.**

## If it fails
- **No lines appear:** check `/hooks`, read `logs/hook_errors.log`, and run the exact hook command from the settings by hand.
- **The server name doesn't start with `unsloth`:** change the matcher in `.claude/settings.json` **and** `SERVER_PREFIX` in `tools/log_mcp.py` to `mcp__<name>`. This is a ✋ change.
- **Long calls abort after ~5 min of silence:** the `env` block raises the idle timeout. If your Claude Code version ignores it, poll instead of using wait options.

## STATUS line
`P1-T03 DONE · hook logs ok/fail calls; secrets redacted; UTF-8 ok` (example)
