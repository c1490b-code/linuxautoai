#!/usr/bin/env python3
"""
watcher.py - watches workspace/scales and runs tasks defined in workspace/master.yaml

Requirements: pip install -r requirements.txt

Behavior summary:
- Watches workspace/scales recursively for file changes
- For each "on_change" task whose watch_path glob matches the changed file, runs the appropriate model runner
- Also runs "periodic" tasks on their interval_seconds schedule (simple timer)
- Writes outputs atomically (temp file then os.replace)
- Simple directory-lock scheme prevents overlapping runs for the same task
- Skips directories and temporary/editor files
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

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT / "workspace"
MANIFEST = WORKSPACE / "master.yaml"
SCALES = WORKSPACE / "scales"
RESULTS = WORKSPACE / "results"
SCRIPTS = ROOT / "scripts"
LOCKDIR = WORKSPACE / ".locks"
LOGFILE = WORKSPACE / "watcher.log"

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
    # Normalize both
    gp = str((WORKSPACE / glob_pattern).resolve())
    p = str(Path(path).resolve())
    # Using fnmatch on full path; allow ** patterns
    # Convert /**.ext to /**\/*.ext for easier matching
    # Use fnmatch.fnmatchcase
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


def run_model_runner(prompt: str, prefer_local: bool):
    # prefer_local: try local runner first if configured; otherwise fall back
    LLAMA_BIN = os.environ.get('LLAMA_CPP_BIN')
    OPENAI_KEY = os.environ.get('OPENAI_API_KEY')
    if prefer_local and LLAMA_BIN and os.path.exists(LLAMA_BIN):
        runner = SCRIPTS / 'run_model_local.py'
        cmd = [sys.executable, str(runner), '--prompt', prompt]
        log(f"Running local model via {LLAMA_BIN}")
    elif OPENAI_KEY:
        runner = SCRIPTS / 'run_model_openai.py'
        cmd = [sys.executable, str(runner), '--prompt', prompt]
        log("Running model via OpenAI API")
    else:
        raise RuntimeError('No model configured: set LLAMA_CPP_BIN or OPENAI_API_KEY')
    # run and capture stdout
    try:
        proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
        return proc.stdout
    except subprocess.CalledProcessError as e:
        log(f"Runner failed: {e}; stdout: {e.stdout}; stderr: {e.stderr}")
        raise


def acquire_lock(lockname: str):
    LOCKDIR.mkdir(parents=True, exist_ok=True)
    path = LOCKDIR / f"{lockname}.lock"
    try:
        # create directory as atomic lock (works cross-platform)
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


def render_prompt(template: str, file_contents: str, watch_basename: str):
    return template.replace('{{file_contents}}', file_contents).replace('{{watch_basename}}', watch_basename)


def run_task(task: dict, changed_path: Path = None):
    task_id = task.get('id', 'task')
    lock = acquire_lock(task_id)
    if lock is None:
        log(f"Task {task_id} is already running, skipping")
        return
    try:
        # gather file contents if applicable
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
        prefer_local = (task.get('model') == 'local')
        out = run_model_runner(prompt, prefer_local=prefer_local)
        # compute output path
        outpath_t = task.get('output_path', 'results/output.txt')
        # replace token {{watch_basename}} if present
        outpath_t = outpath_t.replace('{{watch_basename}}', basename)
        outpath = WORKSPACE / outpath_t
        atomic_write_text(outpath, out)
        log(f"Task {task_id} wrote {outpath}")
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
            # glob matching
            try:
                if matches_glob(watch, str(p)):
                    log(f"Change detected: {p} -> running {task.get('id')}")
                    run_task(task, changed_path=p)
            except Exception as e:
                log(f"Error when matching {p} against {watch}: {e}")


def periodic_loop(interval=10):
    """Run periodic tasks: every `interval` seconds, check manifest for periodic tasks and run them if their interval_seconds elapsed."""
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
                # find files that match watch_path and process each
                watch = task.get('watch_path')
                # naive: walk scales and test fnmatch
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
