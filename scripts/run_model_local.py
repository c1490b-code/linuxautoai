#!/usr/bin/env python3
# scripts/run_model_local.py
# Minimal wrapper that invokes llama.cpp main binary with a prompt and prints output to stdout
# Expects environment variables LLAMA_CPP_BIN and LLAMA_MODEL to be set

import os
import sys
import argparse
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--prompt', required=True)
parser.add_argument('--n', type=int, default=256)
parser.add_argument('--temp', type=float, default=0.7)
args = parser.parse_args()

LLAMA_BIN = os.environ.get('LLAMA_CPP_BIN')
MODEL = os.environ.get('LLAMA_MODEL')
if not LLAMA_BIN or not MODEL:
    print('Set LLAMA_CPP_BIN and LLAMA_MODEL env vars pointing to llama.cpp main binary and a ggml model file', file=sys.stderr)
    sys.exit(1)

if not os.path.exists(LLAMA_BIN):
    print(f'LLAMA_CPP_BIN not found at {LLAMA_BIN}', file=sys.stderr)
    sys.exit(1)
if not os.path.exists(MODEL):
    print(f'LLAMA_MODEL not found at {MODEL}', file=sys.stderr)
    sys.exit(1)

# Construct a safe command. llama.cpp supports -m <model> -p "prompt"
cmd = [LLAMA_BIN, '-m', MODEL, '-p', args.prompt, '-n', str(args.n), '--temp', str(args.temp)]

try:
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    print(proc.stdout)
except subprocess.CalledProcessError as e:
    print('Local runner failed:\n' + e.stderr, file=sys.stderr)
    sys.exit(1)
