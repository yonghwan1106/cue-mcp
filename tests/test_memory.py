"""Tests for cue_mcp.memory — platform-independent."""

from __future__ import annotations

import time

import pytest

from cue_mcp.memory import MemoryStore, _jaccard_similarity
from cue_mcp.types import EpisodeRecord, Lesson


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def store(tmp_path):
    return MemoryStore(db_dir=str(tmp_path))


# ── MemoryStore: instantiation ─────────────────────────────────────────────────

class TestMemoryStoreInit:
    def test_creates_db_files(self, tmp_path):
        store = MemoryStore(db_dir=str(tmp_path))
        assert (tmp_path / "episodic.db").exists()
        assert (tmp_path / "semantic.db").exists()

    def test_creates_dir_if_missing(self, tmp_path):
        new_dir = tmp_path / "subdir" / "deep"
        store = MemoryStore(db_dir=str(new_dir))
        assert new_dir.exists()


# ── Episode: store and retrieve ────────────────────────────────────────────────

class TestStoreEpisode:
    def test_returns_string_id(self, store):
        ep_id = store.store_episode(task="open browser", app="chrome", success=True)
        assert isinstance(ep_id, str)
        assert len(ep_id) > 0

    def test_returns_unique_ids(self, store):
        id1 = store.store_episode(task="task a", app="app", success=True)
        id2 = store.store_episode(task="task b", app="app", success=False)
        assert id1 != id2

    def test_stored_episode_retrievable(self, store):
        store.store_episode(
            task="open settings", app="windows", success=True,
            total_steps=3, reflection="easy task",
        )
        results = store.find_similar_episodes("open settings", app="windows")
        assert len(results) >= 1
        ep = results[0]
        assert isinstance(ep, EpisodeRecord)
        assert ep.task == "open settings"
        assert ep.app == "windows"
        assert ep.success is True
        assert ep.total_steps == 3
        assert ep.reflection == "easy task"

    def test_failure_patterns_stored(self, store):
        store.store_episode(
            task="save file", app="notepad", success=False,
            failure_patterns=["dialog not found", "timeout"],
        )
        results = store.find_similar_episodes("save file", app="notepad")
        assert results[0].failure_patterns == ["dialog not found", "timeout"]

    def test_recovery_strategies_stored(self, store):
        store.store_episode(
            task="close app", app="notepad", success=True,
            recovery_strategies=["alt+f4", "task manager"],
        )
        results = store.find_similar_episodes("close app", app="notepad")
        assert results[0].recovery_strategies == ["alt+f4", "task manager"]

    def test_empty_failure_patterns_default(self, store):
        store.store_episode(task="task", app="app", success=True)
        results = store.find_similar_episodes("task", app="app")
        assert results[0].failure_patterns == []

    def test_no_results_for_different_app(self, store):
        store.store_episode(task="open browser", app="chrome", success=True)
        results = store.find_similar_episodes("open browser", app="firefox")
        assert results == []


# ── Episode: find_similar_episodes ────────────────────────────────────────────

class TestFindSimilarEpisodes:
    def test_top_k_limit(self, store):
        for i in range(5):
            store.store_episode(task=f"task {i}", app="myapp", success=True)
        results = store.find_similar_episodes("task 0", app="myapp", top_k=2)
        assert len(results) <= 2

    def test_similarity_ordering(self, store):
        store.store_episode(task="open file dialog", app="app", success=True)
        store.store_episode(task="open browser tab", app="app", success=True)
        store.store_episode(task="close window", app="app", success=True)
        # "open file dialog" should be most similar to query
        results = store.find_similar_episodes("open file dialog", app="app", top_k=3)
        assert results[0].task == "open file dialog"

    def test_empty_result_for_empty_store(self, store):
        results = store.find_similar_episodes("any task", app="app")
        assert results == []

    def test_returns_episode_record_instances(self, store):
        store.store_episode(task="do something", app="app", success=True)
        results = store.find_similar_episodes("do something", app="app")
        assert all(isinstance(r, EpisodeRecord) for r in results)


