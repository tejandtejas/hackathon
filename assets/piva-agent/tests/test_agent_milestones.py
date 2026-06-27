"""Tests for agent milestone emission and _emit_milestone logic."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

import logging
import pytest
from agent import _emit_milestone, get_system_prompt, get_model_name, get_temperature


class TestEmitMilestone:
    def test_m1_achieved_on_due_query(self, caplog):
        with caplog.at_level(logging.INFO, logger="agent"):
            _emit_milestone("show products due for counting", "here are the overdue products")
        assert any("M1.achieved" in r.message for r in caplog.records)

    def test_m1_missed_on_error_response(self, caplog):
        with caplog.at_level(logging.INFO, logger="agent"):
            _emit_milestone("show overdue products", "error: connection failed")
        assert any("M1.missed" in r.message for r in caplog.records)

    def test_m2_achieved_on_create_query(self, caplog):
        with caplog.at_level(logging.INFO, logger="agent"):
            _emit_milestone("create documents for warehouse 0001", "documents have been created successfully")
        assert any("M2.achieved" in r.message for r in caplog.records)

    def test_m2_missed_on_pending_confirmation(self, caplog):
        with caplog.at_level(logging.INFO, logger="agent"):
            _emit_milestone("create inventory documents", "please confirm to proceed")
        assert any("M2.missed" in r.message for r in caplog.records)

    def test_m4_achieved_on_difference_query(self, caplog):
        with caplog.at_level(logging.INFO, logger="agent"):
            _emit_milestone("show stock differences for warehouse 0001", "here is the counted vs booked summary")
        assert any("M4.achieved" in r.message for r in caplog.records)

    def test_m4_missed_on_error(self, caplog):
        with caplog.at_level(logging.INFO, logger="agent"):
            _emit_milestone("show difference summary", "failed to retrieve booked quantities")
        assert any("M4.missed" in r.message for r in caplog.records)

    def test_m5_achieved_on_post_query(self, caplog):
        with caplog.at_level(logging.INFO, logger="agent"):
            _emit_milestone("post inventory differences", "differences have been posted successfully")
        assert any("M5.achieved" in r.message for r in caplog.records)

    def test_m5_missed_on_pending_confirmation(self, caplog):
        with caplog.at_level(logging.INFO, logger="agent"):
            _emit_milestone("approve and post differences", "please confirm to proceed")
        assert any("M5.missed" in r.message for r in caplog.records)

    def test_m3_achieved_on_queue_query(self, caplog):
        with caplog.at_level(logging.INFO, logger="agent"):
            _emit_milestone("show documents in counting queue", "documents are queued for counting")
        assert any("M3.achieved" in r.message for r in caplog.records)

    def test_no_milestone_for_unrelated_query(self, caplog):
        with caplog.at_level(logging.INFO, logger="agent"):
            _emit_milestone("hello how are you", "I am doing well")
        milestone_logs = [r for r in caplog.records if "achieved" in r.message or "missed" in r.message]
        assert len(milestone_logs) == 0


class TestAgentDecorators:
    def test_model_name_returns_string(self):
        result = get_model_name()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_temperature_returns_float(self):
        result = get_temperature()
        assert isinstance(result, float)
        assert 0.0 <= result <= 1.0

    def test_system_prompt_contains_critical_rules(self):
        prompt = get_system_prompt()
        assert "PIVA" in prompt
        assert "confirmation" in prompt.lower() or "confirm" in prompt.lower()
        assert "Red" in prompt or "RED" in prompt or "red" in prompt.lower()

    def test_system_prompt_contains_cci_logic(self):
        prompt = get_system_prompt()
        assert "CCI" in prompt or "Cycle Counting" in prompt

    def test_system_prompt_contains_threshold_info(self):
        prompt = get_system_prompt()
        assert "2%" in prompt or "threshold" in prompt.lower()
