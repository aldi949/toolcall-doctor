# Reproduction verdict

RELATED FAILURE REPRODUCED

Control: 3/3 STABLE — structured tool_calls under tool_choice=auto, stream=false
Broken: 3/3 STABLE — structured tool_calls under tool_choice=none, stream=false

Not ORIGINAL: original issue used Ollama 0.32.15, macOS, qwen3.8:27b-mlx. This run used Ollama 0.4.6, Windows 11, llama3.2:3b.

The documented inverse of #17921 (`none` still calls tools) matched on every replicate. The primary “Say hello” + named tool_choice curl was not the scored pair.
