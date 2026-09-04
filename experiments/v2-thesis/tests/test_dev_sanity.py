"""Development sanity tests. Not evaluation. No holdout fixtures."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

from lib.constants import BASELINE_ORDER, HYPOTHESES, MAX_PROBE_TYPES, MAX_REQUESTS
from lib.localize import localize
from lib.outcomes import classify_pair, summarize
from lib.selector import select_probe
from lib.engine import apply_outcome, seed_remaining


class PolicyTests(unittest.TestCase):
    def test_budget_frozen(self) -> None:
        self.assertEqual(MAX_PROBE_TYPES, 5)
        self.assertEqual(MAX_REQUESTS, 30)
        self.assertEqual(len(BASELINE_ORDER), 5)

    def test_no_healthy_default(self) -> None:
        d = localize({"remaining": set(HYPOTHESES), "executed": [], "pair_outcomes": [], "stop_reason": "IN_PROGRESS"})
        self.assertNotEqual(d["STATUS"], "HEALTHY")
        self.assertEqual(d["USEFUL_FAILURE_FAMILY"], "UNKNOWN")

    def test_noisy_not_boolean_true_false(self) -> None:
        control = {
            "n": 3,
            "http_2xx": 3,
            "http_err": 0,
            "tool_calls": 3,
            "schema_valid": 1,
            "schema_invalid": 2,
            "timeout": 0,
            "malformed_args": 0,
            "raw_tool_syntax": 0,
        }
        broken = {
            "n": 3,
            "http_2xx": 3,
            "http_err": 0,
            "tool_calls": 3,
            "schema_valid": 0,
            "schema_invalid": 3,
            "timeout": 0,
            "malformed_args": 0,
            "raw_tool_syntax": 0,
        }
        c = classify_pair(control, broken)
        self.assertEqual(c["outcome"], "UNSTABLE")
        self.assertTrue(c["CONTROL_UNSTABLE"])
        self.assertTrue(c["BROKEN_CONSISTENT_FAILURE"])

    def test_http_400_pair_is_malformed_not_timeout_protocol_guess(self) -> None:
        control = {
            "n": 3,
            "http_2xx": 3,
            "http_err": 0,
            "tool_calls": 3,
            "schema_valid": 3,
            "schema_invalid": 0,
            "timeout": 0,
            "malformed_args": 0,
            "raw_tool_syntax": 0,
        }
        broken = {
            "n": 3,
            "http_2xx": 0,
            "http_err": 3,
            "tool_calls": 0,
            "schema_valid": 0,
            "schema_invalid": 0,
            "timeout": 0,
            "malformed_args": 0,
            "raw_tool_syntax": 0,
        }
        c = classify_pair(control, broken)
        self.assertEqual(c["outcome"], "MALFORMED")

    def test_timeout_is_timeout_outcome(self) -> None:
        control = {
            "n": 3,
            "http_2xx": 3,
            "http_err": 0,
            "tool_calls": 3,
            "schema_valid": 3,
            "schema_invalid": 0,
            "timeout": 0,
            "malformed_args": 0,
            "raw_tool_syntax": 0,
        }
        broken = {
            "n": 3,
            "http_2xx": 0,
            "http_err": 0,
            "tool_calls": 0,
            "schema_valid": 0,
            "schema_invalid": 0,
            "timeout": 3,
            "malformed_args": 0,
            "raw_tool_syntax": 0,
        }
        c = classify_pair(control, broken)
        self.assertEqual(c["outcome"], "TIMEOUT")

    def test_seed_http_error_keeps_protocol(self) -> None:
        remaining, elim, _ = seed_remaining({"n": 3, "http_err": 3, "tool_calls": 0})
        self.assertIn("H_PROTOCOL", remaining)
        self.assertNotIn("H_STREAM", remaining)

    def test_selector_changes_after_stream_eliminated(self) -> None:
        all_h = set(HYPOTHESES)
        first = select_probe(all_h, set())
        self.assertIsNotNone(first["probe"])
        after = apply_outcome(all_h, "P_STREAM_ISO", "PASS")
        second = select_probe(after, {"P_STREAM_ISO"})
        self.assertIsNotNone(second["probe"])
        # After stream PASS, H_STREAM should be gone from remaining_if
        self.assertNotIn("H_STREAM", after)
        self.assertNotEqual(second["probe"], "P_STREAM_ISO")

    def test_unique_fail_localizes_family(self) -> None:
        d = localize(
            {
                "remaining": {"H_SCHEMA"},
                "executed": ["P_SCHEMA_FLAT"],
                "pair_outcomes": [{"outcome": "FAIL", "control": {"n": 3, "tool_calls": 3}, "broken": {"n": 3, "tool_calls": 3}}],
                "supporting": ["schema split"],
                "contradicting": ["internal unknown"],
                "eliminated": ["H_STREAM"],
                "stop_reason": "LOCALIZED",
            }
        )
        self.assertEqual(d["USEFUL_FAILURE_FAMILY"], "SCHEMA_HANDLING_FAILURE")
        self.assertEqual(d["STATUS"], "UNHEALTHY")
        self.assertEqual(d["SUSPECTED_INTERNAL_CAUSE"], "UNKNOWN")
        self.assertEqual(d["ROOT_CAUSE_CONFIDENCE"], "LOW")

    def test_summarize_keeps_counts(self) -> None:
        s = summarize(
            [
                {"http_status": 200, "tool_calls_present": True, "arguments_schema_valid": True, "timeout": False},
                {"http_status": 200, "tool_calls_present": True, "arguments_schema_valid": False, "timeout": False},
                {"http_status": 200, "tool_calls_present": False, "arguments_schema_valid": False, "timeout": False},
            ]
        )
        self.assertEqual(s["n"], 3)
        self.assertEqual(s["tool_calls"], 2)
        self.assertEqual(s["schema_valid"], 1)
        self.assertEqual(s["schema_invalid"], 2)


if __name__ == "__main__":
    unittest.main()
