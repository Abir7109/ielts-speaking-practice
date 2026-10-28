"""IELTS speaking test state machine.

Pure logic: no sockets, no LLM calls. The voice layer owns I/O and calls into
this class; evaluation happens in evaluation.py and is fed back via record_answer().
"""
import time
from datetime import date, datetime

from logger import log
from question_bank import get_part1_questions, get_part2_cue_card, get_part3_questions
from rubric import CRITERIA, CRITERIA_LABELS, overall_band, round_half_up
import store


class Examiner:
    def __init__(self, client_id: str = ""):
        self.client_id = client_id or ""
        self.mode = None
        self.part = 0
        self.topic = None
        self.started_at = None
        self.finished = False

        self._queues: dict[int, list] = {}
        self._cursor: dict[int, int] = {}
        self._cue_card = None

        self.current_question = None
        self.current_payload = None
        self._evaluated_current = True   # nothing pending until a question is issued

        self.answers: list[dict] = []     # {part, question, answer_text, evaluation}

    # ── lifecycle ────────────────────────────────────────────────

    def start(self, mode: str, topic: str = None) -> dict:
        mode = (mode or "full").lower()
        if mode not in ("full", "part1", "part2", "part3"):
            mode = "full"
        self.mode = mode
        self.topic = topic
        self.started_at = datetime.now().isoformat()
        self.finished = False
        self.answers = []
        self._spoken_part = None

        if mode in ("full", "part1"):
            p1 = get_part1_questions(topic)
            self._queues[1] = list(p1["questions"])
            self._topic1 = p1["topic"]
        else:
            self._queues[1] = []

        if mode in ("full", "part2", "part3"):
            self._cue_card = get_part2_cue_card()
        else:
            self._cue_card = None

        if mode in ("full", "part2"):
            self._queues[2] = ["__cue_card__"]
        else:
            self._queues[2] = []

        if mode in ("full", "part3"):
            if mode == "part3":
                # need follow-up context: build a throwaway cue card
                self._cue_card = self._cue_card or get_part2_cue_card()
            self._queues[3] = list(
                get_part3_questions(self._cue_card)["questions"]
            )
        else:
            self._queues[3] = []

        self._cursor = {p: 0 for p in (1, 2, 3)}
        self.part = 0
        return self._issue_next()

    def _issue_next(self) -> dict | None:
        for part in (1, 2, 3):
            q = self._queues.get(part) or []
            idx = self._cursor.get(part, 0)
            if idx < len(q):
                if part != self.part and self.part != 0:
                    # part transition
                    self.part = part
                    self._cursor[part] = idx + 1
                    return self._payload_for(part, q[idx], first_of_part=True)
                self.part = part
                self._cursor[part] = idx + 1
                return self._payload_for(part, q[idx], first_of_part=(idx == 0))
        return None

    def advance(self) -> dict | None:
        """Move to the next queued question; None when the test is over."""
        return self._issue_next()

    def _payload_for(self, part: int, item: str, first_of_part: bool) -> dict:
        total = len(self._queues.get(part) or [])
        idx = self._cursor.get(part, 1)
        if item == "__cue_card__":
            card = self._cue_card or get_part2_cue_card()
            bullets = card.get("bullet_points") or card.get("points") or []
            self.current_question = f"{card['topic']}: {', '.join(bullets)}"
            self.current_payload = {
                "kind": "cue_card",
                "part": 2,
                "topic": card["topic"],
                "bullet_points": bullets,
                "prep_time_seconds": card.get("prep_time_seconds", 60),
                "speak_time_seconds": card.get("speak_time_seconds", 120),
                "instructions": card.get("instructions", ""),
                "question_index": idx,
                "question_total": total,
                "first_of_part": first_of_part,
            }
        else:
            self.current_question = item
            self.current_payload = {
                "kind": "question",
                "part": part,
                "topic": self.topic or getattr(self, "_topic1", None),
                "question": item,
                "question_index": idx,
                "question_total": total,
                "first_of_part": first_of_part,
                "instructions": (
                    "Give a developed answer: direct response + reason + example."
                    if part == 1 else
                    "Give a detailed, analytical answer with examples and discourse markers."
                ),
            }
        self._evaluated_current = False
        return self.current_payload

    # ── answer bookkeeping ──────────────────────────────────────

    @property
    def awaiting_answer(self) -> bool:
        """True when a question has been issued but not yet evaluated."""
        return self.current_payload is not None and not self._evaluated_current

    def record_answer(self, answer_text: str, evaluation: dict) -> dict:
        entry = {
            "part": evaluation.get("part", self.part),
            "question": evaluation.get("question") or self.current_question or "",
            "answer_text": answer_text,
            "evaluation": evaluation,
        }
        self.answers.append(entry)
        self._evaluated_current = True
        return entry

    def skip_evaluation(self):
        """Mark current question handled without scoring (no answer captured)."""
        self._evaluated_current = True

    # ── spoken scripts (verbatim protocol) ──────────────────────

    def spoken_question(self, payload: dict | None = None) -> str:
        p = payload or self.current_payload or {}
        part = p.get("part", self.part)
        prefix = ""
        if part != getattr(self, "_spoken_part", None):
            self._spoken_part = part
            if part == 1:
                prefix = (
                    "Thank you. Let's begin Part 1 — the interview section. "
                    "I'll ask you some questions about familiar topics. "
                )
            elif part == 2:
                prefix = "Now we move to Part 2 — the long turn. "
            elif part == 3:
                prefix = (
                    "Thank you. Now for Part 3 — the discussion section. "
                    "I'll ask some more abstract questions. "
                )

        if p.get("kind") == "cue_card":
            pts = "\n".join(f"- {b}" for b in p.get("bullet_points", []))
            return (
                f"{prefix}Here is your cue card. "
                f"Topic: {p.get('topic', '')}. "
                f"You should say: {pts}. "
                f"You have one minute to prepare. "
                f"Start making brief notes now — I'll tell you when your minute is up, "
                f"and then you will have two minutes to speak."
            )
        q = p.get("question", self.current_question or "")
        if part == 2:
            return f"{prefix}{q}"
        return f"{prefix}{q}"

    def spoken_prep_over(self) -> str:
        return (
            "Your one minute of preparation time is now over. "
            "Please begin speaking — you have two minutes to talk about your topic. "
            "Start whenever you are ready."
        )

    def spoken_feedback(self, evaluation: dict) -> str:
        """Band + top correction only. The caller appends the next script."""
        band = evaluation.get("overall_band", "?")
        tip = ""
        imps = evaluation.get("improvements") or []
        if imps and isinstance(imps[0], dict):
            tip = imps[0].get("better_version") or imps[0].get("issue") or ""
        elif imps and isinstance(imps[0], str):
            tip = imps[0]
        speech = f"Your band for that answer is {band}."
        if tip:
            speech += f" Focus on this: {tip}"
        return speech

    def spoken_repeat(self) -> str:
        return f"Of course. {self.spoken_question()}"

    # ── finish / report ─────────────────────────────────────────

    def build_report(self) -> dict:
        per_part: dict[int, list] = {}
        for a in self.answers:
            per_part.setdefault(a["part"], []).append(
                a["evaluation"].get("overall_band", 0)
            )
        part_scores = {
            str(p): round_half_up(sum(v) / len(v))
            for p, v in per_part.items() if v
        }
        if self.answers:
            all_bands = [a["evaluation"].get("overall_band", 0) for a in self.answers]
            overall = round_half_up(sum(all_bands) / len(all_bands))
        else:
            overall = 0.0

        crit_scores = {}
        for crit in CRITERIA:
            vals = [
                float(a["evaluation"].get("band_scores", {}).get(crit, 0) or 0)
                for a in self.answers
            ]
            crit_scores[crit] = round_half_up(sum(vals) / len(vals)) if vals else 0.0

        corrections = []
        strengths = []
        tips = []
        for a in self.answers:
            ev = a["evaluation"]
            corrections.extend(ev.get("grammar_errors") or [])
            strengths.extend(ev.get("strengths") or [])
            if ev.get("band7_tip"):
                tips.append(ev["band7_tip"])

        weakest = min(crit_scores, key=lambda c: crit_scores[c]) if self.answers else None
        strongest = max(crit_scores, key=lambda c: crit_scores[c]) if self.answers else None

        report = {
            "mode": self.mode,
            "overall_band": overall,
            "part_scores": part_scores,
            "band_scores": crit_scores,
            "answer_count": len(self.answers),
            "corrections": corrections[:20],
            "strengths": strengths[:8],
            "top_tips": tips[:5],
            "weakest_criterion": CRITERIA_LABELS.get(weakest, "") if weakest else "",
            "strongest_criterion": CRITERIA_LABELS.get(strongest, "") if strongest else "",
            "disclaimer": "AI-estimated practice score — not an official IELTS result.",
            "generated_at": datetime.now().isoformat(),
        }
        self.finished = True
        return report

    def spoken_report(self, report: dict) -> str:
        scores = report.get("band_scores", {})
        parts = report.get("part_scores", {})
        part_txt = ", ".join(f"Part {k}: {v}" for k, v in sorted(parts.items()))
        return (
            f"That concludes your test. Your estimated overall band is "
            f"{report.get('overall_band', 0)}. "
            f"Fluency {scores.get('fluency_coherence', 0)}, "
            f"Vocabulary {scores.get('lexical_resource', 0)}, "
            f"Grammar {scores.get('grammatical_range', 0)}, "
            f"Pronunciation {scores.get('pronunciation', 0)}. "
            f"{part_txt}. "
            f"Your strongest area is {report.get('strongest_criterion', '—')}; "
            f"focus next on {report.get('weakest_criterion', 'your weakest area')}. "
            f"The full report with every correction is now on your screen."
        )

    # ── persistence ─────────────────────────────────────────────

    def save(self, report: dict) -> int | None:
        session = {
            "client_id": self.client_id,
            "mode": self.mode,
            "part_scores": report.get("part_scores", {}),
            "overall_band": report.get("overall_band", 0),
            "started_at": self.started_at,
            "report": report,
        }
        answers = [
            {
                "part": a["part"],
                "question": a["question"],
                "answer_text": a.get("answer_text", ""),
                "corrected_transcript": a["evaluation"].get("corrected_transcript", ""),
                "band_scores": a["evaluation"].get("band_scores", {}),
                "overall_band": a["evaluation"].get("overall_band", 0),
                "grammar_errors": a["evaluation"].get("grammar_errors", []),
                "vocabulary_feedback": a["evaluation"].get("vocabulary_feedback", {}),
                "pronunciation_detail": a["evaluation"].get("pronunciation_detail", {}),
                "word_count": a["evaluation"].get("word_count", 0),
                "filler_words_count": a["evaluation"].get("filler_words_count", 0),
            }
            for a in self.answers
        ]
        sid = store.save_session(session, answers)
        self._update_progress(report)
        return sid

    def _update_progress(self, report: dict):
        if not self.client_id:
            return
        try:
            client = store.get_client(self.client_id) or {}
            avg = client.get("average_bands") or {}
            new_band = report.get("overall_band", 0)
            prev = avg.get("speaking")
            speaking_avg = round_half_up(new_band if prev in (None, 0) else 0.3 * new_band + 0.7 * float(prev))
            avg["speaking"] = speaking_avg
            avg["overall"] = speaking_avg  # speaking-only app

            today = date.today().isoformat()
            last = client.get("last_session_date")
            streak = int(client.get("streak_days") or 0)
            if last != today:
                if last:
                    try:
                        gap = (date.today() - date.fromisoformat(last)).days
                        streak = streak + 1 if gap == 1 else 1
                    except Exception:
                        streak = 1
                else:
                    streak = 1

            target = float(client.get("target_band") or 7.0)
            gaps = sorted(
                ((c, target - float(report["band_scores"].get(c, 0) or 0)) for c in CRITERIA),
                key=lambda x: x[1],
                reverse=True,
            )
            weak = [c for c, g in gaps[:2] if g > 0]
            strong = [c for c, g in reversed(gaps) if g <= 0]

            store.upsert_client(self.client_id, {
                "average_bands": avg,
                "total_sessions": int(client.get("total_sessions") or 0) + 1,
                "speaking_sessions": int(client.get("speaking_sessions") or 0) + 1,
                "streak_days": streak,
                "last_session_date": today,
                "weak_areas": weak,
                "strong_areas": strong,
            })
        except Exception as e:
            log.warning(f"[EXAMINER] progress update failed: {e}")

    def set_goal(self, target_band=None, exam_date=None) -> dict:
        if not self.client_id:
            return {"target_band": target_band, "exam_date": exam_date}
        client = store.get_client(self.client_id) or {}
        fields = {}
        if target_band:
            fields["target_band"] = float(target_band)
        if exam_date:
            fields["exam_date"] = str(exam_date)
        if fields:
            store.upsert_client(self.client_id, fields)
        merged = {**client, **fields}
        return {"target_band": merged.get("target_band", 7.0), "exam_date": merged.get("exam_date")}

    def get_progress(self) -> dict:
        client = store.get_client(self.client_id) if self.client_id else None
        client = client or {}
        history = store.get_history(self.client_id, 20) if self.client_id else []
        avg = client.get("average_bands") or {}
        return {
            "target_band": client.get("target_band", 7.0),
            "exam_date": client.get("exam_date"),
            "average_bands": avg,
            "streak_days": client.get("streak_days", 0),
            "total_sessions": client.get("total_sessions", 0),
            "weak_areas": client.get("weak_areas", []),
            "strong_areas": client.get("strong_areas", []),
            "history": [
                {
                    "overall_band": h.get("overall_band"),
                    "mode": h.get("mode"),
                    "finished_at": h.get("finished_at") or h.get("generated_at"),
                    "part_scores": h.get("part_scores"),
                }
                for h in history
            ],
        }
