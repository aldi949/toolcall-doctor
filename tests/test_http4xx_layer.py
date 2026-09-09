from __future__ import annotations

import json
from pathlib import Path

from toolcall_doctor.localize import (
    INSUFFICIENT_EVIDENCE,
    LOCALIZED,
    REQUEST_PRECONDITION,
    STRUCTURED_DECODING,
    TRANSPORT_API,
    UNKNOWN,
    localize,
)
from toolcall_doctor.outcome import MANIFESTED, assert_no_causal_fields

FORBIDDEN_KEYS = frozenset({"root_cause", "cause_confirmed", "fix", "remediation"})
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _manifested() -> dict:
    return {
        "status": MANIFESTED,
        "observed": 1,
        "required": 1,
        "trials": 1,
        "probe_facts": {},
        "reason": "test manifested",
    }


def _all_keys(obj) -> set[str]:
    keys: set[str] = set()
    if isinstance(obj, dict):
        keys.update(obj)
        for v in obj.values():
            keys.update(_all_keys(v))
    elif isinstance(obj, list):
        for v in obj:
            keys.update(_all_keys(v))
    return keys


def _assert_safe(loc: dict) -> None:
    assert set(loc) == {"status", "layer", "confidence", "evidence", "excluded_layers", "next_probe"}
    assert_no_causal_fields(loc)
    assert FORBIDDEN_KEYS.isdisjoint(_all_keys(loc))
    blob = json.dumps(loc)
    for key in FORBIDDEN_KEYS:
        assert f'"{key}"' not in blob


def _localize_4xx(status: int | None, text: str, error: str | None = None, **extra) -> dict:
    loc = localize(
        {
            "outcome": _manifested(),
            "request": {"model": "local", "messages": [{"role": "user", "content": "hi"}]},
            "runtime_config": extra.pop("runtime_config", {}),
            "raw_responses": [{"status": status, "text": text, "error": error}],
            **extra,
        }
    )
    assert loc is not None
    _assert_safe(loc)
    return loc


def test_a_grammar_400_wording_alone_is_not_transport_or_structured():
    loc = _localize_4xx(400, json.dumps({"error": {"code": 400, "message": "failed to parse grammar"}}))
    assert loc["layer"] != TRANSPORT_API
    assert loc["layer"] != STRUCTURED_DECODING
    assert loc["status"] == INSUFFICIENT_EVIDENCE


def test_b_unsupported_parameter_free_text_is_not_precondition():
    loc = _localize_4xx(400, '{"error":{"message":"unsupported parameter: response_format"}}')
    assert loc["layer"] != REQUEST_PRECONDITION
    assert loc["status"] == INSUFFICIENT_EVIDENCE


def test_c_unknown_model_free_text_is_not_precondition():
    loc = _localize_4xx(400, "model not found")
    assert loc["layer"] != REQUEST_PRECONDITION
    assert loc["status"] == INSUFFICIENT_EVIDENCE


def test_d_auth_401_403_protocol_status_is_request_precondition():
    loc401 = _localize_4xx(401, "Unauthorized: authentication required")
    assert loc401["status"] == LOCALIZED
    assert loc401["layer"] == REQUEST_PRECONDITION
    loc403 = _localize_4xx(403, '{"error":"invalid api key"}')
    assert loc403["status"] == LOCALIZED
    assert loc403["layer"] == REQUEST_PRECONDITION


def test_e_connection_refused_is_transport_api():
    loc = _localize_4xx(None, "", error="ConnectError('[Errno 111] Connection refused')")
    assert loc["status"] == LOCALIZED
    assert loc["layer"] == TRANSPORT_API


def test_f_timeout_without_http_response_is_transport_api():
    loc = _localize_4xx(None, "", error="ReadTimeout('timed out')")
    assert loc["status"] == LOCALIZED
    assert loc["layer"] == TRANSPORT_API


def test_g_generic_400_is_not_transport_api():
    loc = _localize_4xx(400, '{"error":{"message":"Bad Request"}}')
    assert loc["layer"] != TRANSPORT_API
    assert loc["status"] == INSUFFICIENT_EVIDENCE
    assert loc["layer"] == UNKNOWN


def test_h_conflicting_400_wording_without_probes_is_insufficient():
    loc = _localize_4xx(400, "failed to parse grammar; unknown model 'foo'")
    assert loc["status"] == INSUFFICIENT_EVIDENCE
    assert loc["layer"] == UNKNOWN


def test_i_grammar_wording_does_not_override_generic_http_to_structured():
    loc = _localize_4xx(
        400,
        json.dumps(
            {
                "error": {
                    "code": 400,
                    "message": "Bad Request: failed to parse grammar",
                    "type": "invalid_request_error",
                }
            }
        ),
    )
    assert loc["layer"] != TRANSPORT_API
    assert loc["layer"] != STRUCTURED_DECODING
    assert TRANSPORT_API in loc["excluded_layers"]


def test_k_http4xx_localization_has_no_causal_fields():
    loc = _localize_4xx(400, "failed to parse grammar")
    _assert_safe(loc)
    loc2 = _localize_4xx(400, "Bad Request")
    _assert_safe(loc2)


def test_grammar_400_archived_shape_wording_is_not_sufficient():
    raw = json.loads((FIXTURES / "grammar_400_response.json").read_text(encoding="utf-8"))
    assert raw["http_status"] == 400
    body_text = json.dumps(raw["body"], separators=(",", ":"))
    assert "failed to parse grammar" in body_text
    loc = _localize_4xx(raw["http_status"], body_text)
    assert loc["layer"] != TRANSPORT_API
    assert loc["layer"] != STRUCTURED_DECODING
    assert loc["status"] == INSUFFICIENT_EVIDENCE
    _assert_safe(loc)


def test_protocol_error_code_is_request_precondition():
    loc = _localize_4xx(400, json.dumps({"error": {"code": "model_not_found", "message": "nope"}}))
    assert loc["status"] == LOCALIZED
    assert loc["layer"] == REQUEST_PRECONDITION
