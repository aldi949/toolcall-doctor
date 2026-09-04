"""Candidate catalog for screening. Doctor never imports this file."""
from __future__ import annotations

MODEL = "llama3.2:3b"
NATIVE = "http://127.0.0.1:11434/api/chat"
COMPAT = "http://127.0.0.1:11434/v1/chat/completions"

DISQUALIFIED = {
    "ollama/ollama#5796",
    "ollama/ollama#17921",
    "ollama/ollama#13472",
    "ollama/ollama#8095",
    "ollama/ollama#10164",
    "ollama/ollama#11444",
    "ollama/ollama#9802",
    "ollama/ollama#9055",
}

LOCKED_ORDER = [
    "ollama/ollama#5990",
    "ollama/ollama#6127",
    "ollama/ollama#6155",
    "ollama/ollama#6713",
    "ollama/ollama#6980",
    "ollama/ollama#7051",
    "ollama/ollama#7572",
    "ollama/ollama#7778",
    "ollama/ollama#7881",
    "ollama/ollama#8222",
    "ollama/ollama#8337",
    "ollama/ollama#8421",
    "ollama/ollama#8517",
    "ollama/ollama#8588",
    "ollama/ollama#9437",
    "ollama/ollama#9632",
    "ollama/ollama#9680",
    "ollama/ollama#9941",
    "ollama/ollama#10976",
    "ollama/ollama#11407",
    "ollama/ollama#11805",
    "ollama/ollama#12288",
    "ollama/ollama#12557",
    "ollama/ollama#13705",
    "ollama/ollama#14958",
    "ollama/ollama#14967",
    "ollama/ollama#15539",
    "ollama/ollama#16932",
    "ollama/ollama#17429",
    "ollama/ollama#17597",
    "ollama/ollama#18051",
    "ggml-org/llama.cpp#20260",
    "ggml-org/llama.cpp#24807",
    "ggml-org/llama.cpp#24863",
    "ggml-org/llama.cpp#25746",
    "ggml-org/llama.cpp#26359",
    "ggml-org/llama.cpp#27217",
    "vllm-project/vllm#45167",
    "vllm-project/vllm#47137",
    "vllm-project/vllm#48294",
    "vllm-project/vllm#43713",
    "vllm-project/vllm#54808",
    "vllm-project/vllm#55080",
    "sgl-project/sglang#31915",
    "sgl-project/sglang#32286",
    "sgl-project/sglang#37283",
    "sgl-project/sglang#37634",
    "sgl-project/sglang#37430",
]


def _tool(name: str, desc: str, params: dict) -> dict:
    return {"type": "function", "function": {"name": name, "description": desc, "parameters": params}}


def _chat(user: str, tools: list, extra: dict | None = None, url_kind: str = "native") -> dict:
    body = {
        "model": MODEL,
        "stream": False,
        "messages": [{"role": "user", "content": user}],
        "tools": tools,
    }
    if extra:
        body.update(extra)
    return {"url_kind": url_kind, "payload": body}


WEATHER = _tool(
    "get_weather",
    "Get the current weather for a city",
    {"type": "object", "properties": {"city": {"type": "string", "description": "City name"}}, "required": ["city"]},
)

