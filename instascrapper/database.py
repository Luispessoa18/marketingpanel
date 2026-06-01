"""
Cache SQLite para perfis scraped — evita re-scraping no mesmo dia.

Tabela: profile_cache
  username     — handle do Instagram (minúsculas)
  date         — YYYY-MM-DD do dia do scraping
  zip_path     — caminho para o arquivo ZIP gerado
  report_html  — caminho para o HTML individual
  report_data  — JSON string com dados da análise IA (para reutilizar)
  profile_json — JSON string do profile.json dentro do ZIP
  scraped_at   — timestamp do último update
"""

import sqlite3
import json
from datetime import date
from pathlib import Path

DB_PATH = Path(__file__).parent / "cache.db"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS profile_cache (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT NOT NULL,
                date          TEXT NOT NULL,
                zip_path      TEXT,
                report_html   TEXT,
                report_data   TEXT,
                profile_json  TEXT,
                scraped_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(username, date)
            )
        """)
        conn.commit()


def get_cache(username: str, day: str | None = None) -> dict | None:
    """Retorna row do cache para o dia especificado (padrão: hoje) ou None."""
    day = day or date.today().isoformat()
    init_db()
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM profile_cache WHERE username = ? AND date = ?",
            (username.lower(), day)
        ).fetchone()
    return dict(row) if row else None


def save_cache(
    username: str,
    *,
    zip_path: str | None = None,
    report_html: str | None = None,
    report_data: "dict | str | None" = None,
    profile_json: "dict | str | None" = None,
) -> None:
    """
    Salva ou atualiza o cache do perfil para hoje.
    Apenas os campos não-None são atualizados.
    """
    day = date.today().isoformat()

    if isinstance(report_data, dict):
        report_data = json.dumps(report_data, ensure_ascii=False)
    if isinstance(profile_json, dict):
        profile_json = json.dumps(profile_json, ensure_ascii=False)

    init_db()
    with _conn() as conn:
        existing = conn.execute(
            "SELECT id FROM profile_cache WHERE username = ? AND date = ?",
            (username.lower(), day)
        ).fetchone()

        if existing:
            updates: dict = {}
            if zip_path is not None:    updates["zip_path"]    = zip_path
            if report_html is not None: updates["report_html"] = report_html
            if report_data is not None: updates["report_data"] = report_data
            if profile_json is not None: updates["profile_json"] = profile_json
            if updates:
                set_clause = ", ".join(f"{k} = ?" for k in updates)
                conn.execute(
                    f"UPDATE profile_cache SET {set_clause}, scraped_at = CURRENT_TIMESTAMP "
                    f"WHERE username = ? AND date = ?",
                    list(updates.values()) + [username.lower(), day]
                )
        else:
            conn.execute(
                """INSERT INTO profile_cache
                       (username, date, zip_path, report_html, report_data, profile_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (username.lower(), day, zip_path, report_html, report_data, profile_json)
            )
        conn.commit()


def list_cached(day: str | None = None) -> list[dict]:
    """Lista todos os perfis cacheados no dia especificado (padrão: hoje)."""
    day = day or date.today().isoformat()
    init_db()
    with _conn() as conn:
        rows = conn.execute(
            """SELECT username, date, zip_path, report_html,
                      CASE WHEN report_data IS NOT NULL THEN 1 ELSE 0 END as has_ai,
                      scraped_at
               FROM profile_cache WHERE date = ? ORDER BY scraped_at""",
            (day,)
        ).fetchall()
    return [dict(r) for r in rows]
