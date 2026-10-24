# P1-T02 · Turn on MCP and connect Codex

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| HUMAN + AGENT | P1-T01 | none | 15 min | — |

**Goal:** Codex reaches the local Studio MCP server using a key stored only in the Windows User environment.

## Steps
1. **AGENT:** once P1-T01 is confirmed DONE, start `logs/tasks/P1-T02.md` and give the human these steps.
2. **[HUMAN]** In Studio → Settings → API, create a key and enable **MCP access**.
3. **[HUMAN · your Windows PowerShell]** Outside the agent sandbox, store the key without placing it in shell history. Paste at the hidden prompt:
   ```powershell
   $s = Read-Host 'Paste Unsloth API key' -AsSecureString
   $b = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($s)
   try {
       $k = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($b)
       [Environment]::SetEnvironmentVariable('UNSLOTH_API_KEY', $k, 'User')
   } finally {
       [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($b)
       Remove-Variable s, b, k -ErrorAction SilentlyContinue
   }
   ```
   **Never paste the key into chat, Codex, or a file.**
4. **[HUMAN · new PowerShell window]** Run:
   ```powershell
   unsloth mcp add codex
   $env:UNSLOTH_STUDIO_URL = 'http://127.0.0.1:8888'
   unsloth doctor --mcp
   ```
   The MCP entry refers to `${UNSLOTH_API_KEY}`; the key itself must stay out of `config.toml`. `doctor` should report the API key accepted, MCP enabled, and verdict OK.
5. **[HUMAN]** Restart Codex so it reads the new MCP config and user environment. Confirm that the Unsloth server appears connected, then say **“continue”**.
6. **[AGENT]** Call `studio_status` once. Record the MCP server name and summarized free GPU memory in the TOOLS.md header; do not paste the full response.

## Outputs
- A working Codex MCP connection; the TOOLS.md header filled in.

## Done when
- [ ] `unsloth doctor --mcp` gives Verdict OK.
- [ ] Codex shows the Unsloth server as connected.
- [ ] `studio_status` returns data.

## If it fails
- **doctor says “turned off”:** enable MCP access in Studio → Settings → API.
- **doctor says “set, refused”:** create a new key, repeat step 3, and open a fresh terminal.
- **`unsloth mcp add codex` fails:** inspect `unsloth mcp add --help`; use `unsloth mcp add codex --dry-run` to preview the target config without writing. Do not hand-write a literal key into config.
- **The key appears anywhere** (chat, file, log, or screen share): rotate it in Studio → Settings → API and repeat step 3.

## STATUS line
`P1-T02 DONE · Codex connected, doctor OK, studio_status verified`
