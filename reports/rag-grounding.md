# Report — suite `rag-grounding`

Raw runs: `runs/20260730T-rag-grounding-all4.jsonl`

| Model | EN | RU | Δ EN→RU | mean latency |
|---|---|---|---|---|
| `qwen2.5:7b` | 0.78 (7/9) | 0.11 (1/9) | -0.67 | 1.6s |
| `llama3.2:3b` | 0.67 (6/9) | 0.33 (3/9) | -0.33 | 1.4s |
| `gemma3:1b` | 0.89 (8/9) | 0.00 (0/9) | -0.89 | 0.8s |
| `qwen3-vl:30b` | 0.89 (8/9) | 0.56 (5/9) | -0.33 | 6.9s |

## Failures

| Model | Case | Type | Why |
|---|---|---|---|
| `qwen2.5:7b` | uv_what_en | answerable | missing all expected facts ['Rust', 'faster than pip'] |
| `qwen2.5:7b` | uv_what_ru | answerable | refused on an answerable question |
| `qwen2.5:7b` | langgraph_what_ru | answerable | missing all expected facts ['агент', 'оркестр', 'stateful'] |
| `qwen2.5:7b` | ragas_what_en | answerable | refused on an answerable question |
| `qwen2.5:7b` | ragas_what_ru | answerable | refused on an answerable question |
| `qwen2.5:7b` | ollama_run_ru | answerable | missing all expected facts ['ollama run'] |
| `qwen2.5:7b` | ollama_chat_api_ru | answerable | refused on an answerable question |
| `qwen2.5:7b` | off_capital_ru | unanswerable | wrong language |
| `qwen2.5:7b` | off_kafka_ru | unanswerable | answered instead of refusing |
| `qwen2.5:7b` | off_pricing_ru | unanswerable | wrong language |
| `llama3.2:3b` | vllm_throughput_ru | answerable | wrong language |
| `llama3.2:3b` | uv_what_en | answerable | missing all expected facts ['Rust', 'faster than pip'] |
| `llama3.2:3b` | uv_what_ru | answerable | refused on an answerable question |
| `llama3.2:3b` | ragas_what_ru | answerable | missing all expected facts ['оцен', 'evaluat'] |
| `llama3.2:3b` | ollama_run_en | answerable | missing all expected facts ['ollama run'] |
| `llama3.2:3b` | ollama_run_ru | answerable | refused on an answerable question |
| `llama3.2:3b` | ollama_chat_api_en | answerable | missing all expected facts ['/api/chat'] |
| `llama3.2:3b` | ollama_chat_api_ru | answerable | refused on an answerable question |
| `llama3.2:3b` | off_pricing_ru | unanswerable | wrong language |
| `gemma3:1b` | vllm_throughput_ru | answerable | wrong language |
| `gemma3:1b` | uv_what_en | answerable | missing all expected facts ['Rust', 'faster than pip'] |
| `gemma3:1b` | uv_what_ru | answerable | missing all expected facts ['Rust', 'быстрее pip', 'faster than pip'] |
| `gemma3:1b` | langgraph_what_ru | answerable | missing all expected facts ['агент', 'оркестр', 'stateful'] |
| `gemma3:1b` | ragas_what_ru | answerable | missing all expected facts ['оцен', 'evaluat'] |
| `gemma3:1b` | ollama_run_ru | answerable | missing all expected facts ['ollama run'] |
| `gemma3:1b` | ollama_chat_api_ru | answerable | missing all expected facts ['/api/chat'] |
| `gemma3:1b` | off_capital_ru | unanswerable | wrong language |
| `gemma3:1b` | off_kafka_ru | unanswerable | answered instead of refusing |
| `gemma3:1b` | off_pricing_ru | unanswerable | wrong language |
| `qwen3-vl:30b` | uv_what_en | answerable | missing all expected facts ['Rust', 'faster than pip'] |
| `qwen3-vl:30b` | uv_what_ru | answerable | missing all expected facts ['Rust', 'быстрее pip', 'faster than pip'] |
| `qwen3-vl:30b` | ragas_what_ru | answerable | refused on an answerable question |
| `qwen3-vl:30b` | ollama_run_ru | answerable | missing all expected facts ['ollama run'] |
| `qwen3-vl:30b` | ollama_chat_api_ru | answerable | refused on an answerable question |
