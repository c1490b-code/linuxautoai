#!/usr/bin/env python3
"""
watcher.py - improved orchestrator with multiple AI backends, unified outputs, idempotency,
and hard protections against file-vs-directory conflicts.

Key features added:
- Runner registry with fallback order: local -> huggingface -> openai (configurable per-task)
- Prompt hashing for idempotency (skips rerun if same prompt already processed)
- Unified YAML front-matter metadata in outputs (backend, model, task, input_hash, created)
- Safe filename rendering with placeholders: {{watch_basename}}, {{task_id}}, {{prompt_hash}}
- Directory-vs-file conflict detection and safe alternate naming
- Diagnostic scanner (scripts/scan_conflicts.py) added to repo

Runners are implemented as separate scripts in scripts/ and invoked as subprocesses
for portability between Termux and Debian.
"""

import os
import sys
import time
import yaml
import fnmatch
import argparse
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import subprocess
import tempfile
import shutil
from datetime import datetime
import hashlib
import json

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT / "workspace"
MANIFEST = WORKSPACE / "master.yaml"
SCALES = WORKSPACE / "scales"
RESULTS = WORKSPACE / "results"
SCRIPTS = ROOT / "scripts"
LOCKDIR = WORKSPACE / ".locks"
LOGFILE = WORKSPACE / "watcher.log"

DEFAULT_FALLBACK = ['local', 'huggingface', 'openai']

# Helper: append log
def log(msg):
    ts = datetime.utcnow().isoformat()
    s = f"{ts} {msg}\n"
    print(s, end='')
    try:
        with open(LOGFILE, 'a', encoding='utf-8') as f:
            f.write(s)
    except Exception:
        pass


def load_manifest():
    try:
        with open(MANIFEST, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        log(f"Manifest not found: {MANIFEST}")
        return {}
    except Exception as e:
        log(f"Failed to load manifest: {e}")
        return {}


def is_temporary_file(path: Path):
    name = path.name
    if name.startswith('.') or name.endswith('~') or name.endswith('.swp'):
        return True
    return False


def matches_glob(glob_pattern: str, path: str):
    # glob_pattern is relative to workspace
    gp = str((WORKSPACE / glob_pattern).resolve())
    p = str(Path(path).resolve())
    return fnmatch.fnmatch(p, gp)


def atomic_write_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    # if a directory exists where a file should be, choose an alternate name
    if path.exists() and path.is_dir():
        alt = path.with_name(path.name + '.file')
        log(f"Warning: expected file but found directory. Writing to alternate path {alt}")
        path = alt
    fd, tmp = tempfile.mkstemp(prefix=path.name, dir=str(path.parent))
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(text)
    os.replace(tmp, str(path))


def prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode('utf-8')).hexdigest()[:16]


def read_existing_input_hash(path: Path):
    """If the file exists and has YAML front-matter with input_hash, return it"""
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            head = f.read(8192)
        if head.startswith('---'):
            # find second ---
            parts = head.split('---', 2)
            if len(parts) >= 3:
                meta = parts[1]
                data = yaml.safe_load(meta)
                return data.get('input_hash') if isinstance(data, dict) else None
    except Exception as e:
        log(f"Failed reading existing file for input_hash: {e}")
    return None


def make_output_text(backend: str, model: str, task_id: str, input_hash: str, body: str) -> str:
    meta = {
        'backend': backend,
        'model': model,
        'task': task_id,
        'input_hash': input_hash,
        'created': datetime.utcnow().isoformat() + 'Z'
    }
    fm = '---\n' + yaml.safe_dump(meta) + '---\n\n'
    return fm + body


def safe_filename(name: str) -> str:
    # Basic sanitization: remove slashes, replace spaces, keep letters/numbers/._-@
    keep = []
    for ch in name:
        if ch.isalnum() or ch in '._-@':
            keep.append(ch)
        else:
            keep.append('_')
    s = ''.join(keep)
    if len(s) == 0:
        return 'file'
    return s[:200]


