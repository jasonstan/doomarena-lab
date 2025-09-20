#!/usr/bin/env python3
"""
Minimal secrets loader: env first, then a local .env if present.
Avoids non-stdlib deps.
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Dict

def _parse_dotenv(text: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out

def ensure_loaded(dotenv_path: str = ".env") -> None:
    # If vars already set, we don't override.
    p = Path(dotenv_path)
    if not p.exists():
        return
    try:
        data = _parse_dotenv(p.read_text(encoding="utf-8"))
        for k, v in data.items():
            os.environ.setdefault(k, v)
    except Exception:
        # Fail soft; probes will surface missing keys explicitly.
        pass
