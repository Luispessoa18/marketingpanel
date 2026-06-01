#!/usr/bin/env python3
"""Scrape recent Instagram posts and output selected/recent posts as JSON."""
import base64
import io
import json
import os
import sys
import zipfile
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
        zip_result = client.scrape_profile(target, out_dir=str(BASE / 'debug'))
        telemetry = client.get_last_telemetry()

    if isinstance(zip_result, (bytes, bytearray)):
        zip_bytes = bytes(zip_result)
    elif isinstance(zip_result, str):
        zip_bytes = Path(zip_result).read_bytes()
    else:
        zip_bytes = b''

    profile = {}
    extracted_images = []
    if zip_bytes:
        with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as zf:
            profile_json_name = next((n for n in zf.namelist() if n.endswith('/profile.json')), '')
            if profile_json_name:
                profile = json.loads(zf.read(profile_json_name).decode('utf-8', 'ignore'))
            for name in zf.namelist():
                if '/posts/' not in name:
                    continue
                payload = zf.read(name)
                extracted_images.append({
                    'filename': name.rsplit('/', 1)[-1],
                    'content_base64': base64.b64encode(payload).decode('ascii'),
                })

    selected_posts = profile.get('selected_posts') if isinstance(profile.get('selected_posts'), list) else []
    recent_posts = profile.get('recent_posts') if isinstance(profile.get('recent_posts'), list) else []
    print(json.dumps({
        'ok': True,
        'username': target,
        'profile': profile,
        'selected_posts': selected_posts,
        'recent_posts': recent_posts,
        'images': extracted_images,
        'telemetry': telemetry,
    }), flush=True)
except Exception as e:
    print(json.dumps({'ok': False, 'error': str(e)}), flush=True)
    sys.exit(1)
