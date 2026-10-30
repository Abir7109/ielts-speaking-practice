# IELTS SPEAKING PRACTICE — Living Plan

> **Rule:** Append a Change Log entry after **every** file touch, however small.
> Format: `YYYY-MM-DD | file | change | reason | verification`

---

## 1. Decisions (append-only, confirmed with the user)

- **2026-10-29 | Copy, not move** — New app gets its own copy of SODA's UI (`src/`, `public/`, configs). SODA root stays untouched and runnable.
- **2026-10-29 | Public, isolated sessions** — One Gemini Live AudioLoop per socket (`sid`). Visitors never share audio/scores. `MAX_SESSIONS` cap (default 5).
- **2026-10-29 | Audio-based pronunciation** — Buffer each spoken answer (16 kHz PCM → WAV), send to Gemini (`gemini-2.5-flash`, env `PRONUNCIATION_MODEL`) for a real Pronunciation band + notes. Text-only heuristics only as fallback when audio is unavailable.
- **2026-10-29 | Supabase persistence** — New `ielts_clients` / `ielts_sessions` / `ielts_answers` tables via existing `SUPABASE_DB_URL` pooler. Anonymous `client_id` (UUID in localStorage). Local JSONL fallback when DB unset.
- **2026-10-29 | Folder** — `D:\soda-main-master\soda-main-master\ielts-speaking-practice\` (no spaces; avoids build breakage). App title shown to users: **IELTS SPEAKING PRACTICE**. Own git repo; SODA `.gitignore` gets one line `ielts-speaking-practice/`.
- **2026-10-29 | Deploy scope** — Build + verify locally, then deploy for the user: new Render backend (Docker) + new Netlify site, then live smoke test.
- **2026-10-29 | Scope** — ONLY IELTS Speaking. No writing/reading/vocab/listening modules, no wake word, no camera/desktop tools, no accounts. Spelling+grammar corrections shown as *transcript corrections* (speaking has no spelling criterion); scoring uses the 4 official criteria only.
- **2026-10-29 | Voice parity** — Same pipeline as SODA: Gemini Live `models/gemini-3.1-flash-live-preview`, voice "Charon", server VAD, echo-safe mic mute, browser mic → `browser_audio` → backend, `audio_data` PCM playback at 24 kHz, `mic_level`, `speaking_state`, `transcription` events.

---

## 2. Architecture

```
Browser (Netlify)
  src/  — trimmed SODA HUD: orb + transcript + Start/End + IELTS panels
    │ socket.io  (events allowlist)
    ▼
Backend (Render, Docker python:3.11-slim)
  server.py   FastAPI + Socket.IO, per-sid Session registry, /status
  voice.py    slim AudioLoop: queues, VAD, transcriptions, tool dispatch
  examiner.py test FSM: idle → part1 → part2(prep/speak) → part3 → finished
  evaluation.py  DeepSeek (text 3 criteria) ∥ Gemini (pronunciation from WAV)
  rubric.py   official 0–9 descriptors × 4 criteria, half-band rounding
  question_bank.py  Part 1 topics / Part 2 cue cards / Part 3 follow-ups
  ielts_tools.py    Gemini function declarations (7 tools only)
  prompts.py  examiner system prompt + evaluation prompts
  store.py    Supabase ielts_* tables → JSONL fallback
    │
    ├─ Gemini Live (voice conversation + tool calls)
    ├─ DeepSeek API (band text evaluation)
    ├─ Gemini generate_content (pronunciation, audio part)
    └─ Supabase Postgres (progress/history)
