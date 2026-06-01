import json
import os
from pathlib import Path

SESSIONS_DIR = Path(__file__).parent / "sessions"


def _session_path(username: str) -> Path:
    SESSIONS_DIR.mkdir(exist_ok=True)
    return SESSIONS_DIR / f"{username}.json"


def save_session(page, username: str) -> None:
    cookies = page.context.cookies()
    storage = page.evaluate("() => JSON.stringify(window.localStorage)")
    data = {"cookies": cookies, "localStorage": storage}
    _session_path(username).write_text(json.dumps(data, indent=2))
    print(f"[session] Sessão salva para '{username}'")


def load_session(page, username: str) -> bool:
    path = _session_path(username)
    if not path.exists():
        return False
    data = json.loads(path.read_text())
    page.context.add_cookies(data["cookies"])
    storage = json.loads(data["localStorage"]) if isinstance(data["localStorage"], str) else data["localStorage"]
    page.evaluate(
        "(s) => Object.keys(s).forEach(k => localStorage.setItem(k, s[k]))",
        storage,
    )
    print(f"[session] Sessão carregada para '{username}'")
    return True


def list_sessions() -> list[str]:
    if not SESSIONS_DIR.exists():
        return []
    return [p.stem for p in SESSIONS_DIR.glob("*.json")]


def delete_session(username: str) -> bool:
    path = _session_path(username)
    if path.exists():
        path.unlink()
        return True
    return False
