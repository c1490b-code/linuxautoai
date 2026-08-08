# Requirements

- Python 3.9+
- pip packages from requirements.txt
- Syncthing on desktop and Android (or another sync solution)
- (Optional) llama.cpp built for your platform and a quantized ggml model if you want local inference


# Example manifest and behavior

The orchestrator watches `workspace/scales/` and reads tasks in `workspace/master.yaml`. Tasks can have `trigger: on_change` (runs when a watched file changes) or `trigger: periodic` with an `interval_seconds` field.

Outputs are written atomically to `workspace/results/` or into project folders.