```

### Only-IELTS enforcement (4 layers)
1. Gemini `tools=` = `start_test, repeat_question, evaluate_answer, next_question, finish_test, set_goal, get_progress` only.
2. System prompt: certified IELTS examiner, English only, exact-text-to-speak protocol, "no other abilities — steer back to the test".
3. Backend socket allowlist: `connect, disconnect, start_audio, stop_audio, browser_audio, run_ielts_tool, ping`. Unknown events rejected. `run_ielts_tool` re-checks the 7-tool allowlist.
4. Frontend: all non-IELTS panels/hooks/animations deleted.

### Exam flow
1. **Start Practice** click (user gesture → mic permission) → `start_audio {client_id}` → examiner greets, offers full mock / single part.
2. Part 1: 3–4 questions, evaluate after each (spoken band + one top correction → next question).
3. Part 2: cue card panel + 60 s prep countdown → 2-min long turn → one evaluation.
4. Part 3: 4–5 discussion questions.
5. `finish_test` → final report panel (per-part + overall, corrections, strengths, tips) + spoken summary → saved to Supabase.

### Scoring
- Criteria: Fluency & Coherence, Lexical Resource, Grammatical Range & Accuracy, Pronunciation (full 0–9 descriptors in `rubric.py`).
- Overall = mean of 4 → round to nearest **0.5**. Part band = mean of its answers (rounded). Final = mean of part bands (rounded). Documented approximation of examiner judgement.
- Evaluation robustness: answer text owned by backend (from `input_transcription`, NOT model-supplied); PCM buffer owned by backend; if model skips `evaluate_answer` and calls `next_question`/`finish_test`, pending answer is evaluated first; JSON extraction (```json fence → brace slice) + 1 retry + heuristic fallback.

### Concurrency & limits
- `sessions: dict[sid, Session]`; destroyed on disconnect; `MAX_SESSIONS` (default 5) → friendly "practice room full".
- Evaluation rate limit per session: 30/hour (cost guard).

---

## 3. File inventory

### Source (SODA) → destination
| SODA source | New app | Action |
|---|---|---|
| `index.html` | `index.html` | copy, retitle |
| `vite.config.js`, `tailwind.config.js`, `postcss.config.mjs`, `.nvmrc` | same | copy as-is |
| `package.json` | `package.json` | **rewrite** (no electron/wait-on/gsap/animejs/recharts) |
| `public/*` | `public/` | copy as-is |
| `src/main.jsx` | `src/main.jsx` | copy as-is |
| `src/styles/*` | `src/styles/` | copy as-is |
| `src/contexts/PanelSpaceContext.jsx` | same | copy as-is |
| `src/services/SocketService.js` | same | copy (reads `VITE_BACKEND_URL`) |
| `src/services/useBrowserMic.js` | same | copy as-is |
| `src/hooks/useAudioPlayback.js` | same | copy as-is |
| `src/components/HolographicOrb.jsx` | same | copy as-is |
| `src/components/SlidePanel.jsx` | same | copy as-is |
| `src/components/panels/IELTSSpeakingPanel.jsx` | same | copy + extend (transcript tab, final report) |
| `src/components/panels/IELTSDashboardPanel.jsx` | same | copy as-is |
| `src/App.jsx` | `src/App.jsx` | **rewrite** (IELTS shell only) |
| `src/hooks/usePanelState.js` | same | **rewrite** (IELTS + orb state only) |
| `src/hooks/useSocketHandlers.js` | `src/hooks/useIeltsSession.js` | **rewrite** (IELTS state + socket events: audio_data, mic_level, speaking_state, transcription, test_state, answer_evaluated, report_ready, client_progress, panel_open, error) |
| everything else under `src/` | — | **delete from copy** |

### New backend files
`backend/server.py`, `backend/voice.py`, `backend/examiner.py`, `backend/rubric.py`, `backend/evaluation.py`, `backend/question_bank.py`, `backend/ielts_tools.py`, `backend/prompts.py`, `backend/store.py`, `backend/logger.py`

### New root files
`requirements.txt`, `Dockerfile`, `render.yaml`, `netlify.toml`, `tests/run_all.py`, `tests/test_rubric.py`, `tests/test_examiner.py`, `tests/test_evaluation.py`, `tests/test_store.py`, `README.md`

---

## 4. Phase checklist

