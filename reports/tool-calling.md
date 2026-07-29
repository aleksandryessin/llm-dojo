# Report — suite `tool-calling`

Raw runs: `runs/20260729T173918Z-tool-calling.jsonl`

| Model | EN | RU | Δ EN→RU | mean latency |
|---|---|---|---|---|
| `qwen2.5:7b` | 1.00 (6/6) | 1.00 (6/6) | +0.00 | 0.9s |
| `llama3.2:3b` | 0.83 (5/6) | 0.83 (5/6) | +0.00 | 0.5s |
| `qwen3-vl:30b` | 1.00 (6/6) | 1.00 (6/6) | +0.00 | 3.0s |
| `gemma3:1b` | 0.00 (0/6) | 0.00 (0/6) | +0.00 | 0.2s |

## Failures

| Model | Case | Type | Why |
|---|---|---|---|
| `llama3.2:3b` | no_tool_general_en | no_tool | called ['get_dependencies'], expected ['(no tool)'] |
| `llama3.2:3b` | no_tool_general_ru | no_tool | called ['search_tickets'], expected ['(no tool)'] |
| `gemma3:1b` | simple_deps_en | simple | BadRequestError: Error code: 400 - {'error': {'message': 'registry.ollama.ai/library/gemma3:1b does not support tools', 'type': 'invalid_request_error', 'param': None, 'code': None}} |
| `gemma3:1b` | simple_deps_ru | simple | BadRequestError: Error code: 400 - {'error': {'message': 'registry.ollama.ai/library/gemma3:1b does not support tools', 'type': 'invalid_request_error', 'param': None, 'code': None}} |
| `gemma3:1b` | arg_extraction_en | arg_extraction | BadRequestError: Error code: 400 - {'error': {'message': 'registry.ollama.ai/library/gemma3:1b does not support tools', 'type': 'invalid_request_error', 'param': None, 'code': None}} |
| `gemma3:1b` | arg_extraction_ru | arg_extraction | BadRequestError: Error code: 400 - {'error': {'message': 'registry.ollama.ai/library/gemma3:1b does not support tools', 'type': 'invalid_request_error', 'param': None, 'code': None}} |
| `gemma3:1b` | multi_tool_en | multi_tool | BadRequestError: Error code: 400 - {'error': {'message': 'registry.ollama.ai/library/gemma3:1b does not support tools', 'type': 'invalid_request_error', 'param': None, 'code': None}} |
| `gemma3:1b` | multi_tool_ru | multi_tool | BadRequestError: Error code: 400 - {'error': {'message': 'registry.ollama.ai/library/gemma3:1b does not support tools', 'type': 'invalid_request_error', 'param': None, 'code': None}} |
| `gemma3:1b` | ticket_search_en | search | BadRequestError: Error code: 400 - {'error': {'message': 'registry.ollama.ai/library/gemma3:1b does not support tools', 'type': 'invalid_request_error', 'param': None, 'code': None}} |
| `gemma3:1b` | ticket_search_ru | search | BadRequestError: Error code: 400 - {'error': {'message': 'registry.ollama.ai/library/gemma3:1b does not support tools', 'type': 'invalid_request_error', 'param': None, 'code': None}} |
| `gemma3:1b` | no_tool_general_en | no_tool | BadRequestError: Error code: 400 - {'error': {'message': 'registry.ollama.ai/library/gemma3:1b does not support tools', 'type': 'invalid_request_error', 'param': None, 'code': None}} |
| `gemma3:1b` | no_tool_general_ru | no_tool | BadRequestError: Error code: 400 - {'error': {'message': 'registry.ollama.ai/library/gemma3:1b does not support tools', 'type': 'invalid_request_error', 'param': None, 'code': None}} |
| `gemma3:1b` | no_tool_offdomain_en | no_tool | BadRequestError: Error code: 400 - {'error': {'message': 'registry.ollama.ai/library/gemma3:1b does not support tools', 'type': 'invalid_request_error', 'param': None, 'code': None}} |
| `gemma3:1b` | no_tool_offdomain_ru | no_tool | BadRequestError: Error code: 400 - {'error': {'message': 'registry.ollama.ai/library/gemma3:1b does not support tools', 'type': 'invalid_request_error', 'param': None, 'code': None}} |
