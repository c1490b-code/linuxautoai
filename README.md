# linuxautoai

AI orchestrator for Linux desktop (Debian) and Android (Termux) that watches a synced workspace and runs AI tasks (OpenAI API or local llama.cpp) writing results back to files.

This repo contains a minimal watcher/orchestrator, example manifest, model runner scripts, and platform auto-start tips.

WARNING: Keep API keys and local model files out of the repo. Use environment variables as described below.

## Quick start (suggested)

1. Clone this repo on Debian and on your Android Termux home (or copy files via Syncthing):

   ```bash
   git clone https://github.com/c1490b-code/linuxautoai.git
   cd linuxautoai
   ```

2. Install Python deps (both desktop and Termux):

   ```bash
   python3 -m pip install --user -r requirements.txt
   ```

3. Configure env vars:

   - For OpenAI API usage: set OPENAI_API_KEY in your environment.
   - For local inference (llama.cpp): set LLAMA_CPP_BIN to the llama.cpp main binary and LLAMA_MODEL to a ggml model path.

4. Configure Syncthing (or other sync) to sync the `workspace/` folder between devices. This keeps `workspace/master.yaml`, `workspace/scales/` and `workspace/results/` identical across devices.

5. Edit `workspace/master.yaml` to define your tasks. A sample is included.

6. Run the watcher in the foreground for testing:

   ```bash
   python3 watcher.py
   ```

7. Production: create a systemd service on Debian (see `deploy/ai-orchestrator.service`) and install Termux:Boot on Android to auto-start the watcher (see `scripts/termux_start.sh`).

## Files created
- `watcher.py` - main orchestrator (watcher + periodic runner)
- `workspace/master.yaml` - example manifest
- `scripts/run_model_openai.py` - runner for OpenAI API
- `scripts/run_model_local.py` - runner that invokes llama.cpp binary
- `deploy/ai-orchestrator.service` - systemd unit example
- `scripts/termux_start.sh` - Termux:Boot starter script
- `requirements.txt` - Python dependencies
- `.gitignore`

See the README sections below for detailed instructions and troubleshooting.
