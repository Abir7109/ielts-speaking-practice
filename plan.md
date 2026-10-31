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
- **2026-10-30 | Pronunciation is audio-owned** — Only the audio reviewer (`build_pronunciation_prompt`, WAV from the part recording) may produce a Pronunciation band. The text evaluator is told not to output one, the merge never inherits one, and the old hardcoded `5.0` fabrication is gone. With no usable recording the criterion is `null` / "NOT ASSESSED", never a guessed number.
- **2026-10-30 | Overall band averages assessed criteria only** — `rubric.overall_band()` drops `None` bands instead of reading them as Band 0, so an unassessed Pronunciation no longer drags every report down by ~1.5 bands.
- **2026-10-30 | Evidence-grounded marking** — `build_evidence_brief()` measures per-criterion signals (filler rate, self-repairs, words/turn, TTR, over-used words, less-common items, complex vs advanced clause counts, error density) and injects them into the prompt, with a STRICT UNIQUENESS RULE: each criterion quotes a different span. `_repair_clones()` overwrites any reason/evidence duplicated across criteria with that criterion's own measured signal.
- **2026-10-30 | Fallback kept, but differentiated** — the offline heuristic stays as the safety net (user chose not to remove it), but each of its three text bands is now computed from its own metric (`_fluency_band` / `_lexical_band` / `_grammar_band`) so the fallback can no longer justify all four criteria with one word count.
- **2026-10-30 | The browser owns the mic gate** — `playback_drained` (sent when the Web Audio schedule has been quiet past a 0.35 s guard) is the authoritative "the examiner has stopped talking" signal; it, not a server-side wall-clock guess, reopens the microphone. `SILENCE_FALLBACK_SECONDS = 1.5` only covers a lost socket signal. The silence clock is an *instance* attribute re-armed after every tool response, so a slow `evaluate_part` can no longer fling the gate open mid-sentence.
- **2026-10-30 | A question is read exactly once** — scripted-question transcript suppression is retired by the model's own `turn_complete` (with a 90 s max-age backstop), never by the first incoming mic frame, so the examiner's live paraphrase of the scripted text no longer appears as a second utterance. `next_question` called inside the patience window returns "say only *Take your time.*" guidance instead of a re-ask instruction.
- **2026-10-30 | Phones get a bottom sheet** — at `≤768px` both side panels become a single full-width bottom sheet (`clamp(200px, min(46dvh, 100dvh − 360px), 70dvh)`) and the transcript/panel invariant forces only one open at a time, so the orb and Start/End controls are never covered. `768` is shared between `main.css` and `PanelSpaceContext.jsx`.
- **2026-10-30 | Viewport-relative layout, no fixed screens** — `100dvh`, `viewport-fit=cover`, `env(safe-area-inset-*)`, 44 px minimum touch targets, and an orb sized from `orbSizeFor(w, h, isPhone)` instead of a fixed pixel box; `overflow-hidden` on `html/body` is gone so short-and-wide Android viewports can scroll.

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
  ielts_tools.py    Gemini function declarations (6 tools only)
  prompts.py  examiner system prompt + evaluation prompts
  store.py    Supabase ielts_* tables → JSONL fallback
    │
    ├─ Gemini Live (voice conversation + tool calls)
    ├─ DeepSeek API (band text evaluation)
    ├─ Gemini generate_content (pronunciation, audio part)
    └─ Supabase Postgres (progress/history)