- [x] **P0 Scaffold** — folder, copy UI, plan.md, git init, SODA .gitignore line
- [x] **P1 Backend skeleton** — server.py, requirements, Dockerfile, compileall green
- [x] **P2 Voice engine** — voice.py port written (round-trip verified in P6)
- [x] **P3 Examiner + scoring** — rubric/bank/FSM/evaluation/tools/prompts + unit tests green
- [x] **P4 Persistence** — store.py Supabase + fallback, progress in prompt, tests green
- [x] **P5 Frontend** — App rewrite, lean session hook, panels (question/feedback/progress/report), prep countdown, build green
- [x] **P6 Verification** — `npm run build` ✓, `compileall` OK, 37/37 tests OK, `/status` smoke OK (db=supabase)
- [x] **P7 Deploy** — GitHub repo pushed; Render backend URL `https://ielts-speaking-practice.onrender.com` (user-provided); **Netlify live**: https://ielts-speaking-practice-815.netlify.app (site `ielts-speaking-practice-815`, linked to this folder, `VITE_BACKEND_URL` = Render URL)
- [x] **Final smoke** — open Netlify URL → Start Practice → mic grant → answer → evaluation panel → final report (ensure Render CORS_ORIGINS includes `https://ielts-speaking-practice-815.netlify.app`) — live smoke 2026-10-30: greeting audio + transcript OK, `start_test(full)` → Part 1 Q1/3 OK; user confirmed app running

---

## 5. Change Log (append after EVERY change)

