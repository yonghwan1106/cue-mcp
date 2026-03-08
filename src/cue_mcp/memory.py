"""Memory module: SQLite-backed episodic + semantic memory for learning across sessions.

Ported from CUE memory/episodic.py and memory/semantic.py.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path

from cue_mcp.types import EpisodeRecord, Lesson


class MemoryStore:
    """Combined episodic and semantic memory backed by SQLite."""

    def __init__(self, db_dir: str | None = None) -> None:
        if db_dir is None:
            db_dir = str(Path.home() / ".cue-mcp")
        self._db_dir = Path(db_dir)
        self._db_dir.mkdir(parents=True, exist_ok=True)

        self._episodic_path = str(self._db_dir / "episodic.db")
        self._semantic_path = str(self._db_dir / "semantic.db")

        self._init_episodic_db()
        self._init_semantic_db()

    # ── Episodic Memory ────────────────────────────────────

    def _init_episodic_db(self) -> None:
        with sqlite3.connect(self._episodic_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS episodes (
                    id TEXT PRIMARY KEY,
                    task TEXT NOT NULL,
                    app TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    total_steps INTEGER NOT NULL,
                    steps_summary TEXT NOT NULL,
                    failure_patterns TEXT NOT NULL,
                    recovery_strategies TEXT NOT NULL,
                    reflection TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ep_app ON episodes(app)")
            conn.commit()

    def store_episode(
        self, task: str, app: str, success: bool,
        total_steps: int = 0, reflection: str = "",
        failure_patterns: list[str] | None = None,
        recovery_strategies: list[str] | None = None,
    ) -> str:
        """Store a completed episode. Returns the episode ID."""
        episode_id = str(uuid.uuid4())
        now = time.time()
        with sqlite3.connect(self._episodic_path) as conn:
            conn.execute(
                """INSERT INTO episodes
                (id, task, app, success, total_steps, steps_summary,
                 failure_patterns, recovery_strategies, reflection, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    episode_id, task, app, int(success), total_steps,
                    f"{total_steps} steps",
                    json.dumps(failure_patterns or []),
                    json.dumps(recovery_strategies or []),
                    reflection, now,
                ),
            )
            conn.commit()
        return episode_id

    def find_similar_episodes(
        self, task: str, app: str, top_k: int = 3
    ) -> list[EpisodeRecord]:
        """Find similar past episodes for the given app."""
        with sqlite3.connect(self._episodic_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM episodes WHERE app = ? ORDER BY created_at DESC LIMIT 50",
                (app,),
            ).fetchall()

        if not rows:
            return []

        scored = []
        for row in rows:
            record = self._row_to_episode(row)
            sim = _jaccard_similarity(task, record.task)
            scored.append((sim, record))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [rec for _, rec in scored[:top_k]]

    def cleanup_episodes(self, max_age_days: int = 90) -> int:
        """Delete episodes older than max_age_days. Returns count deleted."""
        cutoff = time.time() - max_age_days * 86400
        with sqlite3.connect(self._episodic_path) as conn:
            cursor = conn.execute(
                "DELETE FROM episodes WHERE created_at < ?", (cutoff,)
            )
            conn.commit()
            return cursor.rowcount

    def _row_to_episode(self, row: sqlite3.Row) -> EpisodeRecord:
        return EpisodeRecord(
            id=row["id"], task=row["task"], app=row["app"],
            success=bool(row["success"]), total_steps=row["total_steps"],
            steps_summary=row["steps_summary"],
            failure_patterns=json.loads(row["failure_patterns"]),
            recovery_strategies=json.loads(row["recovery_strategies"]),
            reflection=row["reflection"], created_at=row["created_at"],
        )

    # ── Semantic Memory (Lessons) ──────────────────────────

    def _init_semantic_db(self) -> None:
        with sqlite3.connect(self._semantic_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS lessons (
                    id TEXT PRIMARY KEY,
                    app TEXT NOT NULL,
                    situation TEXT NOT NULL,
                    failed_approach TEXT NOT NULL,
                    successful_approach TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    success_count INTEGER NOT NULL,
                    failure_count INTEGER NOT NULL,
                    created_at REAL NOT NULL,
                    last_used REAL NOT NULL,
                    task_context TEXT NOT NULL,
                    text TEXT NOT NULL,
                    reinforcement_count INTEGER NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_les_app ON lessons(app)")
            conn.commit()

    def save_lesson(
        self, app: str, situation: str,
        failed_approach: str, successful_approach: str,
        confidence: float = 0.7, task_context: str = "",
    ) -> str:
        """Store or update a lesson. Returns the lesson ID."""
        now = time.time()
        text = (
            f"In {app}, when {situation}, "
            f"'{failed_approach}' fails; use '{successful_approach}' instead."
        )
        lesson = Lesson(
            id=str(uuid.uuid4()), app=app, situation=situation,
            failed_approach=failed_approach,
            successful_approach=successful_approach,
            confidence=confidence, success_count=1, failure_count=0,
            created_at=now, last_used=now,
            task_context=task_context, text=text, reinforcement_count=0,
        )
        self._upsert_lesson(lesson)
        return lesson.id

    def recall_lessons(self, app: str, top_k: int = 5) -> list[Lesson]:
        """Retrieve top lessons for an app, ordered by confidence."""
        with sqlite3.connect(self._semantic_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM lessons WHERE app = ? ORDER BY confidence DESC, last_used DESC LIMIT ?",
                (app, top_k),
            ).fetchall()

        lessons = [self._row_to_lesson(row) for row in rows]
        # Update last_used
        if lessons:
            now = time.time()
            ids = [l.id for l in lessons]
            placeholders = ",".join("?" * len(ids))
            with sqlite3.connect(self._semantic_path) as conn:
                conn.execute(
                    f"UPDATE lessons SET last_used = ? WHERE id IN ({placeholders})",
                    [now, *ids],
                )
                conn.commit()
        return lessons

    def recall_all_lessons(self, top_k: int = 20) -> list[Lesson]:
        """Retrieve top lessons across all apps."""
        with sqlite3.connect(self._semantic_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM lessons ORDER BY confidence DESC, last_used DESC LIMIT ?",
                (top_k,),
            ).fetchall()
        return [self._row_to_lesson(row) for row in rows]

    def _upsert_lesson(self, lesson: Lesson) -> None:
        with sqlite3.connect(self._semantic_path) as conn:
            conn.row_factory = sqlite3.Row
            existing = conn.execute(
                "SELECT id, confidence, success_count, failure_count FROM lessons "
                "WHERE app = ? AND situation = ?",
                (lesson.app, lesson.situation),
            ).fetchone()

            now = time.time()
            if existing:
                new_conf = min(1.0, existing["confidence"] +
                               (lesson.confidence - existing["confidence"]) * 0.3)
                conn.execute(
                    """UPDATE lessons SET confidence = ?, success_count = success_count + ?,
                    failure_count = failure_count + ?, reinforcement_count = reinforcement_count + 1,
                    last_used = ?, successful_approach = ?, text = ? WHERE id = ?""",
                    (new_conf, lesson.success_count, lesson.failure_count,
                     now, lesson.successful_approach, lesson.text, existing["id"]),
                )
            else:
                conn.execute(
                    """INSERT INTO lessons
                    (id, app, situation, failed_approach, successful_approach,
                     confidence, success_count, failure_count, created_at, last_used,
                     task_context, text, reinforcement_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (lesson.id, lesson.app, lesson.situation, lesson.failed_approach,
                     lesson.successful_approach, lesson.confidence,
                     lesson.success_count, lesson.failure_count,
                     lesson.created_at, lesson.last_used,
                     lesson.task_context, lesson.text, lesson.reinforcement_count),
                )
            conn.commit()

    def _row_to_lesson(self, row: sqlite3.Row) -> Lesson:
        return Lesson(
            id=row["id"], app=row["app"], situation=row["situation"],
            failed_approach=row["failed_approach"],
            successful_approach=row["successful_approach"],
            confidence=row["confidence"], success_count=row["success_count"],
            failure_count=row["failure_count"], created_at=row["created_at"],
            last_used=row["last_used"], task_context=row["task_context"],
            text=row["text"], reinforcement_count=row["reinforcement_count"],
        )


def _jaccard_similarity(text1: str, text2: str) -> float:
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    if not words1 and not words2:
        return 1.0
    if not words1 or not words2:
        return 0.0
    return len(words1 & words2) / len(words1 | words2)
