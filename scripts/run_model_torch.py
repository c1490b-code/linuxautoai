#!/usr/bin/env python3
# scripts/run_model_torch.py
# PyTorch / HuggingFace transformers runner. Uses device selection and prints generated text to stdout.

import os
import sys
import argparse

try:
    from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
except Exception as e:
    print('Install transformers and a compatible torch first. Example: pip install transformers', file=sys.stderr)
    print('Detailed error: ' + str(e), file=sys.stderr)
    sys.exit(1)

parser = argparse.ArgumentParser()
parser.add_argument('--prompt', required=True)
parser.add_argument('--max_new_tokens', type=int, default=256)
parser.add_argument('--temperature', type=float, default=0.7)
parser.add_argument('--device', type=str, default=os.environ.get('RUNNER_DEVICE','auto'))
args = parser.parse_args()

MODEL = os.environ.get('PYTORCH_MODEL', 'gpt2')

# Determine device for pipeline: -1 means CPU, 0 means cuda:0
device_env = args.device.lower()
if device_env in ('cpu', '-1'):
    device = -1
elif device_env in ('cuda', 'gpu'):
    device = 0
elif device_env == 'auto':
    # let transformers decide; prefer gpu if available
    try:
        import torch
        device = 0 if torch.cuda.is_available() else -1
    except Exception:
        device = -1
else:
    # try parse integer
    try:
        device = int(device_env)
    except Exception:
        device = -1

try:
    # Use pipeline for simplicity; model and tokenizer loading may be slow on first run
    gen = pipeline('text-generation', model=MODEL, device=device)
    out = gen(args.prompt, max_new_tokens=args.max_new_tokens, do_sample=True, temperature=args.temperature)
    # out is a list of dicts with 'generated_text'
    if isinstance(out, list) and len(out) > 0 and 'generated_text' in out[0]:
        print(out[0]['generated_text'])
    else:
        print(str(out))
except Exception as e:
    print('PyTorch/transformers generation failed: ' + str(e), file=sys.stderr)
    sys.exit(1)
