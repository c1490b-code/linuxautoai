Updated instructions: adding PyTorch/transformers and generic pygpt support.

PyTorch (transformers) runner
- Uses scripts/run_model_torch.py which relies on the transformers library and a compatible torch installation.
- Configure model with: export PYTORCH_MODEL="gpt2" or a larger HF model id.
- Configure device: export RUNNER_DEVICE="cpu" or "cuda" or leave as "auto".
- On Debian install torch via pip or follow official instructions. Example for cpu-only:
  pip install torch --index-url https://download.pytorch.org/whl/cpu

pygpt / gpt4all adapter
- scripts/run_model_pygpt.py tries common local wrappers (pygpt, gpt4all, pygpt4all, llama_cpp).
- Install your preferred library and set required env vars (e.g., LLAMA_PY_MODEL for llama_cpp).
- This adapter provides a path to run lightweight local models that may be easier to install on mobile.

Fallback order
- Default order is now: local -> pytorch -> pygpt -> huggingface -> openai (watcher.py updated accordingly).
- Per-task model order can be set using the `model` field in workspace/master.yaml (a string or list).

Notes about Android/Termux
- PyTorch is difficult to run on Termux; prefer local llama.cpp or pygpt/gpt4all variants that are built for aarch64.
- The orchestrator will try backends in order and fall back if a runner is not available.