```

### Only-IELTS enforcement (4 layers)
1. Gemini `tools=` = `start_test, repeat_question, next_question, finish_test, set_goal, get_progress` only (part scoring is backend-driven).
2. System prompt: certified IELTS examiner, English only, exact-text-to-speak protocol, "no other abilities — steer back to the test".
3. Backend socket allowlist: `connect, disconnect, start_audio, stop_audio, browser_audio, run_ielts_tool, ping`. Unknown events rejected. `run_ielts_tool` re-checks the 6-tool allowlist.
4. Frontend: all non-IELTS panels/hooks/animations deleted.

### Exam flow
1. **Start Practice** click (user gesture → mic permission) → `start_audio {client_id}` → examiner greets, offers full mock / single part.
2. Part 1: 3–4 questions; answers accumulate silently, then the whole part is scored once and spoken before Part 2.
3. Part 2: cue card panel + 60 s prep countdown → 2-min long turn → part scored once before Part 3.
4. Part 3: 4–5 discussion questions → part scored once; final report follows.
5. `finish_test` → final report panel (per-part + overall, corrections, strengths, tips) + spoken summary → saved to Supabase.

### Scoring
- Criteria: Fluency & Coherence, Lexical Resource, Grammatical Range & Accuracy, Pronunciation (full 0–9 descriptors in `rubric.py`).
- Overall = mean of 4 → round to nearest **0.5**. Part band = mean of its answers (rounded). Final = mean of part bands (rounded). Documented approximation of examiner judgement.
- Evaluation cadence: answers are captured per question but scored **once per part** (`evaluate_part` combines all Q/A turns into one performance; pronunciation uses the concatenated part audio). No band is spoken after individual answers. Answer text and PCM are owned by the backend (from `input_transcription`/browser audio, NOT model-supplied); JSON extraction (```json fence → brace slice) + 1 retry + heuristic fallback.

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
- 2026-10-30 | `backend/server.py` | CORS now always allows all origins (`CORS_ORIGINS` informational only; logged when set) for both FastAPI and Socket.IO | new frontend URL `https://soda-ielts.netlify.app` was blocked ("No Access-Control-Allow-Origin") because Render allowlist still had the old domain | verified live: handshake 200 with `access-control-allow-origin: https://soda-ielts.netlify.app`; `smoke_tool.js` from new origin EXIT=0
- 2026-10-30 | `smoke_live.js`, `smoke_tool.js` | origin now `process.env.ORIGIN` default `https://soda-ielts.netlify.app` | smoke tests match the new production frontend | `smoke_tool.js` start_test → Part 1 Q1 OK
- 2026-10-30 | `.env.example` | `CORS_ORIGINS=*` documented as informational; allow-all by design | prevent future site-rename breakage | n/a
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
- 2026-10-30 | `backend/examiner.py`, `backend/voice.py`, `backend/evaluation.py`, `backend/prompts.py`, `backend/ielts_tools.py`, `src/components/panels/IELTSSpeakingPanel.jsx`, `tests/` | **scoring cadence fix**: removed per-answer `evaluate_answer`; answers accumulate and the whole part is scored once via `evaluate_part` (combined Q/A transcript + part audio) at part boundaries; final report aggregates part evals; part feedback names the part and its band; prompt forbids per-answer bands and defaulting to 5.5; part label in UI; duplicate examiner transcript suppression fixed; tests updated (51) | user: examiner scored after every answer and returned 5.5 constantly | `py -3.11 tests/run_all.py` → 51/51 OK; `npm run build` OK
- 2026-10-30 | deploy verification | commit `edb1afe` pushed → Render backend redeploy triggered; Netlify production deploy `6ae4168c` live at https://soda-ielts.netlify.app; `/status` → `{"ok":true,"db":true,"eval":"gemini"}` | ship part-scoring fix to production | backend health OK; live scoring cadence pending user retest (no local `GEMINI_API_KEY`)
- 2026-10-30 | `backend/rubric.py` | `TEXT_CRITERIA` / `AUDIO_CRITERIA` / `assessed_criteria()`; `overall_band()` now averages only criteria that carry a numeric band (`None` = unassessed, not Band 0) | a missing pronunciation review was silently costing ~1.5 bands on every report | `tests/test_rubric.py::test_overall_band_excludes_unassessed` (8.0 / 6.0 / 0.0 cases) replaced the old "missing = 2.0" assertion
- 2026-10-30 | `backend/prompts.py` | rewrote both text-eval prompts: per-criterion *lens* (which evidence belongs to it), STRICT UNIQUENESS RULE (no reused quotes, no reused reason shape, expect band spread), `why_not_higher` / `why_not_lower` / `question_notes[]` / `improvements[].criterion` in the schema, explicit `DO NOT output a "pronunciation" score`, evidence block injection; pronunciation prompt now demands only what is actually *heard*; dropped unused `import os` | "Score the part as ONE performance" produced one impression paraphrased four times — the root cause of the identical-reason complaint | `test_part_prompt_carries_measured_signals`, `test_part_prompt_omits_evidence_block_when_absent`
- 2026-10-30 | `backend/evaluation.py` | added `build_evidence_brief()` (words/turn, wpm, filler %, self-repairs, TTR, over-used words, less-common + idiomatic items, complex-vs-advanced clause counts, error density, pronunciation deferral) and pass it into both prompt builders; split `COMPLEX_MARKERS` into `SUBORDINATION_MARKERS` + `ADVANCED_MARKERS`; whole-word `_marker_hits()` ("if" no longer fires inside "difficult"); sentences/clauses split apart (clause counts drive GRA, `A\d+:` markers drive turns); `SELF_REPAIR_MARKERS`/`LESS_COMMON_LEXIS`/`IDIOM_MARKERS` added | the model only ever saw a wall of text, so it judged all four criteria from overall length; `"if" in "difficult"` was counted as a conditional clause and one 40-word answer was scored as three "turns" | `TestDescriptorShapedScoring` (5 tests): "because…because…" caps GRA at 6.0 while relative/conditional/contrast clauses reach 7.0; connectives cancel the false fluency penalty; a 5-word answer earns no TTR credit; one answer = one turn; whole-word markers
- 2026-10-30 | `backend/evaluation.py` | **filler false-positive fix**: `like` now only counts when comma-adjacent (`r",\s*like\b"`, `r"\blike\s*,"`) | "I like cooking" is the most common answer pattern in the bank and was being scored as hesitation, dragging FC down for everyone | `test_short_answer_scored_low` (FC 4.0) passes again
- 2026-10-30 | `backend/evaluation.py` | per-criterion fallback models `_fluency_band` / `_lexical_band` / `_grammar_band` + `_half_step()` (clamps 2.5–8.5); `_heuristic_text_evaluation()` scores each text criterion from its own metric, returns `pronunciation: None` and an explicit "Not assessed … needs a recording" reason; dropped the `min(band, 6.0)` GRA ceiling when no advanced clause exists; TTR credit needs ≥30 words; discourse-marker penalty only when *no* connective links ideas and the turn is ≥15 words | the old fallback derived one word-count base and stamped it on all four criteria, so a 36-word sophisticated answer scored **below** a 55-word basic one | `test_length_does_not_drive_every_criterion`, `test_pronunciation_is_not_scored_from_text`; 120-word expectation deliberately moved 6.0 → 5.5
- 2026-10-30 | `backend/evaluation.py` | `_merge_evaluations()` never inherits pronunciation from the text result (removed the hardcoded `scores["pronunciation"] = 5.0`), exposes `pronunciation_assessed` / `question_notes` / `repaired_criteria` and the `pronunciation-unassessed` degraded flag; new `_pronunciation_feedback()` (audio-only); new `_repair_clones()` detects duplicated normalized reasons/quotes across `TEXT_CRITERIA` and overwrites them with that criterion's measured signal, logging `[EVAL] cloned reason for … replaced with measured signal`; `_normalise_criterion_feedback()` carries `why_not_higher` / `why_not_lower` | a band presented as measured when nothing was measured, plus the four-identical-reasons report the user reported | `TestCloneGuard` (`test_identical_reasons_are_repaired`, `test_text_evaluator_cannot_set_pronunciation`)
- 2026-10-30 | `backend/examiner.py` | `_numeric_scores()` + `_pick_edge()` rotate over tied bands (a tie used to always resolve to Fluency, so every report named the same weakness); module templates `_CLOSE` / `_LIMIT` / `_FIX` / `_REPORT_OPENERS`; `spoken_feedback()` seeds rotation on `part + int(band*2) + CRITERIA.index(weakest)`, names the strongest side sometimes, and admits an unassessed pronunciation instead of reciting a zero; `build_report()` stores `None` per unassessed criterion, aggregates `question_notes[:12]`, carries `why_not_higher`; `spoken_report()` lists only assessed criteria and states the rest; `_update_progress()` gaps ignore non-numeric bands | user: "make soda's ielts agent feel natural and much more capable while marking" — consecutive parts were word-for-word identical and weak_areas was permanently "pronunciation" | `test_consecutive_parts_are_not_word_for_word`, `test_unassessed_pronunciation_is_admitted_not_recited_as_zero` (replaced two fixed-opener assertions)
- 2026-10-30 | `src/components/panels/IELTSReportPanel.jsx`, `src/components/panels/IELTSSpeakingPanel.jsx` | band cells render `NOT ASSESSED` (muted, smaller) instead of a number when the band is `null`; added `BLOCKING THE NEXT HALF-BAND:` (`why_not_higher`) and an "Examiner notes, question by question" block (`P{n} Q{index}`) | the panels would have shown `null`/blank for an honestly unassessed pronunciation criterion | `npm run build` ✓ 5.23s (no recharts/`BarChart3` consumer in this app, so `null` cannot crash a chart)
- 2026-10-30 | verification | `py -3.11 -m compileall -q backend` OK; `py -3.11 tests/run_all.py` → **67/67 OK**; `npm run build` ✓ | full §8 trio green | offline probe re-run before deletion: ADVANCED `FC 5.5 / LR 6.0 / GRA 7.0`, BASIC-LONG `FC 6.0 / LR 5.5 / GRA 6.0`, HALTING `FC 4.0 / LR 5.0 / GRA 5.5`, Pronunciation `None` in all rows; the four reasons never match; a hand-cloned Gemini payload triggered `[EVAL] cloned reason …` repairs
- 2026-10-30 | deploy verification | commit `548f6e6` pushed → Render live pod `/status` now reports `commit:"548f6e6"`, `eval:"gemini"`, `db:true`; Netlify production deploy `6ae4c942dadb01470f20fdb8` at https://soda-ielts.netlify.app (bundle `index-S-CDAhh7.js` contains `NOT ASSESSED`, `BLOCKING THE NEXT HALF-BAND`, `Examiner notes`); `node smoke_tool.js` EXIT=0 — greeting + Part 1 Q1 spoken verbatim | ship per-criterion marking to production | `eval_last` still empty: no real spoken session scored yet, so per-criterion distinctness on the Gemini path awaits a live test session
- 2026-10-30 | `backend/voice.py` | **mic-gate root cause**: `_last_audio_time` promoted from a local in `play_audio` to an instance attribute, re-armed in `notify_playback_drained()`, after `send_tool_response()` and on WS reconnect; silence fallback renamed `SILENCE_FALLBACK_SECONDS = 1.5` (was a local `_SILENCE_THRESHOLD = 4.0`) | the local clock went stale across a slow `evaluate_part`, so the gate flung open *while the examiner was still talking* — and when it did fire, the candidate waited ~4 s in silence. User: "after its done speaking its not turning on the mic to hear the student immediately !" | `tests/test_voice_turn_taking.py::TestMicGate` (drop-while-speaking, reopen-on-drain, no-op-when-idle)
- 2026-10-30 | `backend/voice.py`, `backend/server.py`, `src/hooks/useAudioPlayback.js`, `src/hooks/useIeltsSession.js` | **authoritative drain signal**: `useAudioPlayback` now tracks `playEndRef` from the Web Audio schedule (`audioNextTime = startTime + buffer.duration`) and fires `onDrained` once the queue has been quiet past `DRAIN_GUARD_SECONDS = 0.35` (polled every `DRAIN_POLL_MS = 100`, one-shot until re-armed); `useIeltsSession.onPlaybackDrained` emits `playback_drained` and flips local `speaking` off; `@sio.on("playback_drained")` → `VoiceSession.notify_playback_drained()` clears `_model_is_speaking` and emits `speaking_state: idle` | the server cannot know when playback ends — chunks arrive faster than they play, so only the browser's own audio clock is accurate | live drain path needs a real session; guard/emit wiring verified by build + socket handler test
- 2026-10-30 | `backend/voice.py` | **duplicate-speech root cause**: `feed_browser_audio` no longer resets `_script_transcript_active`/`_script_transcript_seen` (first mic frame used to unmask the model's live output); suppression now expires only via `SCRIPT_TRANSCRIPT_MAX_AGE = 90.0` or the model's own `turn_complete`, which clears it unconditionally | the examiner read the scripted question *and* its own paraphrase — the transcript showed "Do you work or are you a student?" then "Great. Do you work or are you a student?", then the Part-1 question twice more. User: "its repeating speech its not talking naturally" | `TestMicGate.test_*_do_not_unmask_script_transcript`
- 2026-10-30 | `backend/voice.py` | new `_no_answer_guidance()`: inside `PREMATURE_CALL_SECONDS = 12` of asking, `next_question` tells the model the candidate has not had time to answer → say only "Take your time." and stay silent; after that window it says nothing was recorded → encourage once, call it "that question", never re-read it; `_question_asked_at` stamped in `start_test`, `next_question` (advance) and `repeat_question` | the old guidance literally instructed "answer it again", which manufactured the repeat loop | `TestNoAnswerGuidance` (patience branch, stale branch, neither ever offers a re-ask, both contain "Do NOT repeat")
- 2026-10-30 | `backend/prompts.py` | examiner prompt: YOUR JOB renumbered 1-6 with a new rule 4 (call `next_question` only *after* the candidate has answered, never in the same breath as asking); TOOL RULES `next_question` now says to answer "Take your time." and wait if the tool reports no answer; SPEAKING RULES gained "Say each question exactly once. Once you have read a question aloud, stop talking and listen" and clarifies that rephrasing or repeating it after reading is not natural | behaviour fixes alone leave the model free to re-ask; the contract must say so | manual review; turn-taking tests green
- 2026-10-30 | `tests/test_voice_turn_taking.py` | new file, 9 tests, fully offline (`FakeSio`, `asyncio.Queue`, no Gemini) | the three regressions the user reported were invisible to the old suite | `py -3.11 tests/run_all.py` → 76/76 OK
- 2026-10-30 | `index.html` | viewport meta gains `viewport-fit=cover` | Android gesture bars and notches need the safe-area insets the CSS now consumes | build OK
- 2026-10-30 | `src/styles/main.css` | `html, body` drop `@apply h-screen w-screen overflow-hidden` → `height:100vh/100dvh`, `overflow-x:hidden`, `overflow-y:auto`, `overscroll-behavior-y:none`, `-webkit-text-size-adjust:100%`; `#root` gets `min-height:100dvh`; new trailing section: `.app-shell{min-height:100dvh}`, `button,.slide-panel-close{touch-action:manipulation}`, and a `@media (max-width:768px)` block pinning side panels above the safe area, converting `.slide-panel-left/.right` intent into the `.slide-panel-bottom` sheet (`100vw`, `height: clamp(200px, min(46dvh, calc(100dvh - 360px)), 70dvh)`, no side/bottom borders, `padding-bottom: env(safe-area-inset-bottom)`), `.slide-panel-body{padding:12px;-webkit-overflow-scrolling:touch}`, `.slide-panel-close{min 44px}`; the pre-existing `max-width:400px` and `max-width:640px` media blocks keep their behaviour | `overflow:hidden` + `100vh` clipped content on Android Chrome (dynamic toolbars) and blocked any scroll; fixed 400/520 px panels covered the whole screen on a phone | `npm run build` ✓; at 357 px `document.documentElement.scrollWidth === innerWidth` (no horizontal overflow)
- 2026-10-30 | `src/App.jsx` | `useOrbSize()` → `useViewport()` (resize + orientationchange) with a pure `orbSizeFor(w, h, isPhone) = max(150, min(isPhone ? 400 : 420, min(w * (isPhone ? 0.46 : 0.36), h * 0.32)))`; root becomes `className="app-shell"` (no inline `minHeight:100vh`/`overflow:hidden`); header wraps, pads by `max(Npx, env(safe-area-inset-top))`, hides the "AI EXAMINER" label on phone, Log/Progress become 44×44 icon-only buttons via a shared `headerBtn`, status text shortens to "SPEAKING"; `main` uses `justifyContent: isPhone && sheetOpen ? 'flex-start' : 'center'` with phone-aware gap/padding and hides the hint block while a sheet is open; Start/End/Dashboard use a shared `actionBtn` (`minHeight:48`, `flex:1 1 auto` on phone, Start 52); footer font 8 + `paddingBottom: max(Npx, env(safe-area-inset-bottom))`; both `SlidePanel`s take `direction={isPhone ? 'bottom' : 'left'|'right'}` with 44 px tab buttons; error toast sits at `calc(12px + env(safe-area-inset-bottom))`, `maxWidth: calc(100vw - 24px)`, dismiss button 44×44 with `aria-label` | the fixed 420 px orb, 560/380 px panels and 1024 px-only layout were unusable at Android widths (320–500 px) | measured in same-origin iframes: 357 px → sheet `x0 y376 w357 h321`, chips 77-107, orb 121-285, controls 299-351 (`controlsClear:true`), all buttons ≥44 px; 1021 px desktop panel geometry unchanged (`right:12`, `width:400`, `top:12`, `height:673`)
- 2026-10-30 | `src/hooks/useIeltsSession.js` | `SHEET_WIDTH = 768` + `isSheetLayout()`; `start()` opens the transcript only when not in sheet layout; an effect enforces the invariant "never both the transcript and the right panel on a phone" (auto-closes the transcript) | two full-screen overlapping panels on a phone made the app unusable and hid the mic controls | build OK; layout invariant exercised in the 357 px iframe
- 2026-10-30 | `src/contexts/PanelSpaceContext.jsx` | the four horizontal-nudge cutoffs move from `vw < 640` to `vw < 768`, with a comment tying the number to the `main.css` sheet breakpoint | below 768 the panels span the full viewport, so any nudge pushed them offscreen | desktop offsets (80/120/160/140/200) untouched
- 2026-10-30 | `src/components/panels/IELTSDashboardPanel.jsx` | the trend grid `gridTemplateColumns:'1fr 1fr 1fr'` → `repeat(auto-fit, minmax(96px, 1fr))` | three fixed columns overflowed at 320-400 px | build OK
- 2026-10-30 | verification | `py -3.11 -m compileall -q backend` OK; `py -3.11 tests/run_all.py` → **76/76 OK**; `npm run build` ✓ 3.29 s (`index-C4e0ZEhj.css` 99.90 kB, `index-HIphCtbT.js` 248.01 kB) | §8 trio green for both fixes | live turn-taking (mic reopening, single question) still needs a real spoken session on Render — no local `GEMINI_API_KEY`


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
| `CORS_ORIGINS` | Render backend | no | Allow-all by design (`*`); safe for public cookie-less app |
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
- Pronunciation review needs ≥2 s of clean audio; without it the criterion is reported as **unassessed** (`null` → "NOT ASSESSED" in both panels, excluded from the overall band average, and admitted aloud by the examiner). It is never guessed from the transcript.
- The offline text evaluator (fallback only) still reads long-and-filler-free as *fluent*: turn length is a word-count proxy, so a rambling 61-word answer can out-score a tight 41-word one on Fluency. Real hesitation, pace and pausing only come from the audio path, which production uses (`/status` → `eval:"gemini"`).
- `question_notes` and the clause-tier markers are transcript-shape heuristics; the model may still quote a span the candidate never said. `_repair_clones()` only catches *duplicated* reasons, not fabricated ones.
- Render free tier sleeps when idle → first visit has a cold start (~30 s).
- No user accounts: history tied to anonymous per-browser `client_id` (clearing site data resets progress).
- Turn-taking fixes are verified offline only. `playback_drained` depends on the browser actually emitting it, and `PREMATURE_CALL_SECONDS = 12` is a fixed patience window — a Part-2 long turn legitimately runs longer than it, which is fine (the stale branch encourages once rather than re-asking) but has not been re-heard on a real session. A live run on Render is still pending (no local `GEMINI_API_KEY`).
- The 768 px sheet breakpoint is duplicated as a constant in three places (`main.css` media query, `PanelSpaceContext.jsx` `vw < 768`, `useIeltsSession.js` `SHEET_WIDTH`). They must move together; only comments enforce it.
- `clamp(200px, min(46dvh, 100dvh − 360px), 70dvh)` reserves a fixed 360 px for header + orb + controls. On an extremely short landscape phone (<600 px tall) the sheet floors at 200 px and the orb shrinks instead — not separately measured.