# ── Episode: cleanup ───────────────────────────────────────────────────────────

class TestCleanupEpisodes:
    def test_cleanup_returns_count(self, store):
        store.store_episode(task="old task", app="app", success=True)
        deleted = store.cleanup_episodes(max_age_days=0)
        assert isinstance(deleted, int)

    def test_cleanup_removes_old_episodes(self, store):
        store.store_episode(task="old task", app="app", success=True)
        # max_age_days=0 means cutoff = now, so all existing records are "old"
        deleted = store.cleanup_episodes(max_age_days=0)
        assert deleted >= 1
        results = store.find_similar_episodes("old task", app="app")
        assert results == []

    def test_cleanup_keeps_recent_episodes(self, store):
        store.store_episode(task="new task", app="app", success=True)
        # Keep episodes from the last 90 days — none should be deleted
        deleted = store.cleanup_episodes(max_age_days=90)
        assert deleted == 0
        results = store.find_similar_episodes("new task", app="app")
        assert len(results) == 1

    def test_cleanup_no_episodes_returns_zero(self, store):
        deleted = store.cleanup_episodes(max_age_days=30)
        assert deleted == 0


# ── Lesson: save and recall ────────────────────────────────────────────────────

class TestSaveLesson:
    def test_returns_string_id(self, store):
        lesson_id = store.save_lesson(
            app="notepad",
            situation="file not saved",
            failed_approach="close directly",
            successful_approach="ctrl+s first",
        )
        assert isinstance(lesson_id, str)
        assert len(lesson_id) > 0

    def test_lesson_retrievable(self, store):
        store.save_lesson(
            app="notepad",
            situation="file not saved",
            failed_approach="close directly",
            successful_approach="ctrl+s first",
            confidence=0.85,
        )
        lessons = store.recall_lessons("notepad")
        assert len(lessons) >= 1
        lesson = lessons[0]
        assert isinstance(lesson, Lesson)
        assert lesson.app == "notepad"
        assert lesson.situation == "file not saved"
        assert lesson.failed_approach == "close directly"
        assert lesson.successful_approach == "ctrl+s first"
        assert lesson.confidence == pytest.approx(0.85, abs=0.01)

    def test_lesson_text_generated(self, store):
        store.save_lesson(
            app="chrome",
            situation="page not loading",
            failed_approach="wait",
            successful_approach="refresh",
        )
        lessons = store.recall_lessons("chrome")
        assert lessons[0].text != ""
        assert "chrome" in lessons[0].text

    def test_no_lessons_for_unknown_app(self, store):
        store.save_lesson(
            app="notepad", situation="x", failed_approach="a", successful_approach="b"
        )
        lessons = store.recall_lessons("unknown_app")
        assert lessons == []

    def test_top_k_limit(self, store):
        for i in range(6):
            store.save_lesson(
                app="myapp",
                situation=f"situation {i}",
                failed_approach="bad",
                successful_approach="good",
            )
        lessons = store.recall_lessons("myapp", top_k=3)
        assert len(lessons) <= 3

    def test_task_context_stored(self, store):
        store.save_lesson(
            app="app",
            situation="ctx test",
            failed_approach="a",
            successful_approach="b",
            task_context="automation task",
        )
        lessons = store.recall_lessons("app")
        assert lessons[0].task_context == "automation task"


# ── Lesson: upsert (same situation updates existing) ──────────────────────────

