"""Automated tests from development cases only. Do not import holdout artifacts."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from doctor_frozen.doctor import diagnose
from doctor_frozen.validate_schema import schema_depth, validate_response

FIXTURES = Path(__file__).resolve().parent / "fixtures"

REQUIRED_KEYS = {
    "STATUS",
    "OBSERVABLE_FAILURE_DIMENSION",
    "USEFUL_FAILURE_FAMILY",
    "LOCALIZATION_CONFIDENCE",
    "INTERNAL_ROOT_CAUSE",
    "ROOT_CAUSE_CONFIDENCE",
    "SUPPORTING_EVIDENCE",
    "CONTRADICTING_EVIDENCE",
    "ELIMINATED_ALTERNATIVES",
    "UNRESOLVED_ALTERNATIVES",
    "NEXT_BEST_PROBE",
}


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def assert_diagnosis_shape(test: unittest.TestCase, d: dict) -> None:
    for key in REQUIRED_KEYS:
        test.assertIn(key, d)
        test.assertIsNotNone(d[key])
    test.assertEqual(d["INTERNAL_ROOT_CAUSE"], "UNKNOWN")
    test.assertEqual(d["ROOT_CAUSE_CONFIDENCE"], "LOW")
    test.assertIsInstance(d["SUPPORTING_EVIDENCE"], list)
    test.assertIsInstance(d["CONTRADICTING_EVIDENCE"], list)
    test.assertIsInstance(d["ELIMINATED_ALTERNATIVES"], list)
    test.assertIsInstance(d["UNRESOLVED_ALTERNATIVES"], list)
    test.assertTrue(d["NEXT_BEST_PROBE"])


class DevelopmentCaseTests(unittest.TestCase):
    def test_dev001_stream_family_high_localization_unknown_internal(self) -> None:
        d = diagnose(load("dev001_control.json"), load("dev001_broken.json"))
        assert_diagnosis_shape(self, d)
        self.assertEqual(d["STATUS"], "UNHEALTHY")
        self.assertEqual(d["OBSERVABLE_FAILURE_DIMENSION"], "D_STREAM")
        self.assertEqual(d["USEFUL_FAILURE_FAMILY"], "STREAM_DEPENDENT_FAILURE")
        self.assertEqual(d["LOCALIZATION_CONFIDENCE"], "HIGH")
        self.assertEqual(d["MATCHED_RULE"], "R2")

    def test_dev002_tool_choice_family_high_localization_unknown_internal(self) -> None:
        d = diagnose(load("dev002_control.json"), load("dev002_broken.json"))
        assert_diagnosis_shape(self, d)
        self.assertEqual(d["STATUS"], "UNHEALTHY")
        self.assertEqual(d["OBSERVABLE_FAILURE_DIMENSION"], "D_TOOL_CHOICE")
        self.assertEqual(d["USEFUL_FAILURE_FAMILY"], "TOOL_CHOICE_CONSTRAINT_FAILURE")
        self.assertEqual(d["LOCALIZATION_CONFIDENCE"], "HIGH")
        self.assertEqual(d["MATCHED_RULE"], "R3")

    def test_dev003_schema_family_high_localization_unknown_internal(self) -> None:
        d = diagnose(load("dev003_control.json"), load("dev003_broken.json"))
        assert_diagnosis_shape(self, d)
        self.assertEqual(d["STATUS"], "UNHEALTHY")
        self.assertEqual(d["OBSERVABLE_FAILURE_DIMENSION"], "D_SCHEMA_STRUCTURE")
        self.assertEqual(d["USEFUL_FAILURE_FAMILY"], "SCHEMA_DEPENDENT_FAILURE")
        self.assertEqual(d["LOCALIZATION_CONFIDENCE"], "HIGH")
        self.assertEqual(d["MATCHED_RULE"], "R4")
        self.assertNotEqual(d["INTERNAL_ROOT_CAUSE"], "SCHEMA_TRANSFORMER")


class CalibrationTests(unittest.TestCase):
    def test_timeout_is_not_protocol_failure(self) -> None:
        control = {
            "http_status": 200,
            "streaming": False,
            "tool_calls_present": True,
            "raw_tool_syntax_present": False,
            "timeout": False,
            "tool_choice_kind": "auto",
            "arguments_schema_valid": True,
            "declared_schema_depth": 1,
        }
        broken = {
            "http_status": None,
            "streaming": False,
            "tool_calls_present": False,
            "raw_tool_syntax_present": False,
            "timeout": True,
            "tool_choice_kind": "auto",
            "arguments_schema_valid": None,
            "declared_schema_depth": 1,
        }
        d = diagnose(control, broken)
        self.assertEqual(d["USEFUL_FAILURE_FAMILY"], "UNKNOWN")
        self.assertEqual(d["OBSERVABLE_FAILURE_DIMENSION"], "D_TIMEOUT")
        self.assertEqual(d["LOCALIZATION_CONFIDENCE"], "LOW")
        self.assertEqual(d["MATCHED_RULE"], "R7")
        self.assertNotEqual(d["USEFUL_FAILURE_FAMILY"], "PROTOCOL_FAILURE")

    def test_http_5xx_is_protocol_failure(self) -> None:
        control = {
            "http_status": 200,
            "streaming": False,
            "tool_calls_present": True,
            "timeout": False,
            "tool_choice_kind": "auto",
        }
        broken = {
            "http_status": 500,
            "streaming": False,
            "tool_calls_present": False,
            "timeout": False,
            "tool_choice_kind": "auto",
        }
        d = diagnose(control, broken)
        self.assertEqual(d["USEFUL_FAILURE_FAMILY"], "PROTOCOL_FAILURE")
        self.assertEqual(d["LOCALIZATION_CONFIDENCE"], "MEDIUM")
        self.assertEqual(d["INTERNAL_ROOT_CAUSE"], "UNKNOWN")

    def test_healthy_identical_successful_probes(self) -> None:
        obs = {
            "http_status": 200,
            "streaming": False,
            "tool_choice_kind": "auto",
            "tool_calls_present": True,
            "raw_tool_syntax_present": False,
            "arguments_schema_valid": True,
            "declared_schema_depth": 1,
            "timeout": False,
        }
        d = diagnose(obs, dict(obs))
        self.assertEqual(d["STATUS"], "HEALTHY")
        self.assertEqual(d["USEFUL_FAILURE_FAMILY"], "HEALTHY")
        self.assertEqual(d["LOCALIZATION_CONFIDENCE"], "HIGH")
        self.assertEqual(d["INTERNAL_ROOT_CAUSE"], "UNKNOWN")
        self.assertEqual(d["ROOT_CAUSE_CONFIDENCE"], "LOW")

    def test_healthy_stream_true_when_tool_calls_preserved(self) -> None:
        control = {
            "http_status": 200,
            "streaming": False,
            "tool_calls_present": True,
            "raw_tool_syntax_present": False,
            "timeout": False,
            "arguments_schema_valid": True,
            "declared_schema_depth": 1,
        }
        broken = {
            "http_status": 200,
            "streaming": True,
            "tool_calls_present": True,
            "raw_tool_syntax_present": False,
            "timeout": False,
            "arguments_schema_valid": True,
            "declared_schema_depth": 1,
        }
        d = diagnose(control, broken)
        self.assertEqual(d["USEFUL_FAILURE_FAMILY"], "HEALTHY")

    def test_unexplained_tool_loss_is_unknown_not_healthy(self) -> None:
        control = {
            "http_status": 200,
            "streaming": False,
            "tool_calls_present": True,
            "raw_tool_syntax_present": False,
            "timeout": False,
            "tool_choice_kind": "auto",
        }
        broken = {
            "http_status": 200,
            "streaming": False,
            "tool_calls_present": False,
            "raw_tool_syntax_present": False,
            "timeout": False,
            "tool_choice_kind": "auto",
        }
        d = diagnose(control, broken)
        self.assertNotEqual(d["USEFUL_FAILURE_FAMILY"], "HEALTHY")
        self.assertEqual(d["USEFUL_FAILURE_FAMILY"], "UNKNOWN")

    def test_two_changed_variables_ambiguous(self) -> None:
        control = {
            "http_status": 200,
            "streaming": False,
            "tool_calls_present": True,
            "raw_tool_syntax_present": False,
            "timeout": False,
            "tool_choice_kind": "auto",
            "declared_schema_depth": 1,
            "arguments_schema_valid": True,
        }
        broken = {
            "http_status": 200,
            "streaming": True,
            "tool_calls_present": False,
            "raw_tool_syntax_present": True,
            "timeout": False,
            "tool_choice_kind": "none",
            "declared_schema_depth": 2,
            "arguments_schema_valid": False,
        }
        d = diagnose(control, broken)
        self.assertEqual(d["USEFUL_FAILURE_FAMILY"], "AMBIGUOUS")
        self.assertEqual(d["LOCALIZATION_CONFIDENCE"], "LOW")

    def test_ignores_forbidden_identity_keys(self) -> None:
        control = load("dev001_control.json")
        broken = load("dev001_broken.json")
        control = {
            **control,
            "issue_number": 5796,
            "github_url": "https://github.com/example/issue",
            "ground_truth": "streaming_parser",
            "model": "secret-model-key",
        }
        broken = {**broken, "known_fix": "upgrade"}
        d = diagnose(control, broken)
        self.assertEqual(d["USEFUL_FAILURE_FAMILY"], "STREAM_DEPENDENT_FAILURE")
        blob = json.dumps(d)
        self.assertNotIn("5796", blob)
        self.assertNotIn("github.com", blob)
        self.assertNotIn("secret-model-key", blob)


class ValidatorGenericTests(unittest.TestCase):
    def test_schema_depth_nested_vs_flat(self) -> None:
        flat = {"type": "object", "properties": {"n": {"type": "integer"}}}
        nested = {
            "type": "object",
            "properties": {"button_press": {"type": "object", "properties": {"n": {"type": "integer"}}}},
        }
        self.assertEqual(schema_depth(flat), 1)
        self.assertEqual(schema_depth(nested), 2)

    def test_validate_response_does_not_hardcode_property_names(self) -> None:
        request = {
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "widget",
                        "parameters": {
                            "type": "object",
                            "properties": {"payload": {"type": "object", "properties": {"k": {"type": "string"}}}},
                            "required": ["payload"],
                        },
                    },
                }
            ]
        }
        body = {
            "message": {
                "tool_calls": [
                    {"function": {"name": "widget", "arguments": "{\"k\": \"x\"}"}}
                ]
            }
        }
        result = validate_response(request, body)
        self.assertFalse(result["arguments_schema_valid"])
        self.assertIn("payload", result["missing_required_fields"][0])


if __name__ == "__main__":
    unittest.main()
