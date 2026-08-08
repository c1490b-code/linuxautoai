AI orchestrator for Linux desktop (Debian) and Android (Termux) that watches a synced workspace and runs AI tasks (local llama.cpp, Hugging Face Inference, or OpenAI) writing results back to files.

This updated version adds:
- Multiple runner backends with fallback order
- Unified YAML front-matter output format (metadata + AI text body)
- Idempotency via prompt hashing (skips duplicate prompts)
- Strong safeguards against file-vs-directory conflicts and atomic writes
- Diagnostic scanner to list suspicious directories

Quick start highlights
- Ensure you have Python deps: pip install --user -r requirements.txt
- Configure at least one backend via environment variables:
  - Local: LLAMA_CPP_BIN (path to llama.cpp main) and LLAMA_MODEL (ggml model path)
  - Hugging Face: HUGGINGFACE_API_TOKEN and optional HUGGINGFACE_MODEL (or per-task hf_model)
  - OpenAI: OPENAI_API_KEY and optional OPENAI_MODEL (or per-task openai_model)
- Use Syncthing to sync the workspace/ folder between devices.
- Edit workspace/master.yaml to define tasks and model fallback order.
- Run python3 watcher.py to test.

Output format
Outputs written by the orchestrator include a YAML front-matter with these fields:
- backend: which runner produced the output (local/huggingface/openai)
- model: model name used
- task: task id
- input_hash: truncated sha256 of the rendered prompt (used for idempotency)
- created: ISO timestamp

Followed by the AI-generated text body.

Diagnostic
- scripts/scan_conflicts.py will list directories in the workspace for inspection.

Repository layout
- watcher.py - orchestrator
- workspace/master.yaml - manifest
- scripts/run_model_openai.py
- scripts/run_model_local.py
- scripts/run_model_hf.py
- scripts/scan_conflicts.py
- deploy/ai-orchestrator.service
- scripts/termux_start.sh

