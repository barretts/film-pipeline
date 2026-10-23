# STATUS

**Current task:** P1-T02 (gated on P1-T01 human steps: start Studio, owner account, and Resources settings)
**Project root (from `pwd -W`, forward slashes):** F:/film-pipeline (canonical; original download at C:/code/local-agent-mode-sessions/outputs/film-pipeline)
**Model drive (HF_HOME):** F:\hf

Statuses: TODO · DOING · DONE · BLOCKED · SKIPPED. Keep results ≤ 15 words; details go to `logs/tasks/<ID>.md`.
Rows are in working order. Always take the first TODO row whose Needs are DONE or SKIPPED.

| ID | Task | Who | Needs | Status | Result |
|---|---|---|---|---|---|
| P0-T01 | Hardware check | HUMAN | — | DONE | 16GB RTX 4060 Ti, 128GB RAM, F: NVMe 497GB free, all tools present |
| P0-T02 | Install prerequisites | HUMAN | P0-T01 | DONE | all tools present; node v24, python 3.13, claude signed-in; unsloth MCP via `start claude` |
| P0-T03 | Windows settings + model drive | HUMAN | P0-T02 | DONE | HF_HOME=F:\hf, AC sleep off, long paths+pagefile ok, Dev Mode on; no [FIX] |
| P0-T04 | Project folder, venv, git | AGENT | P0-T03 | DONE | venv(py3.13)+libs ok; folders + git scaffold 707a614 at F:\film-pipeline |
| P1-T01 | Install and start Unsloth Studio | HUMAN | P0-T04 | BLOCKED | VRAM 995/16380 MiB; Studio down; awaiting human setup |
| P1-T02 | Turn on MCP, connect Claude Code | HUMAN+AGENT | P1-T01 | TODO | |
| P1-T03 | MCP logging hook | AGENT | P1-T02 | TODO | |
| P1-T04 | VRAM sampler + MCP report | AGENT | P1-T03 | TODO | |
| P1-T05 | Discover MCP tools → TOOLS.md | AGENT | P1-T03 | TODO | |
| P1-T06 | Map models to catalog → MODELS.md | AGENT | P1-T05 | TODO | |
| P1-T07 | HyperFrames + folder scaffold | AGENT | P0-T04 | DONE | render+render_preview OK; starter MP4 ffprobe-verified; RENDER_CMD in TOOLS.md |
| P1-T08 | Contact-sheet tool | AGENT | P0-T04 | DONE | contact_sheet.py: images+video frames, ≤1600px; 17→exit2; 5-tile test ok |
| P2-T01 | Writer: Qwen3.8-27B | AGENT | P1-T04, P1-T06 | TODO | |
| P2-T02 | Stills: Qwen-Image-2.1-Turbo | AGENT | P1-T04, P1-T06 | TODO | |
| P2-T03 | Character consistency (reference) | AGENT | P2-T02, P1-T08 | TODO | |
| P2-T04 | Motion video: Wan2.2-TI2V-5B | AGENT | P2-T02 | TODO | |
| P2-T05 | Hero video: Wan2.2-I2V-A14B | AGENT | P2-T03, P2-T04 | TODO | |
| P2-T06 | Talking video: LTX-2.5 native audio | AGENT | P2-T02 | TODO | |
| P2-T07 | Separation: HTDemucs | AGENT | P2-T06 | TODO | |
| P2-T08 | Transcription: MOSS | AGENT | P2-T07 | TODO | |
| P2-T09 | Voice: Breeze-TTS-2 | AGENT | P2-T08 | TODO | |
| P2-T10 | Audio-driven talking test (optional) | AGENT | P2-T09 | TODO | |
| P2-T11 | Music: YuE 2 | AGENT | P1-T04, P1-T06 | TODO | |
| P2-T12 | SFX: MiDashengLM-Gen | AGENT | P1-T04, P1-T06 | TODO | |
| P2-T13 | Fine-tune: Qwen3-0.6B → GGUF | AGENT | P1-T04, P1-T06 | TODO | |
| P2-T14 | Render: HyperFrames test | AGENT | P1-T07, P2-T04, P2-T11 | TODO | |
| P2-T15 | ✋ Stack review | HUMAN | P2-T01…P2-T14 | TODO | |
| P3-T01 | Schemas, validator, manifests | AGENT | P2-T15 | TODO | |
| P3-T02 | QA gate: qa_take.py | AGENT | P3-T01 | TODO | |
| P3-T03 | Facts + truth check: facts.py | AGENT | P3-T01 | TODO | |
| P3-T04 | Mixer: mix.py | AGENT | P3-T01 | TODO | |
| P3-T05 | Composition builder | AGENT | P3-T03 | TODO | |
| P3-T06 | Final mux + checks | AGENT | P3-T04, P3-T05 | TODO | |
| P4-T01 | Pilot script + shot list | AGENT | P3-T02, P3-T06 | TODO | |
| P4-T02 | Pilot assets | AGENT | P4-T01 | TODO | |
| P4-T03 | Pilot post | AGENT | P4-T02 | TODO | |
| P4-T04 | ✋ Calibrate + pilot review | HUMAN | P4-T03 | TODO | |
| P5-T01 | Feature list from logs | AGENT | P4-T04 | TODO | |
| P5-T02 | Production prompt (~2,500 words) | AGENT | P5-T01 | TODO | |
| P5-T03 | ✋ Script + shot list | AGENT | P5-T02 | TODO | |
| P5-T04 | ✋ Character master | AGENT | P5-T03 | TODO | |
| P5-T05 | ✋ Stills for every shot | AGENT | P5-T04 | TODO | |
| P6-T01 | ✋ Voice reference | AGENT | P5-T05 | TODO | |
| P6-T02 | Voice-over takes + QA | AGENT | P6-T01 | TODO | |
| P6-T03 | Talking shots | AGENT | P6-T02 | TODO | |
| P6-T04 | Motion shots + still shots | AGENT | P5-T05 | TODO | |
| P6-T07 | Music | AGENT | P5-T03 | TODO | |
| P6-T08 | SFX + drone | AGENT | P5-T03 | TODO | |
| P6-T09 | Fine-tune + loss curve | AGENT | P5-T03 | TODO | |
| P6-T05 | Hero shots (queue in the evening) | AGENT | P5-T05 | TODO | |
| P6-T06 | Video QA + reshoots | AGENT | P6-T03, P6-T04, P6-T05 | TODO | |
| P7-T01 | Captions | AGENT | P6-T02, P6-T06 | TODO | |
| P7-T02 | Edit decision list | AGENT | P7-T01, P6-T07, P6-T08, P6-T09 | TODO | |
| P7-T03 | Mix | AGENT | P7-T02 | TODO | |
| P7-T04 | Composition | AGENT | P7-T02 | TODO | |
| P7-T05 | Render + mux | AGENT | P7-T03, P7-T04 | TODO | |
| P7-T06 | ✋ Review + final report | HUMAN | P7-T05 | TODO | |