# Screening recipes. Doctor does not see identity or gt_*.
CATALOG: dict[str, dict] = {
    "ollama/ollama#5990": {
        "runtime": "ollama",
        "screen": "http_error",
        "need_model": None,
        "recipe": _chat(
            "Hello",
            [_tool("search_files", "Search files", {
                "type": "object",
                "properties": {"query": {"type": ["string", "null"], "description": "nullable query"}},
                "required": ["query"],
            })],
            url_kind="compat",
        ),
        "expect_http": 400,
        "gt_family": "SCHEMA_HANDLING_FAILURE",
        "gt_quality": "GT-B",
        "gt_note": "properties.type array unmarshals as string; HTTP 400. PR #9434.",
    },
    "ollama/ollama#6127": {
        "runtime": "ollama",
        "screen": "wrong_model",
        "need_model": "llama3.1",
        "gt_family": "TOOL_CHOICE_CONSTRAINT_FAILURE",
        "gt_quality": "GT-C",
        "gt_note": "Reported llama3.1 always uses tool; llama3.1 not installed.",
    },
    "ollama/ollama#6155": {
        "runtime": "ollama",
        "screen": "nested_schema_http_ok_then_behavior",
        "need_model": None,
        "recipe": _chat(
            "Turn off light.buro_deckenlampe_2 using execute_service.",
            [_tool("execute_service", "Execute a Home Assistant service", {
                "type": "object",
                "properties": {
                    "list": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "service": {"type": "string"},
                                "entity_id": {"type": "string"},
                            },
                        },
                    }
                },
                "required": ["list"],
            })],
        ),
        "gt_family": "SCHEMA_HANDLING_FAILURE",
        "gt_quality": "GT-B",
        "gt_note": "Nested/array tool parameters not represented in the Go struct; double-encoding on OpenAI path.",
    },
    "ollama/ollama#6713": {"runtime": "ollama", "screen": "wrong_model", "need_model": "mistral-nemo", "gt_family": "PROTOCOL_OR_ADAPTER_FAILURE", "gt_quality": "GT-D", "gt_note": "Mistral-Nemo OpenAI tools; model not installed."},
    "ollama/ollama#6980": {
        "runtime": "ollama",
        "screen": "no_tools_when_prompted",
        "need_model": None,
        "recipe": _chat("Call get_weather for Paris right now. Do not answer in prose.", [WEATHER]),
        "gt_family": "BASE_TOOL_CALL_FAILURE",
        "gt_quality": "GT-D",
        "gt_note": "Generic 'tools not working' without a pinned mechanism.",
    },
    "ollama/ollama#7051": {"runtime": "ollama", "screen": "wrong_model", "need_model": "qwen2.5", "gt_family": "MODEL_OR_TEMPLATE_FAILURE", "gt_quality": "GT-C", "gt_note": "Qwen 2.5 Maybe-pattern; model not installed."},
    "ollama/ollama#7572": {
        "runtime": "ollama",
        "screen": "compat_no_tools",
        "need_model": None,
        "recipe": _chat("Call get_weather for Paris right now. Do not answer in prose.", [WEATHER], url_kind="compat"),
        "gt_family": "PROTOCOL_OR_ADAPTER_FAILURE",
        "gt_quality": "GT-D",
        "gt_note": "OpenAI API tool calling reported broken; treat as adapter if native works and compat does not.",
    },
    "ollama/ollama#7778": {
        "runtime": "ollama",
        "screen": "tool_choice_required_ignored",
        "need_model": None,
        "recipe": _chat("Say hello.", [WEATHER], extra={"tool_choice": "required"}, url_kind="compat"),
        "gt_family": "TOOL_CHOICE_CONSTRAINT_FAILURE",
        "gt_quality": "GT-B",
        "gt_note": "tool_choice required documented as having no effect.",
    },
    "ollama/ollama#7881": {
        "runtime": "ollama",
        "screen": "compat_missing_index",
        "need_model": None,
        "recipe": _chat("Call get_weather for Paris.", [WEATHER], url_kind="compat"),
        "gt_family": "PROTOCOL_OR_ADAPTER_FAILURE",
        "gt_quality": "GT-B",
        "gt_note": "OpenAI-compat tool_calls missing index field.",
    },
    "ollama/ollama#8222": {
        "runtime": "ollama",
        "screen": "http_error_or_strip",
        "need_model": None,
        "recipe": _chat(
            "Look up account ACC-1.",
            [_tool("lookup", "Lookup", {
                "type": "object",
                "$defs": {"Acc": {"type": "string", "minLength": 3}},
                "properties": {"account": {"$ref": "#/$defs/Acc"}},
                "required": ["account"],
            })],
            url_kind="compat",
        ),
        "gt_family": "SCHEMA_HANDLING_FAILURE",
        "gt_quality": "GT-B",
        "gt_note": "Parameters struct cannot carry full JSON Schema; $ref/$defs is the richness the issue asked for.",
    },
    "ollama/ollama#8337": {
        "runtime": "ollama",
        "screen": "cannot_manifest_contract",
        "need_model": None,
        "gt_family": "BASE_TOOL_CALL_FAILURE",
        "gt_quality": "GT-C",
        "gt_note": "Cannot get tool call and message in same response; no binary fail contract without a paired healthy channel.",
    },
    "ollama/ollama#8421": {
        "runtime": "ollama",
        "screen": "tool_choice_none_still_calls",
        "need_model": None,
        "recipe": _chat(
            "You must call get_weather for Paris. Do not reply in prose.",
            [WEATHER],
            extra={"tool_choice": "none"},
            url_kind="compat",
        ),
        "gt_family": "TOOL_CHOICE_CONSTRAINT_FAILURE",
        "gt_quality": "GT-B",
        "gt_note": "tool_choice ignored on OpenAI layer.",
    },
    "ollama/ollama#8517": {"runtime": "ollama", "screen": "wrong_model", "need_model": "deepseek-r1", "gt_family": "MODEL_OR_TEMPLATE_FAILURE", "gt_quality": "GT-C", "gt_note": "DeepSeek-R1 distillates; model not installed."},
    "ollama/ollama#8588": {"runtime": "ollama", "screen": "wrong_model", "need_model": "qwen2.5", "gt_family": "MODEL_OR_TEMPLATE_FAILURE", "gt_quality": "GT-D", "gt_note": "Qwen tools; model not installed."},
    "ollama/ollama#9437": {"runtime": "ollama", "screen": "wrong_model", "need_model": "phi4-mini", "gt_family": "MODEL_OR_TEMPLATE_FAILURE", "gt_quality": "GT-C", "gt_note": "phi4-mini; model not installed."},
    "ollama/ollama#9632": {
        "runtime": "ollama",
        "screen": "stream_drops_tools",
        "need_model": None,
        "recipe": _chat("Call get_weather for Paris. Do not answer in prose.", [WEATHER], extra={"stream": True}),
        "gt_family": "STREAM_DEPENDENT_FAILURE",
        "gt_quality": "GT-C",
        "gt_note": "Streaming tool calling reported broken; 0.4.6 claimed a fix for #5796 so this may be NON_MANIFESTING.",
    },
    "ollama/ollama#9680": {"runtime": "ollama", "screen": "wrong_model", "need_model": "gemma3", "gt_family": "MODEL_OR_TEMPLATE_FAILURE", "gt_quality": "GT-C", "gt_note": "gemma3; model not installed."},
    "ollama/ollama#9941": {"runtime": "ollama", "screen": "wrong_model", "need_model": "gemma3", "gt_family": "MODEL_OR_TEMPLATE_FAILURE", "gt_quality": "GT-C", "gt_note": "Gemma3 OpenAI tools; model not installed."},
    "ollama/ollama#10976": {"runtime": "ollama", "screen": "wrong_model", "need_model": "qwen3", "gt_family": "REASONING_DEPENDENT_FAILURE", "gt_quality": "GT-B", "gt_note": "Thinking + tools empty output on qwen3; model not installed."},
    "ollama/ollama#11407": {
        "runtime": "ollama",
        "screen": "stream_drops_tools",
        "need_model": None,
        "recipe": _chat("Call get_weather for Paris. Do not answer in prose.", [WEATHER], extra={"stream": True}),
        "gt_family": "STREAM_DEPENDENT_FAILURE",
        "gt_quality": "GT-C",
        "gt_note": "Streaming sometimes breaks tool calling.",
    },
    "ollama/ollama#11805": {
        "runtime": "ollama",
        "screen": "extra_nesting_arguments",
        "need_model": None,
        "recipe": _chat(
            "My name is John",
            [_tool("ExtractName", "Extract the name", {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            })],
        ),
        "gt_family": "TOOL_PARSER",
        "gt_quality": "GT-B",
        "gt_note": "arguments envelope duplicated; useful family TOOL_PARSER maps to BASE_TOOL_CALL_FAILURE or SCHEMA; score as BASE_TOOL_CALL_FAILURE.",
        "gt_family_score": "BASE_TOOL_CALL_FAILURE",
    },
    "ollama/ollama#12288": {
        "runtime": "ollama",
        "screen": "http_error",
        "need_model": None,
        "recipe": _chat(
            "Hello",
            [_tool("lookup", "Lookup", {
                "type": "object",
                "properties": {"q": {"type": "string"}},
                "required": None,
            })],
            url_kind="compat",
        ),
        "expect_http": 400,
        "gt_family": "SCHEMA_HANDLING_FAILURE",
        "gt_quality": "GT-B",
        "gt_note": "required:null rejected by Go []string field; related #18051.",
    },
    "ollama/ollama#12557": {
        "runtime": "ollama",
        "screen": "stream_drops_tools",
        "need_model": None,
        "recipe": _chat("Call get_weather for Paris. Do not answer in prose.", [WEATHER], extra={"stream": True}),
        "gt_family": "STREAM_DEPENDENT_FAILURE",
        "gt_quality": "GT-C",
        "gt_note": "Tool calling + streaming issue.",
    },
    "ollama/ollama#13705": {"runtime": "ollama", "screen": "wrong_model", "need_model": "ministral", "gt_family": "TOOL_PARSER", "gt_family_score": "BASE_TOOL_CALL_FAILURE", "gt_quality": "GT-A", "gt_note": "Ministral nested JSON parser 500; model not installed. Merged brace-count fix."},
    "ollama/ollama#14958": {
        "runtime": "ollama",
        "screen": "large_system_drops_tools",
        "need_model": None,
        "recipe": {
            "url_kind": "native",
            "payload": {
                "model": MODEL,
                "stream": False,
                "messages": [
                    {"role": "system", "content": ("Context. " * 400)},
                    {"role": "user", "content": "Call get_weather for Paris. Do not answer in prose."},
                ],
                "tools": [WEATHER],
            },
        },
        "gt_family": "MODEL_OR_TEMPLATE_FAILURE",
        "gt_quality": "GT-C",
        "gt_note": "Tool calls drop with large system prompts.",
    },
    "ollama/ollama#14967": {
        "runtime": "ollama",
        "screen": "tool_choice_required_ignored",
        "need_model": None,
        "recipe": _chat(
            "Call get-orders-at-risk-count now.",
            [_tool("GetOrdersAtRiskCount", "Count orders at risk", {"type": "object", "properties": {}})],
            extra={"tool_choice": "required"},
            url_kind="compat",
        ),
        "gt_family": "TOOL_CHOICE_CONSTRAINT_FAILURE",
        "gt_quality": "GT-C",
        "gt_note": "required + name mismatch silently stops; also tests required honoring.",
    },
    "ollama/ollama#15539": {"runtime": "ollama", "screen": "wrong_model", "need_model": "gemma4", "gt_family": "REASONING_DEPENDENT_FAILURE", "gt_quality": "GT-B", "gt_note": "gemma4 parser + think:false; model not installed."},
    "ollama/ollama#16932": {"runtime": "ollama", "screen": "wrong_model", "need_model": "devstral", "gt_family": "TOOL_PARSER", "gt_family_score": "BASE_TOOL_CALL_FAILURE", "gt_quality": "GT-B", "gt_note": "Parameter named name dropped on Mistral-format models; model not installed."},
    "ollama/ollama#17429": {
        "runtime": "ollama",
        "screen": "hang_on_tool_role",
        "need_model": None,
        "recipe": {
            "url_kind": "native",
            "payload": {
                "model": MODEL,
                "stream": False,
                "messages": [
                    {"role": "user", "content": "What is the weather in Paris?"},
                    {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [{"function": {"name": "get_weather", "arguments": {"city": "Paris"}}}],
                    },
                    {"role": "tool", "content": "{\"temp\": 18}"},
                    {"role": "user", "content": "Thanks, summarize."},
                ],
                "tools": [WEATHER],
            },
        },
        "gt_family": "MULTI_TURN_STATE_FAILURE",
        "gt_quality": "GT-B",
        "gt_note": "Hang when history includes role:tool.",
    },
    "ollama/ollama#17597": {
        "runtime": "ollama",
        "screen": "enum_not_enforced",
        "need_model": None,
        "recipe": _chat(
            "Call set_account with account equal to ACC-999-XYZ even though that is not in the enum.",
            [_tool("set_account", "Set account", {
                "type": "object",
                "properties": {"account": {"type": "string", "enum": ["ONLY-VALID-ACCOUNT"]}},
                "required": ["account"],
            })],
        ),
        "gt_family": "GRAMMAR_CONSTRAINT_FAILURE",
        "gt_quality": "GT-C",
        "gt_note": "enum reaches the model but is not decoding-enforced. Manifest only if a tool call violates the enum.",
    },
    "ollama/ollama#18051": {
        "runtime": "ollama",
        "screen": "http_error",
        "need_model": None,
        "recipe": _chat(
            "calculate area of a circle with radius 5",
            [_tool("calculate_area", "calculate area of a shape", {
                "type": "object",
                "properties": {
                    "shape": {"type": "string", "enum": ["circle", "rectangle", "triangle"]},
                    "dimensions": {
                        "type": "object",
                        "properties": {
                            "radius": {"type": "number"},
                            "length": {"type": "number"},
                            "width": {"type": "number"},
                        },
                        "required": {"circle": ["radius"], "rectangle": ["length", "width"]},
                    },
                },
                "required": ["shape", "dimensions"],
            })],
            url_kind="compat",
        ),
        "expect_http": 400,
        "gt_family": "SCHEMA_HANDLING_FAILURE",
        "gt_quality": "GT-B",
        "gt_note": "Nested required object unmarshals as []string; HTTP 400. PR #18140.",
    },
}

