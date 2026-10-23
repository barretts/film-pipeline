# P1-T02 · Turn on MCP and connect Claude Code

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| HUMAN + AGENT | P1-T01 | none | 15 min | — |

**Goal:** Claude Code reaches Studio's MCP server with an API key that exists only in the user environment variable `UNSLOTH_API_KEY`.

## Steps
1. **AGENT:** write a handoff in `logs/tasks/P1-T02.md` that says "waiting for the human to finish steps 2–6 and restart Claude Code". Then give the human the steps below.
2. **[HUMAN]** In Studio › Settings › API, create an API key (`sk-unsloth-…`) and switch **MCP access on** (owner only). On older builds, start Studio with `UNSLOTH_STUDIO_ENABLE_MCP=1` instead.
3. **[HUMAN · PowerShell]** Store the key without leaving it in your PowerShell history. Paste the key at the hidden prompt:
   ```powershell
   $s = Read-Host 'Paste Unsloth API key' -AsSecureString
   $k = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s))
   [Environment]::SetEnvironmentVariable('UNSLOTH_API_KEY', $k, 'User'); Remove-Variable s, k
   ```
   **Never paste the key into Claude Code, chat or a file.**
4. **[HUMAN]** Open a **new** PowerShell window, because environment variables only reach new processes. Leave the **Studio window running**. Then run:
   ```powershell
   unsloth mcp add claude-code
   unsloth doctor --mcp
   ```
   - `mcp add` writes a user-scope entry that refers to `${UNSLOTH_API_KEY}`, not the key itself.
   - `doctor` should report: `API key: set, accepted` · `MCP endpoint: on` · `Verdict: OK`.
5. **[HUMAN]** Exit Claude Code and start it again **from a new terminal** in the project folder. Type `/mcp`; the Unsloth server should show as connected.
6. **[HUMAN]** Say "continue" to the agent.
7. **AGENT:** call `studio_status` once. In the TOOLS.md header, write the server name (the `<server>` in `mcp__<server>__…`) and the GPU's free memory, as a summary. Don't paste the response.

## Outputs
- A working MCP connection; the TOOLS.md header filled in.

## Done when
- [ ] `unsloth doctor --mcp` gives Verdict OK.
- [ ] `/mcp` shows the server as connected.
- [ ] `studio_status` returns data.

## If it fails
- **doctor says "turned off":** switch MCP access on in Settings › API.
- **doctor says "set, refused":** create a new key, repeat step 3, and open new terminals.
- **`mcp add` fails:** add the server by hand. The single quotes keep the variable unexpanded, so the key stays out of `~/.claude.json`:
  ```bash
  claude mcp add --transport http --scope user unsloth-studio http://127.0.0.1:8888/mcp/ --header 'Authorization: Bearer ${UNSLOTH_API_KEY}'
  ```
- **The key showed up anywhere** (chat, file, log, screen share): the human rotates it in Settings › API and repeats step 3.

## STATUS line
`P1-T02 DONE · server "unsloth-studio" connected, doctor OK` (example)
