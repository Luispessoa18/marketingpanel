#!/usr/bin/env python3
"""Fetch Instagram profile data and output as JSON line to stdout."""
import sys, json, os
from pathlib import Path

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))

try:
    from dotenv import load_dotenv
    load_dotenv(BASE / '.env')
except Exception:
    pass

target = sys.argv[1] if len(sys.argv) > 1 else ''
as_user = sys.argv[3] if (len(sys.argv) > 3 and sys.argv[2] == '--as') else ''

if not target:
    print(json.dumps({'ok': False, 'error': 'missing_username'}), flush=True)
    sys.exit(1)

try:
    from instagram import InstagramClient
    with InstagramClient(headless=True) as client:
        if as_user:
            if not client.login(as_user, '', save=False):
                print(
                    json.dumps({
                        'ok': False,
                        'error': 'instagram_session_expired',
                        'detail': 'Sessão inválida ou expirada. Rode: python3 instascrapper/main.py login <usuario> <senha>',
                    }),
                    flush=True,
                )
                sys.exit(1)
        data = client.get_profile(target, out_dir=str(BASE / "debug"))
        telemetry = client.get_last_telemetry()
    print(json.dumps({'ok': True, 'profile': data, 'telemetry': telemetry}), flush=True)
except Exception as e:
    print(json.dumps({'ok': False, 'error': str(e)}), flush=True)
    sys.exit(1)