## Decisions
<!-- date · decision · by whom. Example: 2026-10-24 · writer quant UD-Q4_K_XL (9.8 tok/s) · human -->
- 2026-10-23 · model drive = F: (NVMe, 497 GB free ≥250; K:/G:/H: are HDDs, rejected) · agent
- 2026-10-23 · relocate package to F:/film-pipeline (short path) during P0-T04 · agent
- 2026-10-23 · run pipeline on Python 3.13 (`py -3`); venv pinned to 3.13 in P0-T04; no 2nd system python · agent
- 2026-10-23 · unsloth 2026.8.18 registers MCP via `unsloth start claude`, not `unsloth mcp add`; P1 uses that · agent
- 2026-10-23 · P0-T03 applied: HF_HOME=F:\hf (created F:\hf), AC sleep/hibernate→never (verified 0x0); Dev Mode pending human (§3.7) · agent
- 2026-10-23 · P0-T03 complete: human enabled Developer Mode; checker now clean (no [FIX], no long-path/pagefile/DevMode [NOTE]) · human+agent
- 2026-10-23 · canonical project root = F:/film-pipeline (relocated from C: original in P0-T04); all future work + commits target F: · agent
- 2026-10-23 · this MSYS bash can't exec the .venv python.exe stub by path; run venv python/pip via PowerShell `& 'F:\film-pipeline\.venv\Scripts\python.exe'` · agent
- 2026-10-23 · P1-T01: agent ran curl(:8888)=000 + Get-NetTCPConnection=none + nvidia-smi(compute apps). Root blocker = VRAM (15348/16380 MiB) held by GUI/Electron/game procs (strata.exe, Epic+overlay, msedge+webview2, Claude, VS Code, DWM), not a model. Studio NOT running. Do NOT start under VRAM pressure (no room to load models). Human: free VRAM, then `unsloth studio`, owner account, conservative Resources. Skipping `winget upgrade` (unsloth present; §3.7). Park P1-T01, advance agent tasks P1-T07/P1-T08 (needs=P0-T04). · agent
- 2026-10-23 · P1-T07: HyperFrames render default is 30fps; film pins 24fps (CONTEXT §5); canonical RENDER_CMD uses --quality delivery + frames-cache on F: (TOOLS.md) · agent
- 2026-10-23 · P1-T08: contact sheets are the visual-review path; run venv python via PowerShell; vision ?q= endpoint (127.0.0.1:8080) is down → verified labels via PIL stddev instead · agent
- 2026-10-23 · Resume check: local model stopped; VRAM 994/16380 MiB; Studio :8888 unavailable; human setup remains · agent
- 2026-10-23 · Follow-up check: VRAM 995/16380 MiB; Studio :8888 unavailable; awaiting human Studio setup · agent

## Key measurements
Per-model VRAM, time and production settings are in MODELS.md. Full-run time estimate after the pilot (P4-T04): _fill in_.

## Session log
<!-- one line per session: date · tasks touched · stopped at -->
2026-10-23 · P0-T01 · DONE; machine matches §2, tools present, model drive = F:
2026-10-23 · P0-T02 · DONE; git/node24/ffmpeg/claude/unsloth present; dev: py3.13 + mcp cmd rename
2026-10-23 · P0-T03 DOING · HF_HOME + no-sleep applied, long-paths/pagefile already OK, no [FIX]; needs human: Developer Mode On (or authorize documented skip)
2026-10-23 · P0-T03 · DONE; model cache→F:\hf, no-sleep, DevMode on; moving to P0-T04
2026-10-23 · P0-T04 · DONE; venv+libs on 3.13, folders, git scaffold 707a614 @ F:\film-pipeline — Phase 0 COMPLETE
2026-10-23 · P1-T07 · DONE; render+render_preview + starter MP4 verified + RENDER_CMD; skills at ~/.claude/skills/hyperframes. P1-T01 BLOCKED(human)
2026-10-23 · P1-T08 · DONE; contact_sheet.py (images+video frames, ≤1600px, 16-limit exit2). All non-Studio P1 tasks done → HALT at P1-T01 human gate
2026-10-23 · P1-T01 resumed · VRAM freed; endpoint checked; waiting for human to start Studio and set Resources