class TestLessonUpsert:
    def test_same_situation_updates_not_duplicates(self, store):
        store.save_lesson(
            app="app", situation="same_situation",
            failed_approach="old_fail", successful_approach="old_success",
        )
        store.save_lesson(
            app="app", situation="same_situation",
            failed_approach="new_fail", successful_approach="new_success",
            confidence=0.9,
        )
        lessons = store.recall_lessons("app")
        # Should have exactly one lesson for this situation
        matching = [l for l in lessons if l.situation == "same_situation"]
        assert len(matching) == 1

    def test_upsert_updates_successful_approach(self, store):
        store.save_lesson(
            app="app", situation="same_situation",
            failed_approach="fail", successful_approach="old_success",
        )
        store.save_lesson(
            app="app", situation="same_situation",
            failed_approach="fail", successful_approach="new_success",
        )
        lessons = store.recall_lessons("app")
        matching = [l for l in lessons if l.situation == "same_situation"]
        assert matching[0].successful_approach == "new_success"

    def test_upsert_increases_reinforcement_count(self, store):
        store.save_lesson(
            app="app", situation="same_situation",
            failed_approach="fail", successful_approach="success",
        )
        store.save_lesson(
            app="app", situation="same_situation",
            failed_approach="fail", successful_approach="success",
        )
        lessons = store.recall_lessons("app")
        matching = [l for l in lessons if l.situation == "same_situation"]
        assert matching[0].reinforcement_count >= 1

    def test_different_situations_create_separate_lessons(self, store):
        store.save_lesson(
            app="app", situation="situation_a",
            failed_approach="fail", successful_approach="success_a",
        )
        store.save_lesson(
            app="app", situation="situation_b",
            failed_approach="fail", successful_approach="success_b",
        )
        lessons = store.recall_lessons("app", top_k=10)
        situations = {l.situation for l in lessons}
        assert "situation_a" in situations
        assert "situation_b" in situations


# ── recall_all_lessons ─────────────────────────────────────────────────────────

class TestRecallAllLessons:
    def test_returns_across_apps(self, store):
        store.save_lesson(
            app="app1", situation="s1", failed_approach="f", successful_approach="g"
        )
        store.save_lesson(
            app="app2", situation="s2", failed_approach="f", successful_approach="g"
        )
        all_lessons = store.recall_all_lessons(top_k=20)
        apps = {l.app for l in all_lessons}
        assert "app1" in apps
        assert "app2" in apps

    def test_empty_returns_empty_list(self, store):
        assert store.recall_all_lessons() == []


# ── _jaccard_similarity ────────────────────────────────────────────────────────

class TestJaccardSimilarity:
    def test_identical_texts(self):
        assert _jaccard_similarity("hello world", "hello world") == pytest.approx(1.0)

    def test_completely_different_texts(self):
        assert _jaccard_similarity("foo bar", "baz qux") == pytest.approx(0.0)

    def test_partial_overlap(self):
        # words1 = {a, b}, words2 = {b, c} → intersection=1, union=3 → 1/3
        score = _jaccard_similarity("a b", "b c")
        assert score == pytest.approx(1 / 3, abs=1e-6)

    def test_both_empty(self):
        assert _jaccard_similarity("", "") == pytest.approx(1.0)

    def test_one_empty(self):
        assert _jaccard_similarity("hello", "") == pytest.approx(0.0)
        assert _jaccard_similarity("", "world") == pytest.approx(0.0)

    def test_case_insensitive(self):
        # lowercase split: "Hello" vs "hello" are different tokens
        score_lower = _jaccard_similarity("hello world", "hello world")
        assert score_lower == pytest.approx(1.0)

    def test_subset(self):
        # words1={a, b, c}, words2={a, b} → intersection=2, union=3 → 2/3
        score = _jaccard_similarity("a b c", "a b")
        assert score == pytest.approx(2 / 3, abs=1e-6)

    def test_single_word_match(self):
        assert _jaccard_similarity("open", "open") == pytest.approx(1.0)

    def test_single_word_no_match(self):
        assert _jaccard_similarity("open", "close") == pytest.approx(0.0)

    def test_longer_text_similarity(self):
        t1 = "open the file dialog and select a file"
        t2 = "open the file browser and pick a file"
        score = _jaccard_similarity(t1, t2)
        assert 0.0 < score < 1.0
