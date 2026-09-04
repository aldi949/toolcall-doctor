#!/bin/sh
curl -sS -D - http://127.0.0.1:11434/v1/chat/completions -H "Content-Type: application/json" -d @payload.json