for _cid in [
    "ggml-org/llama.cpp#20260",
    "ggml-org/llama.cpp#24807",
    "ggml-org/llama.cpp#24863",
    "ggml-org/llama.cpp#25746",
    "ggml-org/llama.cpp#26359",
    "ggml-org/llama.cpp#27217",
]:
    CATALOG[_cid] = {
        "runtime": "llama.cpp",
        "screen": "runtime_down",
        "gt_family": "UNKNOWN",
        "gt_quality": "GT-B",
        "gt_note": "llama-server not running; 4GB VRAM laptop cannot host the reported models.",
    }

for _cid in [
    "vllm-project/vllm#45167",
    "vllm-project/vllm#47137",
    "vllm-project/vllm#48294",
    "vllm-project/vllm#43713",
    "vllm-project/vllm#54808",
    "vllm-project/vllm#55080",
]:
    CATALOG[_cid] = {
        "runtime": "vllm",
        "screen": "runtime_down",
        "gt_family": "STREAM_DEPENDENT_FAILURE" if "47137" in _cid or "48294" in _cid else "BASE_TOOL_CALL_FAILURE",
        "gt_quality": "GT-A" if _cid.endswith(("45167", "48294")) else "GT-B",
        "gt_note": "vLLM not installed/running; Docker/WSL unavailable.",
    }

for _cid in [
    "sgl-project/sglang#31915",
    "sgl-project/sglang#32286",
    "sgl-project/sglang#37283",
    "sgl-project/sglang#37634",
    "sgl-project/sglang#37430",
]:
    CATALOG[_cid] = {
        "runtime": "sglang",
        "screen": "runtime_down",
        "gt_family": "STREAM_DEPENDENT_FAILURE",
        "gt_quality": "GT-B",
        "gt_note": "SGLang not installed/running; Docker/WSL unavailable.",
    }

# Fix 11805 score family
CATALOG["ollama/ollama#11805"]["gt_family"] = "BASE_TOOL_CALL_FAILURE"
CATALOG["ollama/ollama#13705"]["gt_family"] = "BASE_TOOL_CALL_FAILURE"
CATALOG["ollama/ollama#16932"]["gt_family"] = "BASE_TOOL_CALL_FAILURE"
