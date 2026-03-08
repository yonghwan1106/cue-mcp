"""Tests for cue_mcp.safety — platform-independent."""

from __future__ import annotations

import time

import pytest

from cue_mcp.safety import EmergencyStop, SafetyGate
from cue_mcp.types import SafetyLevel


# ── SafetyGate: instantiation ──────────────────────────────────────────────────

class TestSafetyGateInstantiation:
    def test_default_instantiation(self):
        gate = SafetyGate()
        assert gate is not None

    def test_custom_blocked(self):
        gate = SafetyGate(blocked_commands=["evil_cmd"])
        decision = gate.check("type", text="evil_cmd something")
        assert decision.level is SafetyLevel.BLOCKED

    def test_custom_confirmation(self):
        gate = SafetyGate(confirmation_patterns=["confirm_this"])
        decision = gate.check("click", text="confirm_this action")
        assert decision.level is SafetyLevel.NEEDS_CONFIRMATION

    def test_custom_sensitive_paths(self):
        gate = SafetyGate(sensitive_paths=["/custom/secret/"])
        decision = gate.check("type", text="/custom/secret/file.txt")
        assert decision.level is SafetyLevel.NEEDS_CONFIRMATION


# ── SafetyGate: SAFE actions ───────────────────────────────────────────────────

class TestSafetyGateSafe:
    def setup_method(self):
        self.gate = SafetyGate()

    def test_simple_click_is_safe(self):
        decision = self.gate.check("click", text="", key="")
        assert decision.level is SafetyLevel.SAFE

    def test_plain_type_is_safe(self):
        decision = self.gate.check("type", text="hello world")
        assert decision.level is SafetyLevel.SAFE

    def test_scroll_is_safe(self):
        decision = self.gate.check("scroll", text="", key="")
        assert decision.level is SafetyLevel.SAFE

    def test_empty_action_is_safe(self):
        decision = self.gate.check("", text="", key="")
        assert decision.level is SafetyLevel.SAFE

    def test_safe_reason_present(self):
        decision = self.gate.check("click")
        assert decision.reason != ""

    def test_safe_pattern_matched_is_none(self):
        decision = self.gate.check("click")
        assert decision.pattern_matched is None


# ── SafetyGate: BLOCKED actions ────────────────────────────────────────────────

class TestSafetyGateBlocked:
    def setup_method(self):
        self.gate = SafetyGate()

    def test_rm_rf_is_blocked(self):
        decision = self.gate.check("type", text="rm -rf /")
        assert decision.level is SafetyLevel.BLOCKED

    def test_rm_rf_pattern_matched(self):
        decision = self.gate.check("type", text="rm -rf /home/user")
        assert decision.pattern_matched == "rm -rf"

    def test_format_c_is_blocked(self):
        decision = self.gate.check("type", text="format c:")
        assert decision.level is SafetyLevel.BLOCKED

    def test_format_c_case_insensitive(self):
        decision = self.gate.check("type", text="FORMAT C:")
        assert decision.level is SafetyLevel.BLOCKED

    def test_drop_table_is_blocked(self):
        decision = self.gate.check("type", text="DROP TABLE users")
        assert decision.level is SafetyLevel.BLOCKED

    def test_drop_database_is_blocked(self):
        decision = self.gate.check("type", text="DROP DATABASE mydb")
        assert decision.level is SafetyLevel.BLOCKED

    def test_delete_from_is_blocked(self):
        decision = self.gate.check("type", text="DELETE FROM accounts")
        assert decision.level is SafetyLevel.BLOCKED

    def test_truncate_is_blocked(self):
        decision = self.gate.check("type", text="TRUNCATE logs")
        assert decision.level is SafetyLevel.BLOCKED

    def test_sudo_rm_is_blocked(self):
        decision = self.gate.check("type", text="sudo rm /etc/important")
        assert decision.level is SafetyLevel.BLOCKED

    def test_mkfs_is_blocked(self):
        decision = self.gate.check("type", text="mkfs.ext4 /dev/sda")
        assert decision.level is SafetyLevel.BLOCKED

    def test_shutdown_is_blocked(self):
        decision = self.gate.check("type", text="shutdown -h now")
        assert decision.level is SafetyLevel.BLOCKED

    def test_blocked_reason_present(self):
        decision = self.gate.check("type", text="rm -rf /")
        assert "rm -rf" in decision.reason

    def test_blocked_via_key(self):
        decision = self.gate.check("hotkey", text="", key="rm -rf /")
        assert decision.level is SafetyLevel.BLOCKED

    def test_del_s_q_is_blocked(self):
        decision = self.gate.check("type", text="del /s /q C:\\important")
        assert decision.level is SafetyLevel.BLOCKED


# ── SafetyGate: NEEDS_CONFIRMATION ────────────────────────────────────────────

