#!/usr/bin/env python3
# scripts/run_model_openai.py
# Simple wrapper that sends prompt to OpenAI and prints the result to stdout

import os
import sys
import argparse
try:
    import openai
except Exception:
    print('Install the openai package: pip install openai', file=sys.stderr)
    raise

parser = argparse.ArgumentParser()
parser.add_argument('--prompt', required=True)
parser.add_argument('--max_tokens', type=int, default=800)
args = parser.parse_args()

OPENAI_KEY = os.environ.get('OPENAI_API_KEY')
if not OPENAI_KEY:
    print('Set OPENAI_API_KEY environment variable', file=sys.stderr)
    sys.exit(1)

openai.api_key = OPENAI_KEY

# Use a conservative model by default; change as needed
model = os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')

try:
    resp = openai.ChatCompletion.create(
        model=model,
        messages=[{"role": "user", "content": args.prompt}],
        max_tokens=args.max_tokens,
    )
    # support both ChatCompletion and older response shapes
    if hasattr(resp, 'choices'):
        out = resp.choices[0].message.content if hasattr(resp.choices[0], 'message') else resp.choices[0].text
    else:
        out = str(resp)
    print(out)
except Exception as e:
    print('OpenAI request failed: ' + str(e), file=sys.stderr)
    sys.exit(1)
