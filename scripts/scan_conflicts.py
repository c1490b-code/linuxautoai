#!/usr/bin/env python3
# scripts/scan_conflicts.py
# Scan workspace for paths where a directory exists where a file is expected or
# where names may conflict across platforms. Prints findings for manual inspection.

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT / 'workspace'
SCALES = WORKSPACE / 'scales'

print('Scanning workspace for potential file/directory conflicts...')
for p in WORKSPACE.rglob('*'):
    try:
        if p.is_dir():
            # check if there are sibling files with same base name but different case or with/without extension
            print('DIR: ', p)
    except Exception as e:
        print('Error inspecting', p, e)

print('Scan complete. Inspect the listed directories for unexpected folder-instead-of-file cases.')
