# Report — suite `tool-calling`

Raw runs: `runs/20260729T161141Z-tool-calling.jsonl`

| Model | EN | RU | Δ EN→RU | mean latency |
|---|---|---|---|---|
| `qwen2.5:7b` | 1.00 (6/6) | 1.00 (6/6) | +0.00 | 1.0s |
| `llama3.2:3b` | 0.83 (5/6) | 0.83 (5/6) | +0.00 | 1.1s |

## Failures

| Model | Case | Type | Why |
|---|---|---|---|
| `llama3.2:3b` | no_tool_general_en | no_tool | called ['get_dependencies'], expected ['(no tool)'] |
| `llama3.2:3b` | no_tool_general_ru | no_tool | called ['search_tickets'], expected ['(no tool)'] |
