Meta Connection Panel

Run locally:
1. python3 -m venv .venv
2. .venv/bin/pip install -r requirements.txt
3. .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8400

Segredos: por defeito em data/secrets.json. Para usar o ficheiro do OpenClaw no servidor:
  export META_PANEL_SECRETS_PATH=/root/.openclaw/workspace/.openclaw/secrets.json

Login web: POST /panel/login (cookies panel_auth / panel_user). Aliases: POST /auth/login, GET /auth/me.
Documentação de rotas novas: docs/api.md (secções 10+).

Main URLs:
- /
- /studio
- /health
- /meta/webhook
- /meta/connect/start
- /meta/connect/callback