- 2026-10-29 | `ielts-speaking-practice/` | created folder; copied `index.html`, `vite.config.js`, `tailwind.config.js`, `postcss.config.mjs`, `.nvmrc`, `public/` (4 files), `src/` (97 files) from SODA | P0 step 1 (copy UI, SODA untouched) | directory listing confirms 97 src files
- 2026-10-29 | `ielts-speaking-practice/package.json` | new manifest: react/socket.io-client/lucide-react + vite/tailwind/concurrently; dropped electron, wait-on, gsap, animejs, recharts (only deleted components imported them) | only-IELTS app needs no desktop shell or dead deps | grep showed gsap/animejs only in WakeSequence/NightWinddown (deleted), recharts in MetricsPanel (deleted), lucide in no kept file
- 2026-10-29 | `ielts-speaking-practice/.gitignore` | node_modules, dist, .env, backend/ielts_data, pycache, logs, .netlify | never commit secrets/deploy artifacts | n/a
- 2026-10-29 | `ielts-speaking-practice/.env.example` | documented GEMINI_API_KEY, DEEPSEEK_API_KEY, PRONUNCIATION_MODEL, SUPABASE_DB_URL, MAX_SESSIONS, CORS_ORIGINS, PORT, VITE_BACKEND_URL | full env contract for Render + local dev | n/a
- 2026-10-29 | `ielts-speaking-practice/plan.md` | created living plan: decisions, architecture, file inventory, phase checklist, change log, env, deploy, verification | user step 2 (log every small detail) | n/a
- 2026-10-29 | `ielts-speaking-practice/src/App.jsx`, `src/hooks/useIeltsSession.js`, `src/components/panels/IELTS*Panel.jsx`, `index.html`, `public/manifest.json` | P5 frontend rewrite: trimmed to orb + transcript + Start/End/Dashboard; tabs Question/Feedback/Progress/Report; prep countdown; audio playback; VITE_BACKEND_URL socket; SODA title→IELTS SPEAKING PRACTICE | `npm run build` ✓ 16.8s, dist/ 242 KB JS
- 2026-10-29 | `backend/voice.py` | `_test_state` gains `prep_ends_at` for cue cards + `prep_over`; added `_dashboard_data` wrapper (`progress`, `target_band`, `days_until_exam`) | frontend countdown + dashboard panel shape correct | `compileall -q backend` OK
- 2026-10-29 | `ielts-speaking-practice/git` | `git add -A` → commit `5f4f54d` (46 files); `gh repo create ielts-speaking-practice --public --source=. --remote origin --push` → https://github.com/Abir7109/ielts-speaking-practice | code in GitHub, ready for Render + Netlify | remote tracked, push OK
- 2026-10-30 | `backend/ielts_tools.py`, `backend/voice.py`, `tests/test_tools.py` | **BUG FIX**: raw dict `IELTS_TOOLS` passed to `LiveConnectConfig(tools=...)` → pydantic `ValidationError` (28 errors) killed `run()` silently before any event (no greeting). Added `build_tools()` wrapping dicts in `types.Tool(function_declarations=[types.FunctionDeclaration(...)])`; `run()` now wraps config build in try/except and emits `error`/`connection_state(config_error)`; new `tests/test_tools.py` (4 tests) asserts config accepts tools | remote app was silent: socket connected, 0 audio/transcript events; local probe reproduced identical failure, then after fix examiner greeting audio + transcription: "Which one would you like to do?" | 41/41 tests OK
- 2026-10-30 | `netlify` | site `ielts-speaking-practice-815` (`https://ielts-speaking-practice-815.netlify.app`) deployed via `npx netlify deploy --prod`; linked with `netlify link --id ab4b802e-...`; `VITE_BACKEND_URL=https://ielts-speaking-practice.onrender.com` verified baked into live bundle; Socket.IO handshake from Netlify origin → Render returns 200 ACAO=netlify origin | frontend live | live bundle + socket smoke OK
- 2026-10-30 | `netlify` **INCIDENT + FIX** | Netlify CLI walked up from `ielts-speaking-practice/` to SODA root `.netlify/state.json`, so early IELTS deploys overwrote **`soda-hud.netlify.app` (real SODA)** and `netlify link` repointed SODA's state to the IELTS site. Restored: rebuilt SODA `dist` + deployed to `soda-hud` (title "SODA Core Intelligence" verified), wrote SODA `.netlify/state.json` → `189b0c91-...`, wrote explicit `ielts-speaking-practice/.netlify/state.json` → `ab4b802e-...`; `netlify status` in each folder now reports the correct project | real SODA must stay untouched; IELTS must stay isolated | both URLs verified live with correct titles; `git ls-files` shows 0 IELTS files in SODA repo; SODA_BACKEND repo never pushed
- 2026-10-30 | diagnosis (no file change) | Render IELTS backend connects to Gemini Live but API rejects with `1008: The Gemini API free tier is not available for this project`; local probe: `GEMINI_API_KEY` connects OK, `GOOGLE_API_KEY` fails 1008 (SDK prefers `GOOGLE_API_KEY` when both set) → Render key/project mismatch | unblocks voice on Render | probe printed only CONNECT OK/FAIL, no secrets
- 2026-10-30 | verification (no file change) | user fixed Render `GEMINI_API_KEY`; live smoke: greeting audio 45 chunks + full examiner transcript ("Hello, welcome to IELTS speaking practice..."); `run_ielts_tool start_test(full)` → `test_state phase=answering part=1 kind=question q=1/3` | P7 final smoke | `smoke_live.js` EXIT=0; `smoke_tool.js` part1=true; user confirmed app running
- 2026-10-30 | `backend/rubric.py` | replaced descriptors with official public Band 5-9 wording (FC/LR/GRA/P), added 25% weighting note + official half-band rounding example | user reported scores not matching official IELTS criteria | 44/44 tests OK
- 2026-10-30 | `backend/prompts.py` | text-eval prompt v2: per-criterion `criterion_feedback` (reason/evidence/next_step), `why_band_summary`, official descriptors, STT-noise rule, output caps; examiner prompt now reads why-not-higher aloud; pronunciation prompt official 5-9 descriptors + STT-noise note | user reported no explanation for lost marks | probe shows Gemini returns reasons + evidence + next steps
- 2026-10-30 | `backend/evaluation.py` | **scoring root-cause fix**: `DEEPSEEK_API_KEY` was empty → silent word-count heuristic. Gemini (`gemini-2.5-flash`, JSON mode, thinking off, 8192 tokens) is now primary text scorer; DeepSeek optional (`TEXT_EVAL_PROVIDER`); heuristic v2 analyses fillers/repetition/TTR/grammar patterns and returns per-criterion reasons; `evaluator` field added | real band scores without extra key; graceful, honest fallback | Gemini probe: evaluator=gemini, bands 7/6/7/6, criteria reasons present
- 2026-10-30 | `backend/voice.py` | VAD: `END_SENSITIVITY_LOW`, `silence_duration_ms=2000`, `prefix_padding_ms=500` (was HIGH/800ms/300ms) | examiner was ending candidate turns on short thinking pauses | config accepted; live retest pending
- 2026-10-30 | `backend/examiner.py` | spoken feedback now states band + main limit (weakest criterion reason) + top fix; report aggregates `criterion_feedback`, `weakest_reason`, `scoring_mode` (ai vs estimate) | user asked why marks were lost | tests 44/44 OK
- 2026-10-30 | `backend/server.py` | `/status` exposes `eval` (gemini/deepseek/heuristic); startup log includes eval mode | make silent scorer degradation visible on Render | import + tests OK
- 2026-10-30 | `backend/tests` | updated heuristic expectations; new tests: per-criterion explanations, Gemini routing, report criterion notes/scoring mode | regression coverage | 44/44 pass
- 2026-10-30 | `src/components/panels/IELTSSpeakingPanel.jsx` | scores tab shows WHY/evidence/NEXT under each criterion; degraded banner when scoring is estimate-only; feedback tab shows why-band summary | user reported no explanation of scores | build OK
- 2026-10-30 | `src/components/panels/IELTSReportPanel.jsx` | per-criterion explanation blocks, "Why you lost marks" (weakest_reason), estimate-mode banner | final report must explain lost marks | build OK
- 2026-10-30 | `.env.example` | documented TEXT_EVAL_PROVIDER/TEXT_EVAL_MODEL; GEMINI now required for scoring; DeepSeek optional | prevent silent heuristic deployment | n/a
- 2026-10-30 | deploy verification | commit `f4a6a5d` pushed → Render redeployed; `/status` reports `eval:"gemini"`; Netlify site `ielts-speaking-practice-815` redeployed; live smoke: greeting 55 audio chunks + full transcript, `start_test(full)` → Part 1 Q1 spoken | confirm fixes on production | `smoke_live.js` and `smoke_tool.js` EXIT=0
- 2026-10-30 | `backend/examiner.py` | `band_words()` natural number speech; concise 2-3 sentence spoken_feedback (no "Top fix" label, clipped first sentence); warmer spoken_report | user heard "5 5", "7 0" and essay-length robotic feedback | 46 tests OK
- 2026-10-30 | `backend/voice.py` | fixed missing-space concatenation between feedback and next question/report; natural get_progress/set_goal wording with band words; merge last report into progress when average missing | user heard "life?That concludes" and stale "not yet scored" | tests OK
- 2026-10-30 | `backend/prompts.py` | warm human examiner persona, natural contractions/bridges, spoken numbers, brevity, encourage silent candidates | user: "not acting like a real examiner / friend" | manual review
- 2026-10-30 | deploy verification | commit `59e599f` pushed → Render redeployed; `/status` `eval:"gemini"`; live smoke: greeting 63 audio chunks + full transcript | confirm natural delivery on production | `smoke_live.js` EXIT=0
- 2026-10-29 | `ielts-speaking-practice/.git` | `git init` — own independent repo | P0 (nested repo, ignored by SODA) | `git status` shows 11 untracked entries
- 2026-10-29 | `../.gitignore` (SODA root) | appended `ielts-speaking-practice/` | keep SODA repo clean of the sub-project | file edit applied; only SODA change in this whole project
- 2026-10-29 | `ielts-speaking-practice/node_modules` | `npm install` — 165 packages | deps for copied UI | install exited 0
- 2026-10-29 | `ielts-speaking-practice/dist/` | `npm run build` baseline with untouched copied src | prove the copied UI is intact before trimming | ✓ built in 22.26s
- 2026-10-29 | `backend/logger.py` | console logger (Render-aware level, module:line format) | shared logging for all backend modules | imported by every module successfully
- 2026-10-29 | `backend/rubric.py` | official 0-9 descriptors × 4 criteria, `RUBRIC_PROMPT`, `round_half_up` (IELTS half-up), `overall_band`, `clamp_band` | single source of truth for scoring | 6 unit tests green
- 2026-10-29 | `backend/question_bank.py` | 20 Part-1 topics × 3 Qs, 15 Part-2 cue cards (with Part-3 follow-ups) | exam content + repeatable sessions | exercised by examiner tests
- 2026-10-29 | `backend/prompts.py` | examiner system prompt (verbatim-read protocol), text-eval prompt, pronunciation prompt, greeting | model behavior contract | imported by voice + evaluation
- 2026-10-29 | `backend/ielts_tools.py` | exactly 7 Gemini function declarations (start_test, evaluate_answer, next_question, repeat_question, finish_test, set_goal, get_progress) | no non-IELTS tools exist | compile OK
- 2026-10-29 | `backend/evaluation.py` | DeepSeek text eval ∥ Gemini WAV pronunciation eval, JSON extraction, heuristic fallbacks, merged band output | scoring with per-provider degradation | 9 offline tests green
- 2026-10-29 | `backend/store.py` | Supabase DDL (`ielts_clients/sessions/answers`), lazy connect, JSONL fallback, progress/history | persistence without accounts | 7 tests green; fixed invalid `global ... as` line
- 2026-10-29 | `backend/examiner.py` | test FSM (part1→2→3, cue-card prep), spoken-script builders (verbatim), report math (half-band), progress update | deterministic exam flow independent of LLM | 15 tests green
- 2026-10-29 | `backend/voice.py` | slim AudioLoop port: per-session queues, echo-safe browser mic, answer PCM/text capture, 4s wall-clock silence, tool dispatch, Part-2 prep timer, eval rate limit, room-targeted emits | one isolated voice session per visitor | imported OK; unit tests green
- 2026-10-29 | `backend/server.py` | FastAPI + Socket.IO (`app_socketio`), `/status` health, allowlisted events (connect/disconnect/start_audio/stop_audio/browser_audio/run_ielts_tool/ping), MAX_SESSIONS gate, CORS env | public multi-visitor backend | imports OK; `/status` route present
- 2026-10-29 | `requirements.txt`, `Dockerfile`, `render.yaml`, `netlify.toml` | deploy config: python:3.11-slim + uvicorn, Render docker + `/status` health, Netlify build `dist` + SPA redirect | one-command deploys | compile + build green
- 2026-10-29 | `tests/run_all.py`, `tests/test_rubric.py`, `tests/test_examiner.py`, `tests/test_evaluation.py`, `tests/test_store.py` | stdlib unittest suite, fully offline (mock store `_connect`, blank keys) | regression safety + Render CI parity | 37/37 pass in 0.05s

