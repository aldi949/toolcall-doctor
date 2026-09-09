"""Holdout wording variants. Written after test_active_isolation.py.

These strings are intentionally not Phase-017/018 matcher phrases. Layer must
follow the isolation experiment, not the text.
"""
from __future__ import annotations

import pytest

from toolcall_doctor.adapter import MockRuntimeAdapter
from toolcall_doctor.localize import (
    INSUFFICIENT_EVIDENCE,
    LOCALIZED,
    PARSER_ORCHESTRATION,
    STRUCTURED_DECODING,
    UNKNOWN,
    localize,
)
from toolcall_doctor.outcome import MANIFESTED

HOLDOUT_PARSER_WORDINGS = (
    "upstream returned code T-88 while binding tools",
    "dispatch table miss on call envelope",
    "runtime refused to hydrate the instrumented payload",
)

HOLDOUT_GRAMMAR_WORDINGS = (
    "constraint compiler aborted at logits filter setup",
    "sampler rejected the production set before decode",
    "guided path returned E_DECODE_CONSTRAINT",
)


def _manifested() -> dict:
    return {
        "status": MANIFESTED,
        "observed": 1,
        "required": 1,
        "trials": 1,
        "probe_facts": {},
        "reason": "holdout manifested",
    }


def _loc(**extra) -> dict:
    bundle = {"outcome": _manifested(), "request": {"model": "m"}}
    bundle.update(extra)
    loc = localize(bundle)
    assert loc is not None
    return loc


@pytest.mark.parametrize("wording", HOLDOUT_PARSER_WORDINGS)
def test_holdout_parser_wording_follows_synthetic_failure(wording: str):
    loc = _loc(
        raw_responses=[{"status": 400, "text": wording}],
        runtime_adapter=MockRuntimeAdapter(parser_ok=False),
    )
    assert loc["status"] == LOCALIZED
    assert loc["layer"] == PARSER_ORCHESTRATION


@pytest.mark.parametrize("wording", HOLDOUT_PARSER_WORDINGS)
def test_holdout_parser_wording_does_not_win_when_probe_passes(wording: str):
    loc = _loc(
        raw_responses=[{"status": 400, "text": wording}],
        runtime_adapter=MockRuntimeAdapter(parser_ok=True),
    )
    assert loc["layer"] != PARSER_ORCHESTRATION


@pytest.mark.parametrize("wording", HOLDOUT_GRAMMAR_WORDINGS)
def test_holdout_grammar_wording_follows_on_off_pair(wording: str):
    loc = _loc(
        raw_responses=[{"status": 400, "text": wording}],
        runtime_adapter=MockRuntimeAdapter(
            structured_pair={"on": {"manifested": True}, "off": {"manifested": False}}
        ),
    )
    assert loc["status"] == LOCALIZED
    assert loc["layer"] == STRUCTURED_DECODING


@pytest.mark.parametrize("wording", HOLDOUT_GRAMMAR_WORDINGS)
def test_holdout_grammar_wording_alone_is_insufficient(wording: str):
    loc = _loc(raw_responses=[{"status": 400, "text": wording}])
    assert loc["status"] == INSUFFICIENT_EVIDENCE
    assert loc["layer"] == UNKNOWN
    assert loc["layer"] != STRUCTURED_DECODING
