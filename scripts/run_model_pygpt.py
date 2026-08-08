#!/usr/bin/env python3
# scripts/run_model_pygpt.py
# Generic adapter that attempts to use common lightweight GPT-style Python libraries
# It supports a sequence of common libraries if present: pygpt, pygpt4all, gpt4all, or falls back to an informative error.

import os
import sys
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--prompt', required=True)
parser.add_argument('--max_tokens', type=int, default=256)
args = parser.parse_args()

PROMPT = args.prompt

# Try common libraries in order; each block attempts to call a simple API and print text to stdout.

# 1) pygpt (generic name) - try to import and call `complete` or `generate`
try:
    import pygpt
    try:
        # hypothetical API: pygpt.complete(prompt)
        if hasattr(pygpt, 'complete'):
            out = pygpt.complete(PROMPT, max_tokens=args.max_tokens)
            print(out)
            sys.exit(0)
        if hasattr(pygpt, 'generate'):
            out = pygpt.generate(PROMPT, max_tokens=args.max_tokens)
            print(out)
            sys.exit(0)
    except Exception as e:
        print('pygpt import succeeded but call failed: ' + str(e), file=sys.stderr)
except Exception:
    pass

# 2) pygpt4all / gpt4all - common names; try `gpt4all` package
try:
    import gpt4all
    try:
        # gpt4all Python package API: from gpt4all import GPT; gpt = GPT(); gpt.generate(prompt)
        from gpt4all import GPT
        g = GPT()
        out = g.generate(PROMPT, max_tokens=args.max_tokens)
        print(out)
        sys.exit(0)
    except Exception as e:
        print('gpt4all import succeeded but call failed: ' + str(e), file=sys.stderr)
except Exception:
    pass

# 3) pygpt4all package sometimes is 'pygpt4all'
try:
    import pygpt4all
    try:
        from pygpt4all import GPT
        g = GPT()
        out = g.generate(PROMPT)
        print(out)
        sys.exit(0)
    except Exception as e:
        print('pygpt4all import succeeded but call failed: ' + str(e), file=sys.stderr)
except Exception:
    pass

# 4) ollama/llama_cpp_python adapters could be added here if installed
try:
    import llama_cpp
    try:
        from llama_cpp import Llama
        model_path = os.environ.get('LLAMA_PY_MODEL')
        if not model_path:
            raise RuntimeError('Set LLAMA_PY_MODEL env var to local model path for llama_cpp usage')
        llm = Llama(model_path=model_path)
        out = llm.create(prompt=PROMPT, max_tokens=args.max_tokens)
        # response shape may vary
        if isinstance(out, dict) and 'choices' in out and len(out['choices'])>0:
            txt = out['choices'][0].get('text') or out['choices'][0].get('message', {}).get('content')
            print(txt)
            sys.exit(0)
    except Exception as e:
        print('llama_cpp usage failed: ' + str(e), file=sys.stderr)
except Exception:
    pass

# If we reached here, none succeeded
sys.stderr.write('No supported pygpt-like library found.\n')
sys.stderr.write('Install one of: pygpt, gpt4all, pygpt4all, or llama_cpp and configure environment variables.\n')
sys.exit(2)
