"""Oracle: HTTP_400_UNMARSHAL_TYPE_ARRAY_INTO_STRING. No issue IDs. No fixes."""
from __future__ import annotations

IDENTITY = "HTTP_400_UNMARSHAL_TYPE_ARRAY_INTO_STRING"
NEEDLE = "cannot unmarshal array into Go struct field .tools.function.parameters.properties.type of type string"


def evaluate(http_status: int | None, body_text: str | None) -> dict:
    text = body_text or ""
    fail = http_status == 400 and NEEDLE in text
    return {
        "oracle": "FAIL" if fail else "PASS",
        "failure_identity": IDENTITY if fail else None,
        "http_status": http_status,
    }
