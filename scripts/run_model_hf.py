#!/usr/bin/env python3
# scripts/run_model_hf.py
# Simple Hugging Face Inference API runner. Expects HUGGINGFACE_API_TOKEN and HUGGINGFACE_MODEL env vars

import os
import sys
import argparse
import requests

parser = argparse.ArgumentParser()
parser.add_argument('--prompt', required=True)
parser.add_argument('--max_tokens', type=int, default=512)
args = parser.parse_args()

TOKEN = os.environ.get('HUGGINGFACE_API_TOKEN')
MODEL = os.environ.get('HUGGINGFACE_MODEL')
if not TOKEN or not MODEL:
    print('Set HUGGINGFACE_API_TOKEN and HUGGINGFACE_MODEL env vars', file=sys.stderr)
    sys.exit(1)

API = f"https://api-inference.huggingface.co/models/{MODEL}"
HEADERS = { 'Authorization': f'Bearer {TOKEN}' }

payload = { 'inputs': args.prompt, 'parameters': {'max_new_tokens': args.max_tokens} }

try:
    r = requests.post(API, headers=HEADERS, json=payload, timeout=60)
    r.raise_for_status()
    # many HF models return either a plain string, or a list of dicts with 'generated_text'
    j = r.json()
    if isinstance(j, list) and len(j) > 0 and isinstance(j[0], dict) and 'generated_text' in j[0]:
        out = j[0]['generated_text']
    elif isinstance(j, dict) and 'generated_text' in j:
        out = j['generated_text']
    elif isinstance(j, str):
        out = j
    else:
        out = str(j)
    print(out)
except Exception as e:
    print('Hugging Face request failed: ' + str(e), file=sys.stderr)
    sys.exit(1)
