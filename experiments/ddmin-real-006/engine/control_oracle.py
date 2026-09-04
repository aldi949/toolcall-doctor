"""Control: flat schema should not emit stringified list."""
from __future__ import annotations


def control_ok(payload: dict, ora: dict, facts: dict) -> bool:
    if ora.get("http_status") != 200:
        return False
    if not ora.get("tool_call_present"):
        return False
    if ora.get("tool_name") != facts.get("tool_name", "execute_service"):
        return False
    args = ora.get("arguments")
    if not isinstance(args, dict):
        return False
    if ora.get("list_is_str"):
        return False
    entity = facts.get("entity", "light.buro_deckenlampe_2")
    eid = args.get("entity_id")
    svc = args.get("service")
    return eid == entity or (isinstance(eid, str) and isinstance(svc, str))
