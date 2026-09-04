"""Generic JSON Schema validation of returned tool arguments.

Does not encode a specific bug, model, runtime, or expected property names.
Uses jsonschema against the declared parameters schema from the request.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator


def _json_load_maybe(text: str | None) -> Any:
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def schema_depth(schema: Any, depth: int = 0) -> int:
    if not isinstance(schema, dict):
        return depth
    deepest = depth
    props = schema.get("properties")
    if isinstance(props, dict):
        for child in props.values():
            deepest = max(deepest, schema_depth(child, depth + 1))
    items = schema.get("items")
    if isinstance(items, dict):
        deepest = max(deepest, schema_depth(items, depth + 1))
    elif isinstance(items, list):
        for child in items:
            deepest = max(deepest, schema_depth(child, depth + 1))
    return deepest


def instance_depth(obj: Any, depth: int = 0) -> int:
    if isinstance(obj, dict) and obj:
        return max(instance_depth(v, depth + 1) for v in obj.values())
    if isinstance(obj, list) and obj:
        return max(instance_depth(v, depth + 1) for v in obj)
    return depth


def _parse_arguments(args: Any) -> tuple[Any, bool | None]:
    if args is None:
        return None, None
    if isinstance(args, dict):
        return args, True
    if isinstance(args, str):
        if args.strip() == "":
            return None, None
        try:
            return json.loads(args), True
        except json.JSONDecodeError:
            return args, False
    return args, False


def missing_required_paths(schema: Any, instance: Any, prefix: str = "") -> list[str]:
    missing: list[str] = []
    if not isinstance(schema, dict):
        return missing
    required = schema.get("required") or []
    inst = instance if isinstance(instance, dict) else {}
    for key in required:
        path = f"{prefix}.{key}" if prefix else key
        if not isinstance(inst, dict) or key not in inst:
            missing.append(path)
            continue
        props = schema.get("properties")
        if isinstance(props, dict) and key in props:
            missing.extend(missing_required_paths(props[key], inst.get(key), path))
    return missing


def extra_property_paths(schema: Any, instance: Any, prefix: str = "") -> list[str]:
    extra: list[str] = []
    if not isinstance(schema, dict) or not isinstance(instance, dict):
        return extra
    props = schema.get("properties")
    allowed = set(props.keys()) if isinstance(props, dict) else set()
    additional = schema.get("additionalProperties", True)
    for key, value in instance.items():
        path = f"{prefix}.{key}" if prefix else key
        if allowed and key not in allowed and additional is False:
            extra.append(path)
        elif isinstance(props, dict) and key in props:
            extra.extend(extra_property_paths(props[key], value, path))
    return extra


def declared_schemas_from_request(request: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for tool in request.get("tools") or []:
        if not isinstance(tool, dict):
            continue
        fn = tool.get("function") if isinstance(tool.get("function"), dict) else tool
        if not isinstance(fn, dict):
            continue
        params = fn.get("parameters")
        if isinstance(params, dict):
            out.append({"name": fn.get("name"), "schema": params})
    return out


def collect_tool_argument_instances(obj: Any, found: list[dict[str, Any]]) -> None:
    if isinstance(obj, dict):
        tcs = obj.get("tool_calls")
        if isinstance(tcs, list):
            for tc in tcs:
                if not isinstance(tc, dict):
                    continue
                fn = tc.get("function") if isinstance(tc.get("function"), dict) else tc
                if not isinstance(fn, dict):
                    continue
                parsed, json_ok = _parse_arguments(fn.get("arguments"))
                found.append(
                    {
                        "name": fn.get("name") or tc.get("name"),
                        "arguments": parsed,
                        "arguments_json_valid": json_ok,
                    }
                )
        for v in obj.values():
            collect_tool_argument_instances(v, found)
    elif isinstance(obj, list):
        for item in obj:
            collect_tool_argument_instances(item, found)


def validate_response(request: dict[str, Any], body: Any) -> dict[str, Any]:
    declared = declared_schemas_from_request(request)
    schema_by_name = {d["name"]: d["schema"] for d in declared if d.get("name")}
    max_declared_depth = max((schema_depth(d["schema"]) for d in declared), default=0)
    instances: list[dict[str, Any]] = []
    collect_tool_argument_instances(body, instances)
    per_call = []
    all_schema_valid = True
    any_call = False
    missing_all: list[str] = []
    extra_all: list[str] = []
    max_arg_depth = 0
    for inst in instances:
        any_call = True
        name = inst.get("name")
        schema = schema_by_name.get(name) or (declared[0]["schema"] if len(declared) == 1 else None)
        args = inst.get("arguments")
        json_ok = inst.get("arguments_json_valid")
        errors: list[str] = []
        schema_ok = False
        missing: list[str] = []
        extra: list[str] = []
        depth = instance_depth(args) if isinstance(args, (dict, list)) else 0
        max_arg_depth = max(max_arg_depth, depth)
        if json_ok is False:
            all_schema_valid = False
            errors.append("arguments_not_json")
        elif schema is None:
            all_schema_valid = False
            errors.append("no_declared_schema_for_tool")
        elif not isinstance(args, dict):
            all_schema_valid = False
            errors.append("arguments_not_object")
        else:
            validator = Draft7Validator(schema)
            errors = [e.message for e in validator.iter_errors(args)]
            schema_ok = len(errors) == 0
            if not schema_ok:
                all_schema_valid = False
            missing = missing_required_paths(schema, args)
            extra = extra_property_paths(schema, args)
            missing_all.extend(missing)
            extra_all.extend(extra)
        per_call.append(
            {
                "name": name,
                "arguments_json_valid": json_ok,
                "arguments_schema_valid": schema_ok,
                "schema_errors": errors,
                "missing_required_fields": missing,
                "unexpected_fields_when_additional_false": extra,
                "returned_argument_depth": depth,
                "tool_name_declared": name in schema_by_name if name else False,
            }
        )
    return {
        "declared_schema_count": len(declared),
        "declared_schema_depth": max_declared_depth,
        "returned_argument_depth": max_arg_depth,
        "tool_calls_found": any_call,
        "arguments_schema_valid": (all_schema_valid and any_call) if any_call else None,
        "missing_required_fields": missing_all,
        "unexpected_fields_when_additional_false": extra_all,
        "nested_structure_valid": (
            True
            if not any_call
            else (all_schema_valid and (max_arg_depth >= 1 if max_declared_depth >= 2 else True))
        )
        if any_call
        else None,
        "per_call": per_call,
    }


def validate_files(request_path: Path, body_path: Path) -> dict[str, Any]:
    request = _json_load_maybe(request_path.read_text(encoding="utf-8")) or {}
    body = _json_load_maybe(body_path.read_text(encoding="utf-8", errors="replace"))
    result = validate_response(request, body)
    result["request_path"] = str(request_path)
    result["body_path"] = str(body_path)
    return result


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--request-json", required=True)
    parser.add_argument("--body-json", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = validate_files(Path(args.request_json), Path(args.body_json))
    Path(args.out).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
