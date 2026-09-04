"""Filesystem safety: never rmtree a generic work/ or unrelated user files."""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from toolcall_doctor.cli import (
    OWNED_MARKER_NAME,
    OWNED_WORKDIR_NAME,
    DoesNotReproduce,
    main,
    minimize,
    prepare_owned_work_dir,
)
from toolcall_doctor.contract import parse_contract


def _tool_response() -> dict:
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call1",
                            "type": "function",
                            "function": {
                                "name": "execute_service",
                                "arguments": json.dumps({"list": '["x"]'}),
                            },
                        }
                    ],
                }
            }
        ]
    }


def _handler(request: httpx.Request) -> httpx.Response:
    if request.url.path.endswith("/api/version"):
        return httpx.Response(200, json={"version": "0.4.6"})
    if request.url.path.endswith("/api/tags"):
        return httpx.Response(200, json={"models": [{"name": "llama3.2:3b"}]})
    return httpx.Response(200, json=_tool_response())


@pytest.fixture
def mock_client():
    transport = httpx.MockTransport(_handler)
    with httpx.Client(transport=transport, timeout=10.0) as client:
        yield client


def _ok_request() -> dict:
    return {
        "model": "llama3.2:3b",
        "stream": False,
        "temperature": 0,
        "messages": [{"role": "user", "content": "x"}],
        "tools": [
            {
                "function": {
                    "name": "execute_service",
                    "parameters": {"properties": {"list": {"type": "array"}}},
                }
            }
        ],
    }


def _ok_contract() -> dict:
    return parse_contract(
        {
            "failure": {"condition": "type_is", "path": "arguments.list", "value": "string"},
            "preserve": [
                {"type": "tool_name", "value": "execute_service"},
                {"type": "contains", "value": "x"},
                {"type": "schema_type", "property": "list", "value": "array"},
            ],
        }
    )


def test_existing_work_directory_survives(tmp_path: Path, mock_client: httpx.Client):
    user = tmp_path / "work" / "user-file.txt"
    user.parent.mkdir(parents=True)
    user.write_text("keep-me\n", encoding="utf-8")
    minimize(
        _ok_request(),
        _ok_contract(),
        tmp_path,
        n=1,
        url="http://127.0.0.1/v1/chat/completions",
        client=mock_client,
        skip_probe=True,
    )
    assert user.is_file()
    assert user.read_text(encoding="utf-8") == "keep-me\n"


def test_existing_output_directory_unrelated_files_survive(tmp_path: Path, mock_client: httpx.Client):
    notes = tmp_path / "notes.txt"
    notes.write_text("user notes\n", encoding="utf-8")
    nested = tmp_path / "keep" / "data.bin"
    nested.parent.mkdir()
    nested.write_bytes(b"abc")
    minimize(
        _ok_request(),
        _ok_contract(),
        tmp_path,
        n=1,
        url="http://127.0.0.1/v1/chat/completions",
        client=mock_client,
        skip_probe=True,
    )
    assert notes.read_text(encoding="utf-8") == "user notes\n"
    assert nested.read_bytes() == b"abc"


def test_tool_owned_workdir_can_be_cleaned(tmp_path: Path, mock_client: httpx.Client):
    first = prepare_owned_work_dir(tmp_path)
    stale = first / "stale.txt"
    stale.write_text("old\n", encoding="utf-8")
    assert (first / OWNED_MARKER_NAME).is_file()
    second = prepare_owned_work_dir(tmp_path)
    assert second == first
    assert not stale.exists()
    assert (second / OWNED_MARKER_NAME).is_file()
    minimize(
        _ok_request(),
        _ok_contract(),
        tmp_path,
        n=1,
        url="http://127.0.0.1/v1/chat/completions",
        client=mock_client,
        skip_probe=True,
    )
    assert (tmp_path / OWNED_WORKDIR_NAME / OWNED_MARKER_NAME).is_file()


def test_failure_path_does_not_delete_user_files(tmp_path: Path):
    def text_only(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "ok"}}]})

    user = tmp_path / "work" / "user-file.txt"
    user.parent.mkdir(parents=True)
    user.write_text("keep-me\n", encoding="utf-8")
    extra = tmp_path / "other.txt"
    extra.write_text("also-keep\n", encoding="utf-8")
    request = {"model": "llama3.2:3b", "messages": [{"role": "user", "content": "hi"}]}
    contract = parse_contract({"failure": {"condition": "has_tool_call"}, "preserve": []})
    transport = httpx.MockTransport(text_only)
    with httpx.Client(transport=transport, timeout=10.0) as client:
        with pytest.raises(DoesNotReproduce):
            minimize(
                request,
                contract,
                tmp_path,
                n=1,
                url="http://127.0.0.1/v1/chat/completions",
                client=client,
                skip_probe=True,
            )
    assert user.read_text(encoding="utf-8") == "keep-me\n"
    assert extra.read_text(encoding="utf-8") == "also-keep\n"


def test_default_output_does_not_delete_cwd_work(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    work_file = tmp_path / "work" / "user-file.txt"
    work_file.parent.mkdir()
    work_file.write_text("cwd-work\n", encoding="utf-8")
    req = tmp_path / "request.json"
    con = tmp_path / "contract.json"
    req.write_text("{}", encoding="utf-8")
    con.write_text('{"failure":{"condition":"nope"}}', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert main(["minimize", str(req), "--contract", str(con)]) == 1
    assert work_file.is_file()
    assert work_file.read_text(encoding="utf-8") == "cwd-work\n"


def test_refuses_to_replace_unowned_dot_toolcall_doctor(tmp_path: Path):
    alien = tmp_path / OWNED_WORKDIR_NAME
    alien.mkdir()
    (alien / "mine.txt").write_text("hands off\n", encoding="utf-8")
    with pytest.raises(Exception, match="refusing to replace"):
        prepare_owned_work_dir(tmp_path)
    assert (alien / "mine.txt").read_text(encoding="utf-8") == "hands off\n"