def render_outpath(template: str, watch_basename: str, task_id: str, phash: str) -> Path:
    t = template.replace('{{watch_basename}}', safe_filename(watch_basename))
    t = t.replace('{{task_id}}', safe_filename(task_id))
    t = t.replace('{{prompt_hash}}', phash)
    return WORKSPACE / t


def acquire_lock(lockname: str):
    LOCKDIR.mkdir(parents=True, exist_ok=True)
    path = LOCKDIR / f"{lockname}.lock"
    try:
        os.mkdir(path)
        return path
    except FileExistsError:
        return None
    except Exception as e:
        log(f"Lock acquire error: {e}")
        return None


def release_lock(lockpath: Path):
    try:
        os.rmdir(lockpath)
    except Exception as e:
        log(f"Lock release error: {e}")


def run_runner_subprocess(runner_script: Path, prompt: str, extra_env: dict = None) -> str:
    cmd = [sys.executable, str(runner_script), '--prompt', prompt]
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    try:
        proc = subprocess.run(cmd, check=True, capture_output=True, text=True, env=env)
        return proc.stdout
    except subprocess.CalledProcessError as e:
        log(f"Runner {runner_script} failed: rc={e.returncode}; stderr={e.stderr}")
        raise


def run_model_runner(prompt: str, prefer_list: list, task: dict) -> tuple:
    """Try runners in prefer_list order. Return (backend, model, text). Raises if none available."""
    # normalize prefer_list: could be string 'auto' or list
    for backend in prefer_list:
        if backend == 'local':
            binpath = os.environ.get('LLAMA_CPP_BIN')
            modelpath = os.environ.get('LLAMA_MODEL') or task.get('llama_model')
            if binpath and os.path.exists(binpath) and modelpath and os.path.exists(modelpath):
                # pass model via env so the runner script can pick it up
                try:
                    out = run_runner_subprocess(SCRIPTS / 'run_model_local.py', prompt, {'LLAMA_CPP_BIN': binpath, 'LLAMA_MODEL': modelpath})
                    return ('local', os.path.basename(modelpath), out)
                except Exception:
                    log('Local runner failed, trying next')
                    continue
            else:
                log('Local runner not configured or model missing')
        elif backend == 'huggingface':
            token = os.environ.get('HUGGINGFACE_API_TOKEN')
            hf_model = os.environ.get('HUGGINGFACE_MODEL') or task.get('hf_model')
            if token and hf_model:
                try:
                    out = run_runner_subprocess(SCRIPTS / 'run_model_hf.py', prompt, {'HUGGINGFACE_API_TOKEN': token, 'HUGGINGFACE_MODEL': hf_model})
                    return ('huggingface', hf_model, out)
                except Exception:
                    log('Hugging Face runner failed, trying next')
                    continue
            else:
                log('Hugging Face not configured (HUGGINGFACE_API_TOKEN/HUGGINGFACE_MODEL)')
        elif backend == 'openai':
            key = os.environ.get('OPENAI_API_KEY')
            model = os.environ.get('OPENAI_MODEL') or task.get('openai_model') or 'gpt-4o-mini'
            if key:
                try:
                    out = run_runner_subprocess(SCRIPTS / 'run_model_openai.py', prompt, {'OPENAI_API_KEY': key, 'OPENAI_MODEL': model})
                    return ('openai', model, out)
                except Exception:
                    log('OpenAI runner failed, trying next')
                    continue
            else:
                log('OpenAI not configured')
        else:
            log(f'Unknown backend {backend}, skipping')
    raise RuntimeError('No runner succeeded')


def render_prompt(template: str, file_contents: str, watch_basename: str):
    return template.replace('{{file_contents}}', file_contents).replace('{{watch_basename}}', watch_basename)