class TestSafetyGateNeedsConfirmation:
    def setup_method(self):
        self.gate = SafetyGate()

    def test_send_needs_confirmation(self):
        decision = self.gate.check("click", text="send email")
        assert decision.level is SafetyLevel.NEEDS_CONFIRMATION

    def test_submit_needs_confirmation(self):
        decision = self.gate.check("click", text="submit form")
        assert decision.level is SafetyLevel.NEEDS_CONFIRMATION

    def test_delete_word_needs_confirmation(self):
        decision = self.gate.check("click", text="delete file")
        assert decision.level is SafetyLevel.NEEDS_CONFIRMATION

    def test_publish_needs_confirmation(self):
        decision = self.gate.check("click", text="publish article")
        assert decision.level is SafetyLevel.NEEDS_CONFIRMATION

    def test_purchase_needs_confirmation(self):
        decision = self.gate.check("click", text="purchase item")
        assert decision.level is SafetyLevel.NEEDS_CONFIRMATION

    def test_pay_needs_confirmation(self):
        decision = self.gate.check("click", text="pay now")
        assert decision.level is SafetyLevel.NEEDS_CONFIRMATION

    def test_email_needs_confirmation(self):
        decision = self.gate.check("click", text="email report")
        assert decision.level is SafetyLevel.NEEDS_CONFIRMATION

    def test_tweet_needs_confirmation(self):
        decision = self.gate.check("click", text="tweet this")
        assert decision.level is SafetyLevel.NEEDS_CONFIRMATION

    def test_pattern_matched_present(self):
        decision = self.gate.check("click", text="send message")
        assert decision.pattern_matched == "send"

    def test_sensitive_path_etc(self):
        decision = self.gate.check("type", text="/etc/passwd")
        assert decision.level is SafetyLevel.NEEDS_CONFIRMATION

    def test_sensitive_path_ssh(self):
        decision = self.gate.check("type", text="~/.ssh/id_rsa")
        assert decision.level is SafetyLevel.NEEDS_CONFIRMATION

    def test_sensitive_path_windows(self):
        decision = self.gate.check("type", text="C:\\Windows\\System32\\config")
        assert decision.level is SafetyLevel.NEEDS_CONFIRMATION

    def test_confirmation_word_boundary(self):
        # "sender" should NOT trigger "send" (word boundary \b)
        decision = self.gate.check("type", text="sender address")
        assert decision.level is SafetyLevel.SAFE

    def test_remove_triggers_confirmation(self):
        decision = self.gate.check("click", text="remove item")
        assert decision.level is SafetyLevel.NEEDS_CONFIRMATION


# ── SafetyGate: priority (BLOCKED before NEEDS_CONFIRMATION) ──────────────────

class TestSafetyGatePriority:
    def test_blocked_takes_priority_over_confirmation(self):
        gate = SafetyGate()
        # "rm -rf" is blocked, "delete" is confirmation-level
        decision = gate.check("type", text="rm -rf delete folder")
        assert decision.level is SafetyLevel.BLOCKED


# ── EmergencyStop ──────────────────────────────────────────────────────────────

class TestEmergencyStop:
    def test_instantiation(self):
        es = EmergencyStop()
        assert es.max_repeated == 5
        assert es.timeout == 600

    def test_custom_parameters(self):
        es = EmergencyStop(max_repeated=3, timeout=60)
        assert es.max_repeated == 3
        assert es.timeout == 60

    def test_check_returns_true_initially(self):
        es = EmergencyStop(max_repeated=5)
        ok, reason = es.check("click_button")
        assert ok is True
        assert reason == ""

    def test_repeated_action_triggers_stop(self):
        es = EmergencyStop(max_repeated=3)
        for _ in range(2):
            ok, _ = es.check("same_action")
            assert ok is True
        # 3rd repeat should trigger
        ok, reason = es.check("same_action")
        assert ok is False
        assert "same_action" in reason

    def test_varied_actions_do_not_trigger(self):
        es = EmergencyStop(max_repeated=3)
        for i in range(10):
            ok, _ = es.check(f"action_{i}")
            assert ok is True

    def test_reset_clears_history(self):
        es = EmergencyStop(max_repeated=3)
        for _ in range(3):
            es.check("same_action")
        es.reset()
        # After reset, should allow same action again
        ok, _ = es.check("same_action")
        assert ok is True

    def test_start_clears_history(self):
        es = EmergencyStop(max_repeated=3)
        for _ in range(3):
            es.check("same_action")
        es.start()
        ok, _ = es.check("same_action")
        assert ok is True

    def test_different_action_resets_run(self):
        es = EmergencyStop(max_repeated=3)
        es.check("action_a")
        es.check("action_a")
        es.check("action_b")  # breaks the run
        # Now two more a's should not immediately trigger
        ok, _ = es.check("action_a")
        assert ok is True


# ── SafetyGate.check_emergency ─────────────────────────────────────────────────

class TestSafetyGateEmergency:
    def test_check_emergency_safe_initially(self):
        gate = SafetyGate()
        gate.start_session()
        decision = gate.check_emergency("click_ok")
        assert decision.level is SafetyLevel.SAFE

    def test_check_emergency_blocks_on_repeat(self):
        gate = SafetyGate()
        gate.start_session()
        action = "click_submit"
        for _ in range(4):
            gate.check_emergency(action)
        decision = gate.check_emergency(action)
        assert decision.level is SafetyLevel.BLOCKED

    def test_reset_session_clears_emergency(self):
        gate = SafetyGate()
        gate.start_session()
        for _ in range(5):
            gate.check_emergency("repeat")
        gate.reset_session()
        decision = gate.check_emergency("repeat")
        assert decision.level is SafetyLevel.SAFE