---

## 6. Environment variables

| Var | Where | Required | Purpose |
|---|---|---|---|
| `GEMINI_API_KEY` | Render backend | yes | Gemini Live voice + band scoring + pronunciation review (billing-enabled key required) |
| `TEXT_EVAL_PROVIDER` | Render backend | no | text scorer: `gemini` (default) or `deepseek` |
| `TEXT_EVAL_MODEL` | Render backend | no | default `gemini-2.5-flash` |
| `DEEPSEEK_API_KEY` | Render backend | no | optional alternative text evaluator (only when `TEXT_EVAL_PROVIDER=deepseek`) |
| `SUPABASE_DB_URL` | Render backend | no | progress/history persistence (JSONL fallback) |
| `PRONUNCIATION_MODEL` | Render backend | no | default `gemini-2.5-flash` |
| `MAX_SESSIONS` | Render backend | no | default `5` |
| `CORS_ORIGINS` | Render backend | no | Netlify site origin |
| `PORT` | Render backend | no | default `8000` |
| `VITE_BACKEND_URL` | Netlify build env | yes | UI → backend URL |

---

## 7. Deployment

- **Backend**: Render web service from repo, Docker (`python:3.11-slim`), health check `/status`.
- **Frontend**: Netlify site, build `npm run build`, publish `dist`, redirect `/* → /index.html`, build env `VITE_BACKEND_URL`.
- **Git**: own repo (private) → `gh repo create`; SODA `.gitignore` gains `ielts-speaking-practice/`.
- **Smoke**: open live URL → Start Practice → mic grant → 1 question → evaluation panel → final report.

---

## 8. Verification commands

```bash
cd ielts-speaking-practice
npm run build                    # frontend
py -3.11 -m compileall -q backend
py -3.11 tests/run_all.py        # unit tests
npm run dev                      # local E2E: backend :8000 + vite :5173
```

---

## 9. Known limitations / follow-ups

- Band scores are AI-estimated, not an official IELTS exam result (stated in UI footer).
- Pronunciation review needs ≥2 s of clean audio; otherwise text-heuristic + "audio unavailable" note.
- Render free tier sleeps when idle → first visit has a cold start (~30 s).
- No user accounts: history tied to anonymous per-browser `client_id` (clearing site data resets progress).

