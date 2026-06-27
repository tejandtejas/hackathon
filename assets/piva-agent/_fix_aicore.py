#!/usr/bin/env python3
"""Fix clientsecret casing in aicore.py — BTP returns clientSecret (camelCase)."""
import re, pathlib

p = pathlib.Path("app/aicore.py")
src = p.read_text()

# Replace the single cfg.get("clientsecret") lookup with a case-insensitive helper
old_block = '''        base_url = (cfg.get("URL") or "").rstrip("/")
        client_id = cfg.get("clientId") or ""
        client_secret = [REDACTED]