def run_task(task: dict, changed_path: Path = None):
    task_id = task.get('id', 'task')
    lock = acquire_lock(task_id)
    if lock is None:
        log(f"Task {task_id} is already running, skipping")
        return
    try:
        file_contents = ''
        basename = 'unknown'
        if changed_path and changed_path.exists() and changed_path.is_file():
            try:
                with open(changed_path, 'r', encoding='utf-8', errors='ignore') as f:
                    file_contents = f.read()
                basename = changed_path.name
            except Exception as e:
                log(f"Failed reading changed file {changed_path}: {e}")
        prompt = render_prompt(task.get('prompt_template', ''), file_contents, basename)
        phash = prompt_hash(prompt)
        # determine output filename
        out_template = task.get('output_path', 'results/{{task_id}}_{{watch_basename}}_{{prompt_hash}}.txt')
        outpath = render_outpath(out_template, basename, task_id, phash)
        # idempotency: skip if existing file has same input_hash
        existing_hash = None
        if outpath.exists() and outpath.is_file():
            existing_hash = read_existing_input_hash(outpath)
        if existing_hash == phash:
            log(f"Skipping task {task_id} for {basename}: existing output with same input_hash")
            return
        # if outpath exists but is a directory, pick alternate
        if outpath.exists() and outpath.is_dir():
            alt = outpath.with_name(outpath.name + '.file')
            log(f"Conflict: expected file but found directory at {outpath}. Using {alt}")
            outpath = alt
        # choose fallback order
        model_pref = task.get('model')
        if isinstance(model_pref, list):
            prefer = model_pref
        elif isinstance(model_pref, str):
            if model_pref == 'auto' or model_pref == 'fallback' or model_pref is None:
                prefer = DEFAULT_FALLBACK
            else:
                prefer = [model_pref]
        else:
            prefer = DEFAULT_FALLBACK
        # run model
        backend, model, body = run_model_runner(prompt, prefer, task)
        outtext = make_output_text(backend, model, task_id, phash, body)
        atomic_write_text(outpath, outtext)
        log(f"Task {task_id} wrote {outpath} (backend={backend} model={model})")
    except Exception as e:
        log(f"Task {task_id} failed: {e}")
    finally:
        release_lock(lock)


class ChangeHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.is_directory:
            return
        p = Path(event.src_path)
        if is_temporary_file(p):
            return
        manifest = load_manifest()
        tasks = manifest.get('tasks', [])
        for task in tasks:
            if task.get('trigger') != 'on_change':
                continue
            watch = task.get('watch_path')
            if not watch:
                continue
            try:
                if matches_glob(watch, str(p)):
                    log(f"Change detected: {p} -> running {task.get('id')}")
                    run_task(task, changed_path=p)
            except Exception as e:
                log(f"Error when matching {p} against {watch}: {e}")


def periodic_loop(interval=10):
    last_run = {}
    while True:
        manifest = load_manifest()
        tasks = manifest.get('tasks', [])
        now = time.time()
        for task in tasks:
            if task.get('trigger') != 'periodic':
                continue
            tid = task.get('id')
            ival = int(task.get('interval_seconds', 3600))
            lr = last_run.get(tid, 0)
            if now - lr >= ival:
                log(f"Running periodic task {tid}")
                watch = task.get('watch_path')
                for fp in SCALES.rglob('*'):
                    if fp.is_file() and not is_temporary_file(fp):
                        try:
                            if matches_glob(watch, str(fp)):
                                run_task(task, changed_path=fp)
                        except Exception as e:
                            log(f"Periodic match error for {fp}: {e}")
                last_run[tid] = now
        time.sleep(interval)


def main():
    if not WORKSPACE.exists():
        WORKSPACE.mkdir(parents=True, exist_ok=True)
    if not SCALES.exists():
        SCALES.mkdir(parents=True, exist_ok=True)
    if not RESULTS.exists():
        RESULTS.mkdir(parents=True, exist_ok=True)

    if not MANIFEST.exists():
        log(f"No manifest at {MANIFEST} - create one first (sample at workspace/master.yaml)")

    observer = Observer()
    handler = ChangeHandler()
    observer.schedule(handler, str(SCALES), recursive=True)
    observer.start()
    log("Watcher started")
    try:
        periodic_loop(interval=10)
    except KeyboardInterrupt:
        log("Interrupted, stopping")
        observer.stop()
    observer.join()

if __name__ == '__main__':
    main()
