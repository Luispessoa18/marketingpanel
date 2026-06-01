from fastapi import FastAPI, Request, Form, Cookie, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, PlainTextResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from functools import lru_cache
from pathlib import Path
import os
import json
import hashlib
import base64
from urllib.parse import quote
import urllib.parse
import urllib.request
import urllib.error
import subprocess
import time
import shutil
import mimetypes
import requests
from PIL import Image
from typing import Optional
import traceback

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / 'data'
DATA_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_PATH = DATA_DIR / 'config.json'
EVENTS_PATH = DATA_DIR / 'webhook_events.jsonl'
# Em produção pode apontar para o ficheiro partilhado do OpenClaw: export META_PANEL_SECRETS_PATH=/root/.openclaw/workspace/.openclaw/secrets.json
SECRETS_PATH = Path(os.environ.get('META_PANEL_SECRETS_PATH', str(DATA_DIR / 'secrets.json')))
META_SESSION_PATH = DATA_DIR / 'meta_session.json'
META_USER_SESSIONS_PATH = DATA_DIR / 'meta_user_sessions.json'
INSTAGRAM_DIRECT_SESSION_PATH = DATA_DIR / 'instagram_direct_session.json'
INSTAGRAM_WEB_ACCOUNTS_PATH = DATA_DIR / 'instagram_web_accounts.json'
INSTAGRAM_BROWSER_ACCOUNTS_PATH = DATA_DIR / 'instagram_browser_accounts.json'
INSTAGRAM_BROWSER_JOBS_PATH = DATA_DIR / 'instagram_browser_jobs.json'
AI_POST_RUNS_PATH = DATA_DIR / 'ai_post_runs.jsonl'
META_AD_DRAFT_RUNS_PATH = DATA_DIR / 'meta_ad_draft_runs.jsonl'

AD_ACCOUNT_MEMORY_PATH = DATA_DIR / 'ad_account_memory.json'
CRM_SYNC_STATE_PATH = DATA_DIR / 'crm_sync_state.json'

ADS_REPORTS_HISTORY_PATH = DATA_DIR / 'ads_reports_history.json'
PROFILE_FOLLOWERS_DAILY_PATH = DATA_DIR / 'profile_followers_daily.json'
SYSTEM_ERRORS_LOG_PATH = DATA_DIR / 'system_errors.log'


OBJECTIVE_LABELS_PT = {
    'OUTCOME_SALES': 'Campanha de Vendas',
    'OUTCOME_LEADS': 'Campanha de Cadastros',
    'OUTCOME_TRAFFIC': 'Campanha de Tráfego',
    'OUTCOME_AWARENESS': 'Campanha de Reconhecimento',
    'OUTCOME_ENGAGEMENT': 'Campanha de Engajamento',
    'OUTCOME_APP_PROMOTION': 'Campanha de Promoção de App',
}

def objective_label_pt(value: str) -> str:
    return OBJECTIVE_LABELS_PT.get((value or '').strip(), (value or '').strip() or 'Objetivo não informado')

BRAND_PROFILES_PATH = DATA_DIR / 'brand_profiles.json'
USERS_PATH = DATA_DIR / 'users.json'
API_KEYS_PATH = DATA_DIR / 'api_keys.json'
API_KEY_USAGE_PATH = DATA_DIR / 'api_key_usage.jsonl'
AI_USAGE_PATH = DATA_DIR / 'ai_usage.jsonl'
COMPANIES_PATH = DATA_DIR / 'companies.json'
SCHEDULED_POSTS_PATH = DATA_DIR / 'scheduled_posts.json'
CONTENT_PLANS_PATH = DATA_DIR / 'content_plans.json'
PANEL_DB_PATH = DATA_DIR / 'panel.db'
INSTASCRAPPER_DIR = BASE_DIR / 'instascrapper'
INSTA_VENV_PYTHON = str(BASE_DIR / '.venv' / 'bin' / 'python3')
STATIC_DIR = BASE_DIR / 'static'
TEMPLATES_DIR = BASE_DIR / 'templates'
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
PANEL_TEMPLATE_PATH = TEMPLATES_DIR / 'panel.html'
GENERATED_DIR = STATIC_DIR / 'generated'
GENERATED_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR = STATIC_DIR / 'uploads'
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
RESTART_TOKEN_NAME = 'META_PANEL_RESTART_TOKEN'
PANEL_ADMIN_TOKEN_NAME = 'META_PANEL_ADMIN_TOKEN'
INSTAGRAM_APP_ID_NAME = 'INSTAGRAM_APP_ID'
MANUS_API_KEY_NAME = 'MANUS_API_KEY'
GEMINI_API_KEY_NAME = 'GEMINI_API_KEY'
OPENAI_API_KEY_NAME = 'OPENAI_API_KEY'
OPENAI_BASE_URL_NAME = 'OPENAI_BASE_URL'
ANTHROPIC_API_KEY_NAME = 'ANTHROPIC_API_KEY'
CLOUDINARY_CLOUD_NAME = 'CLOUDINARY_CLOUD_NAME'
CLOUDINARY_API_KEY_NAME = 'CLOUDINARY_API_KEY'
CLOUDINARY_API_SECRET_NAME = 'CLOUDINARY_API_SECRET'
FREEIMAGE_API_KEY_NAME = 'FREEIMAGE_API_KEY'
INSTAGRAM_APP_SECRET_NAME = 'INSTAGRAM_APP_SECRET'
INSTAGRAM_VERIFY_TOKEN_NAME = 'INSTAGRAM_VERIFY_TOKEN'
LINKEDIN_CLIENT_ID_NAME = 'LINKEDIN_CLIENT_ID'
LINKEDIN_CLIENT_SECRET_NAME = 'LINKEDIN_CLIENT_SECRET'
LINKEDIN_REDIRECT_PATH = '/linkedin/connect/callback'
LINKEDIN_SESSION_PATH = DATA_DIR / 'linkedin_session.json'
X_CLIENT_ID_NAME = 'X_CLIENT_ID'
X_CLIENT_SECRET_NAME = 'X_CLIENT_SECRET'
X_REDIRECT_PATH = '/x/connect/callback'
X_SESSION_PATH = DATA_DIR / 'x_session.json'
AGENTS_CONFIG_PATH = DATA_DIR / 'agents_config.json'

DEFAULT_CONFIG = {
    'public_base_url': 'https://marketing.incorporacao.digital',
    'app_id': '',
    'app_secret_name': 'META_APP_SECRET',
    'verify_token_name': 'META_VERIFY_TOKEN',
    'graph_api_version': 'v23.0',
    'default_scopes': 'pages_show_list,pages_read_engagement,pages_manage_posts,instagram_basic,instagram_content_publish,instagram_manage_insights,ads_management,ads_read,business_management',
    'webhook_path': '/meta/webhook',
    'oauth_callback_path': '/meta/connect/callback',
    'ai_settings': {
        'copy_generation': {'provider': 'gemini', 'model': ''},
        'prompt_generation': {'provider': 'gemini', 'model': ''},
        'plan_generation': {'provider': 'gemini', 'model': ''},
        'focus_suggestion': {'provider': 'gemini', 'model': ''},
        'brand_analysis': {'provider': 'gemini', 'model': ''},
        'campaign_analysis': {'provider': 'gemini', 'model': ''},
        'profile_analysis': {'provider': 'gemini', 'model': ''},
        'competitor_analysis': {'provider': 'gemini', 'model': ''},
        'icp_analysis': {'provider': 'gemini', 'model': ''},
        'image_generation': {
            'provider': 'nano_banana',
            'model': '',
            'size': '1024x1024',
            'quality': 'standard',
            'background': 'auto',
            'output_format': 'png',
            'moderation': 'auto',
        },
    },
}

OPENAI_TEXT_MODEL_FALLBACK = [
    'gpt-4o-mini',
    'gpt-4o',
]

CLAUDE_TEXT_MODEL_FALLBACK = [
    'claude-sonnet-4-6',
    'claude-3-5-sonnet-latest',
]

OPENAI_IMAGE_MODELS = {'dall-e-2', 'dall-e-3', 'gpt-image-1', 'gpt-image-1-mini', 'gpt-image-1.5', 'gpt-image-2'}
OPENAI_IMAGE_PROMPT_LIMITS = {
    'dall-e-2': 1000,
    'dall-e-3': 4000,
    'gpt-image-1': 32000,
    'gpt-image-1-mini': 32000,
    'gpt-image-1.5': 32000,
    'gpt-image-2': 32000,
}

AI_PRICE_TABLE = {
    'gemini-2.0-flash': {'input_per_million': 0.10, 'output_per_million': 0.40},
    'gemini-2.0-flash-001': {'input_per_million': 0.10, 'output_per_million': 0.40},
    'gemini-2.5-flash': {'input_per_million': 0.30, 'output_per_million': 2.50},
    'gemini-2.5-flash-lite': {'input_per_million': 0.10, 'output_per_million': 0.40},
    'gemini-flash-latest': {'input_per_million': 0.10, 'output_per_million': 0.40},
    'gemini-1.5-flash': {'input_per_million': 0.35, 'output_per_million': 1.05},
    'gemini-1.5-flash-8b': {'input_per_million': 0.04, 'output_per_million': 0.15},
    'gemini-1.5-pro': {'input_per_million': 3.50, 'output_per_million': 10.50},
    'gpt-4o-mini': {'input_per_million': 0.15, 'output_per_million': 0.60},
    'gpt-4o': {'input_per_million': 2.50, 'output_per_million': 10.00},
    'dall-e-2': {'image_standard': 0.02},
    'dall-e-3': {'image_standard': 0.08},
}


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def _safe_text(value, limit: int = 4000) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return text[:limit]


def _safe_int(value, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def append_system_error_log(kind: str, message: str, **extra):
    payload = {
        'ts': int(time.time()),
        'kind': kind,
        'message': _safe_text(message, 2000),
    }
    for key, value in (extra or {}).items():
        if value is None or value == '':
            continue
        payload[key] = _safe_text(value) if isinstance(value, (str, dict, list, tuple)) else value
    SYSTEM_ERRORS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SYSTEM_ERRORS_LOG_PATH.open('a', encoding='utf-8') as f:
        f.write(json.dumps(payload, ensure_ascii=False, default=str) + '\n')


def _request_context(request: Optional[Request]) -> dict:
    if not request:
        return {}
    return {
        'method': request.method,
        'path': str(request.url.path),
        'query': str(request.url.query or ''),
        'client': getattr(request.client, 'host', '') if request.client else '',
    }


def read_system_error_logs(limit: int = 200) -> list:
    if not SYSTEM_ERRORS_LOG_PATH.exists():
        return []
    try:
        lines = SYSTEM_ERRORS_LOG_PATH.read_text(encoding='utf-8', errors='replace').splitlines()
    except Exception:
        return []
    items = []
    for line in lines[-max(1, min(limit, 1000)):]:
        try:
            items.append(json.loads(line))
        except Exception:
            items.append({'ts': int(time.time()), 'kind': 'log_parse_error', 'message': line[:1000]})
    return list(reversed(items))


def clear_system_error_logs():
    SYSTEM_ERRORS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    SYSTEM_ERRORS_LOG_PATH.write_text('', encoding='utf-8')


# ── SQLite helpers ────────────────────────────────────────────────────────────

import sqlite3

def _db_conn():
    conn = sqlite3.connect(str(PANEL_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    return conn

def init_panel_db():
    with _db_conn() as conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS insta_competitors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                page_id TEXT NOT NULL,
                username TEXT NOT NULL,
                label TEXT DEFAULT '',
                is_own INTEGER DEFAULT 0,
                added_at INTEGER DEFAULT 0,
                UNIQUE(page_id, username)
            );
            CREATE TABLE IF NOT EXISTS insta_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                page_id TEXT NOT NULL,
                username TEXT NOT NULL,
                date TEXT NOT NULL,
                followers INTEGER DEFAULT 0,
                following INTEGER DEFAULT 0,
                posts INTEGER DEFAULT 0,
                engagement_rate REAL DEFAULT 0.0,
                profile_json TEXT DEFAULT '',
                analysis_json TEXT DEFAULT '',
                scraped_at INTEGER DEFAULT 0,
                UNIQUE(username, date)
            );
            CREATE INDEX IF NOT EXISTS idx_comp_page ON insta_competitors(page_id);
            CREATE INDEX IF NOT EXISTS idx_snap_user ON insta_snapshots(username, date DESC);
            CREATE TABLE IF NOT EXISTS content_plans (
                id TEXT PRIMARY KEY,
                page_id TEXT NOT NULL,
                page_name TEXT DEFAULT '',
                ig_user_id TEXT DEFAULT '',
                ig_username TEXT DEFAULT '',
                title TEXT DEFAULT '',
                plan_type TEXT DEFAULT 'monthly',
                month_label TEXT DEFAULT '',
                focus TEXT DEFAULT '',
                model TEXT DEFAULT '',
                generation_cost_usd REAL DEFAULT 0,
                created_at INTEGER DEFAULT 0,
                updated_at INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS plan_posts (
                id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                page_id TEXT NOT NULL,
                sort_order INTEGER DEFAULT 0,
                title TEXT DEFAULT '',
                theme TEXT DEFAULT '',
                format TEXT DEFAULT 'feed',
                suggested_date TEXT DEFAULT '',
                suggested_time TEXT DEFAULT '19:00',
                brief TEXT DEFAULT '',
                cta TEXT DEFAULT '',
                hashtag_theme TEXT DEFAULT '',
                caption TEXT DEFAULT '',
                image_url TEXT DEFAULT '',
                image_prompt TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                created_at INTEGER DEFAULT 0,
                updated_at INTEGER DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_cp_page ON content_plans(page_id, updated_at);
            CREATE INDEX IF NOT EXISTS idx_pp_plan ON plan_posts(plan_id, sort_order);
            CREATE INDEX IF NOT EXISTS idx_pp_page ON plan_posts(page_id);
        ''')
        plan_posts_cols = {row['name'] for row in conn.execute("PRAGMA table_info(plan_posts)").fetchall()}
        plan_cols = {row['name'] for row in conn.execute("PRAGMA table_info(content_plans)").fetchall()}
        if 'title' not in plan_cols:
            conn.execute("ALTER TABLE content_plans ADD COLUMN title TEXT DEFAULT ''")
        if 'plan_type' not in plan_cols:
            conn.execute("ALTER TABLE content_plans ADD COLUMN plan_type TEXT DEFAULT 'monthly'")
        if 'month_label' not in plan_cols:
            conn.execute("ALTER TABLE content_plans ADD COLUMN month_label TEXT DEFAULT ''")
        if 'generation_cost_usd' not in plan_cols:
            conn.execute("ALTER TABLE content_plans ADD COLUMN generation_cost_usd REAL DEFAULT 0")
        if 'meta_json' not in plan_posts_cols:
            conn.execute("ALTER TABLE plan_posts ADD COLUMN meta_json TEXT DEFAULT ''")
        if 'validation_json' not in plan_posts_cols:
            conn.execute("ALTER TABLE plan_posts ADD COLUMN validation_json TEXT DEFAULT ''")

def _plan_to_dict(row) -> dict:
    return dict(row) if row else {}

def db_save_plan(plan_id: str, page_id: str, page_name: str, ig_user_id: str, ig_username: str,
                 posts: list, focus: str = '', model: str = '', title: str = '', plan_type: str = 'monthly', month_label: str = '',
                 generation_cost_usd: float = 0.0) -> dict:
    import random, string
    if not plan_id:
        plan_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))
    now = int(time.time())
    with _db_conn() as conn:
        conn.execute(
            '''INSERT INTO content_plans (id, page_id, page_name, ig_user_id, ig_username, title, plan_type, month_label, focus, model, generation_cost_usd, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 page_name=excluded.page_name, ig_user_id=excluded.ig_user_id,
                 ig_username=excluded.ig_username, title=excluded.title, plan_type=excluded.plan_type,
                 month_label=excluded.month_label, focus=excluded.focus,
                 model=excluded.model, generation_cost_usd=excluded.generation_cost_usd, updated_at=excluded.updated_at''',
            (plan_id, page_id, page_name, ig_user_id, ig_username, title, plan_type, month_label, focus, model, float(generation_cost_usd or 0.0), now, now)
        )
        # Replace the current plan snapshot atomically so post ids from previous plans
        # do not collide with new plans generated with generic ids like p1, p2, ...
        conn.execute('DELETE FROM plan_posts WHERE plan_id=?', (plan_id,))
        for i, p in enumerate(posts or []):
            raw_post_id = str(p.get('id') or '').strip() or ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
            post_id = f'{plan_id}_{raw_post_id}'
            meta_json = json.dumps({
                'story_script': p.get('story_script', []),
                'carousel_slides': p.get('carousel_slides', []),
                'image_urls': p.get('image_urls', []),
                'image_prompts': p.get('image_prompts', []),
                'image_focus': p.get('image_focus', ''),
            }, ensure_ascii=False)
            validation_json = json.dumps(p.get('validation', {}) or {}, ensure_ascii=False)
            conn.execute(
                '''INSERT INTO plan_posts
                   (id, plan_id, page_id, sort_order, title, theme, format, suggested_date, suggested_time,
                    brief, cta, hashtag_theme, caption, image_url, image_prompt, status, meta_json, validation_json, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                     caption=excluded.caption, image_url=excluded.image_url,
                     image_prompt=excluded.image_prompt, status=excluded.status,
                     title=excluded.title, theme=excluded.theme, brief=excluded.brief,
                     sort_order=excluded.sort_order, format=excluded.format,
                     suggested_date=excluded.suggested_date, suggested_time=excluded.suggested_time,
                     cta=excluded.cta, hashtag_theme=excluded.hashtag_theme,
                     meta_json=excluded.meta_json, validation_json=excluded.validation_json,
                     updated_at=excluded.updated_at''',
                (post_id, plan_id, page_id, i,
                 p.get('title',''), p.get('theme',''), p.get('format','feed'),
                 p.get('suggested_date',''), p.get('suggested_time','19:00'),
                 p.get('brief',''), p.get('cta',''), p.get('hashtag_theme',''),
                 p.get('caption',''), p.get('image_url',''), p.get('image_prompt',''),
                 p.get('status','pending'), meta_json, validation_json, now, now)
            )
    return db_load_plan(plan_id)

def db_update_post(post_id: str, plan_id: str, updates: dict):
    updates = dict(updates or {})
    if any(k in updates for k in ('story_script', 'carousel_slides', 'image_urls', 'image_prompts')):
        meta = {}
        if 'story_script' in updates:
            meta['story_script'] = updates.pop('story_script')
        if 'carousel_slides' in updates:
            meta['carousel_slides'] = updates.pop('carousel_slides')
        if 'image_urls' in updates:
            meta['image_urls'] = updates.pop('image_urls')
        if 'image_prompts' in updates:
            meta['image_prompts'] = updates.pop('image_prompts')
        updates['meta_json'] = json.dumps(meta, ensure_ascii=False)
    if 'validation' in updates:
        updates['validation_json'] = json.dumps(updates.pop('validation'), ensure_ascii=False)
    allowed = {'caption', 'image_url', 'image_prompt', 'status', 'title', 'theme', 'brief', 'cta', 'hashtag_theme', 'format', 'meta_json', 'validation_json', 'suggested_date', 'suggested_time'}
    filtered = {k: v for k, v in (updates or {}).items() if k in allowed}
    if not filtered:
        return
    filtered['updated_at'] = int(time.time())
    cols = ', '.join(f'{k}=?' for k in filtered)
    vals = list(filtered.values()) + [post_id, plan_id]
    with _db_conn() as conn:
        conn.execute(f'UPDATE plan_posts SET {cols} WHERE id=? AND plan_id=?', vals)
    # Also update plan updated_at
    with _db_conn() as conn:
        conn.execute('UPDATE content_plans SET updated_at=? WHERE id=?', (int(time.time()), plan_id))

def db_load_plans(page_id: str, limit: int = 10) -> list:
    with _db_conn() as conn:
        plans = conn.execute(
            'SELECT * FROM content_plans WHERE page_id=? ORDER BY updated_at DESC LIMIT ?',
            (str(page_id), limit)
        ).fetchall()
        result = []
        for plan in plans:
            pd = dict(plan)
            posts = conn.execute(
                'SELECT * FROM plan_posts WHERE plan_id=? ORDER BY sort_order ASC',
                (pd['id'],)
            ).fetchall()
            pd['posts'] = [_expand_plan_post(dict(p)) for p in posts]
            result.append(pd)
        return result

def db_load_plan(plan_id: str) -> dict:
    with _db_conn() as conn:
        plan = conn.execute('SELECT * FROM content_plans WHERE id=?', (plan_id,)).fetchone()
        if not plan:
            return {}
        pd = dict(plan)
        posts = conn.execute('SELECT * FROM plan_posts WHERE plan_id=? ORDER BY sort_order ASC', (plan_id,)).fetchall()
        pd['posts'] = [_expand_plan_post(dict(p)) for p in posts]
        return pd


def _expand_plan_post(post: dict) -> dict:
    meta = {}
    validation = {}
    if post.get('meta_json'):
        try:
            meta = json.loads(post.get('meta_json') or '{}')
        except Exception:
            meta = {}
    if post.get('validation_json'):
        try:
            validation = json.loads(post.get('validation_json') or '{}')
        except Exception:
            validation = {}
    post['story_script'] = meta.get('story_script', [])
    post['carousel_slides'] = meta.get('carousel_slides', [])
    post['image_urls'] = meta.get('image_urls', [])
    post['image_prompts'] = meta.get('image_prompts', [])
    post['image_focus'] = meta.get('image_focus', '')
    post['validation'] = validation
    return post


def db_add_competitor(page_id: str, username: str, label: str = '', is_own: int = 0):
    with _db_conn() as conn:
        if is_own:
            # Só um "próprio" por página; o login do scrapper (ex. homeunity) não pode ficar is_own=1 a par do @ da marca
            conn.execute('UPDATE insta_competitors SET is_own=0 WHERE page_id=?', (str(page_id),))
        conn.execute(
            '''INSERT INTO insta_competitors (page_id, username, label, is_own, added_at)
               VALUES (?,?,?,?,?) ON CONFLICT(page_id, username) DO UPDATE SET label=COALESCE(excluded.label,label), is_own=excluded.is_own''',
            (str(page_id), username.lower().lstrip('@'), label, is_own, int(time.time()))
        )

def db_remove_competitor(page_id: str, username: str):
    with _db_conn() as conn:
        conn.execute('DELETE FROM insta_competitors WHERE page_id=? AND username=?',
                     (str(page_id), username.lower().lstrip('@')))

def db_get_competitors(page_id: str) -> list:
    with _db_conn() as conn:
        rows = conn.execute('SELECT * FROM insta_competitors WHERE page_id=? ORDER BY is_own DESC, added_at ASC', (str(page_id),)).fetchall()
        return [dict(r) for r in rows]

def db_save_snapshot(page_id: str, username: str, data: dict):
    import datetime
    today = datetime.date.today().isoformat()
    with _db_conn() as conn:
        conn.execute(
            '''INSERT INTO insta_snapshots
               (page_id, username, date, followers, following, posts, engagement_rate, profile_json, analysis_json, scraped_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(username, date) DO UPDATE SET
                 followers=excluded.followers, following=excluded.following, posts=excluded.posts,
                 engagement_rate=excluded.engagement_rate, profile_json=excluded.profile_json,
                 analysis_json=excluded.analysis_json, scraped_at=excluded.scraped_at''',
            (str(page_id), username.lower().lstrip('@'), today,
             int(data.get('followers', 0) or 0), int(data.get('following', 0) or 0),
             int(data.get('posts', 0) or 0), float(data.get('engagement_rate', 0.0) or 0),
             json.dumps(data.get('profile', {}), ensure_ascii=False),
             json.dumps(data.get('analysis', {}), ensure_ascii=False),
             int(time.time()))
        )

def db_get_snapshots(username: str, days: int = 60) -> list:
    with _db_conn() as conn:
        rows = conn.execute(
            'SELECT * FROM insta_snapshots WHERE username=? ORDER BY date DESC LIMIT ?',
            (username.lower(), days)
        ).fetchall()
        return [dict(r) for r in rows]

def db_get_competitor_summary(page_id: str) -> list:
    comps = db_get_competitors(page_id)
    result = []
    for c in comps:
        snaps = db_get_snapshots(c['username'], days=60)
        latest = snaps[0] if snaps else {}
        prev = snaps[1] if len(snaps) > 1 else {}
        followers_now = latest.get('followers', 0)
        followers_prev = prev.get('followers', 0)
        delta = followers_now - followers_prev if followers_prev else 0
        analysis = {}
        if latest.get('analysis_json'):
            try:
                analysis = json.loads(latest['analysis_json'])
            except Exception:
                pass
        profile = {}
        if latest.get('profile_json'):
            try:
                profile = json.loads(latest['profile_json'])
            except Exception:
                pass
        result.append({
            'username': c['username'], 'label': c['label'], 'is_own': c['is_own'],
            'followers': followers_now, 'followers_prev': followers_prev,
            'delta': delta, 'delta_pct': round(delta/followers_prev*100, 1) if followers_prev else 0,
            'posts': latest.get('posts', 0),
            'last_scraped': latest.get('date', ''),
            'profile': profile, 'analysis': analysis,
            'snapshots': snaps[:30],
        })
    return result


def build_icp_context(page_id: str) -> dict:
    profile = get_brand_profile(page_id)
    try:
        competitors = db_get_competitor_summary(page_id)
    except Exception as e:
        append_system_error_log(
            'icp_context_error',
            'Failed to build ICP competitor context',
            detail=str(e),
            page_id=page_id,
        )
        competitors = []
    own = next((c for c in competitors if c.get('is_own')), None)
    others = [c for c in competitors if not c.get('is_own')]
    return {
        'brand_profile': profile,
        'own_profile': own or {},
        'competitors': others[:8],
        'icp_onboarding_text': profile.get('icp_onboarding_text', ''),
        'icp_compare_notes': profile.get('icp_compare_notes', ''),
        'icp_adjustment_notes': profile.get('icp_adjustment_notes', ''),
        'icp_analysis_history': profile.get('icp_analysis_history', [])[-10:],
        'page_id': page_id,
    }


def generate_icp_analysis(page_id: str, onboarding_text: str = '', compare_notes: str = '', adjustment_notes: str = '') -> dict:
    context = build_icp_context(page_id)
    if onboarding_text:
        context['owner_onboarding'] = onboarding_text
    if compare_notes:
        context['owner_compare_notes'] = compare_notes
    if adjustment_notes:
        context['owner_adjustment_notes'] = adjustment_notes
    prompt = (
        'Você é um estrategista de marketing, pesquisa de mercado e ICP. '
        'Analise o Instagram da marca e os concorrentes já mapeados. '
        'Considere também a visão do dono da operação quando ela existir, compare com os sinais observados e aponte convergências, divergências e ajustes. '
        'Responda SOMENTE com JSON válido em português do Brasil. '
        'Estrutura obrigatória: '
        '{"overview":"","analysis_text":"","demographics":{"age_range":"","gender_mix":"","regions":[],"income_band":"","interests":[]},'
        '"persona":{"name":"","summary":"","goals":[],"pain_points":[],"objections":[],"triggers":[]},'
        '"empathy_map":{"thinks":[],"feels":[],"sees":[],"hears":[],"says_and_does":[]},'
        '"owner_alignment":{"matches":[],"differences":[],"questions":[]},'
        '"competitor_gaps":[],"content_opportunities":[],"offers_and_positioning":[],"recommendations":[]}. '
        'Se inferir algo, seja prudente e útil. '
        'Dados: ' + json.dumps(context, ensure_ascii=False)
    )
    result = _ai_generate_text('icp_analysis', prompt, 90, json_mode=True)
    parsed = _extract_json_block(result.get('text') or '')
    if not isinstance(parsed, dict):
        raise ValueError('invalid_icp_analysis')
    parsed['_ai_provider'] = result.get('provider', '')
    parsed['_ai_model'] = result.get('model', '')
    parsed['_ai_usage'] = result.get('usage', {})
    parsed['_ai_cost_usd'] = result.get('cost_usd', 0.0)
    log_ai_usage('icp_analysis', result.get('provider', ''), result.get('model', ''), result.get('usage', {}), result.get('cost_usd', 0.0), page_id=page_id, item_type='icp')
    return parsed


def _insta_load_env() -> dict:
    env = os.environ.copy()
    env_file = INSTASCRAPPER_DIR / '.env'
    if env_file.exists():
        for line in env_file.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                env[k.strip()] = v.strip()
    return env


def _insta_default_session_username() -> str:
    """Conta cujos cookies o instascrapper usa (ex.: homeunity). Definir em instascrapper/.env: INSTASCRAPPER_DEFAULT_SESSION=homeunity"""
    return (_insta_load_env().get('INSTASCRAPPER_DEFAULT_SESSION') or os.environ.get('INSTASCRAPPER_DEFAULT_SESSION') or '').strip()


def _insta_match_stem(ideal: str) -> str:
    """Quando existe homeunity.json, devolve o stem exato (case) do ficheiro."""
    if not ideal or not str(ideal).strip():
        return ''
    t = str(ideal).strip().lower()
    for s in _insta_saved_sessions():
        if s.lower() == t:
            return s
    return ''


def _insta_effective_as_user(_requested: str) -> str:
    """
    Conta usada SÓ para cookies (login no browser do scrapper). O alvo a ler vem
    de `username` noutro campo do body — o painel não define qual conta fazer login
    a não ser que INSTASCRAPPER_DEFAULT_SESSION exista. Caso contrário, priorizamos
    a sessão `homeunity` se o ficheiro existir, senão a 1.ª alfabeticamente.
    (O seletor do painel é ignorado de propósito.)
    """
    _ = _requested
    d = _insta_default_session_username()
    if d:
        m = _insta_match_stem(d)
        return m or d.strip()
    m = _insta_match_stem('homeunity')
    if m:
        return m
    stems = _insta_saved_sessions()
    if not stems:
        return ''
    return sorted(stems, key=str.lower)[0]


def run_insta_script(script_name: str, args: list = None, timeout: int = 150) -> dict:
    """Run an instascrapper JSON helper script and return parsed result."""
    script_path = INSTASCRAPPER_DIR / script_name
    if not script_path.exists():
        return {'ok': False, 'error': f'script_not_found: {script_name}'}
    cmd = [INSTA_VENV_PYTHON, str(script_path)] + (args or [])
    env = _insta_load_env()
    profile_route = _ai_route('profile_analysis')
    provider = profile_route.get('provider', 'gemini')
    model = profile_route.get('model', '')
    if provider == 'openai':
        env['AI_PROVIDER'] = 'openai'
        env['OPENAI_API_KEY'] = _openai_api_key()
        env['AI_MODEL'] = model or 'gpt-4o'
        if _openai_base_url():
            env['OPENAI_BASE_URL'] = _openai_base_url()
    else:
        env['AI_PROVIDER'] = 'gemini'
        env['GOOGLE_API_KEY'] = get_secret(GEMINI_API_KEY_NAME) or get_secret('GOOGLE_API_KEY')
        if model:
            env['AI_MODEL'] = model
    try:
        r = subprocess.run(cmd, cwd=str(INSTASCRAPPER_DIR), capture_output=True,
                           text=True, encoding='utf-8', errors='replace', timeout=timeout, env=env)
        # Parse last valid JSON line from stdout
        for line in reversed(r.stdout.strip().splitlines()):
            line = line.strip()
            if line.startswith('{'):
                try:
                    out = json.loads(line)
                    if r.stderr and str(r.stderr).strip():
                        tail = (r.stderr or '')[-2000:]
                        if isinstance(out, dict):
                            out['script_stderr_tail'] = tail
                    return out
                except Exception:
                    pass
        result = {'ok': r.returncode == 0, 'stdout': r.stdout[:2000], 'stderr': r.stderr[:1000]}
        if not result['ok']:
            append_system_error_log(
                'local_script_error',
                'Instagram local script failed',
                script=script_name,
                args=args or [],
                returncode=r.returncode,
                stdout=r.stdout[:2000],
                stderr=r.stderr[:2000],
            )
        return result
    except subprocess.TimeoutExpired:
        append_system_error_log('local_script_timeout', 'Instagram local script timeout', script=script_name, args=args or [], timeout=timeout)
        return {'ok': False, 'error': 'timeout', 'detail': f'Comando excedeu {timeout}s'}
    except Exception as e:
        append_system_error_log('local_script_error', 'Instagram local script crashed', script=script_name, args=args or [], detail=str(e))
        return {'ok': False, 'error': str(e)}


def _insta_saved_sessions() -> list:
    sessions_dir = INSTASCRAPPER_DIR / 'sessions'
    sessions = []
    if sessions_dir.exists():
        for f in sessions_dir.glob('*.json'):
            sessions.append(f.stem)
    return sessions


def _is_insta_session_error(result: dict) -> bool:
    if not isinstance(result, dict):
        return False
    profile = result.get('profile') if isinstance(result.get('profile'), dict) else {}
    profile_error = str(profile.get('error', '') or '').strip().lower()
    if profile_error in ('not_logged_in', 'login_required'):
        return True
    blob = ' '.join([
        str(result.get('error', '') or ''),
        str(result.get('detail', '') or ''),
        str(result.get('stderr', '') or ''),
    ]).lower()
    markers = [
        'sessão inválida', 'sessao invalida', 'sessão expirada', 'sessao expirada',
        'session invalid', 'session expired', 'not_logged_in', 'login required',
        'instagram_session_expired', 'session_expired',
        'checkpoint required', 'challenge required',
    ]
    return any(m in blob for m in markers)


def _run_insta_script_with_session_fallback(script_name: str, username: str, as_user: str = '', extra_args: list = None, timeout: int = 150) -> dict:
    extra_args = list(extra_args or [])
    sessions = _insta_saved_sessions()
    ordered = []
    if as_user:
        ordered.append(as_user)
    for s in sessions:
        if s not in ordered:
            ordered.append(s)
    if not ordered:
        return {
            'ok': False,
            'error': 'instagram_session_expired',
            'detail': 'Nenhuma sessão do Instagram encontrada. Faça login no instascrapper.',
        }

    last_session_error = None
    for session_name in ordered:
        args = [username, '--as', session_name] + extra_args
        r = run_insta_script(script_name, args, timeout=timeout)
        if r.get('ok') and not _is_insta_session_error(r):
            r['session_used'] = session_name
            return r
        if _is_insta_session_error(r):
            last_session_error = r
            continue
        return r

    detail = (last_session_error or {}).get('detail') or (last_session_error or {}).get('error') or 'Sessão inválida ou expirada.'
    return {
        'ok': False,
        'error': 'instagram_session_expired',
        'detail': str(detail),
        'tried_sessions': ordered,
    }


def _build_insta_analyze_diagnostics(r: dict) -> dict:
    """Explica ao painel o que aconteceu no scrapper + IA (perfil, ZIP, chaves, JSON)."""
    if not isinstance(r, dict):
        return {}
    analysis = r.get('analysis') if isinstance(r.get('analysis'), dict) else {}
    nkeys = r.get('analysis_key_count')
    if nkeys is None:
        nkeys = len([k for k in analysis if not str(k).startswith('_')])
    has_body = nkeys > 0
    return {
        'username': r.get('username'),
        'cached': bool(r.get('cached')),
        'session_used': r.get('session_used'),
        'source': (r.get('source') or ('cache_disco' if r.get('cached') else 'corrida_nova')),
        'profile_fetched': bool(r.get('profile')) and not (r.get('profile') or {}).get('error'),
        'profile_error': (r.get('profile') or {}).get('error') if isinstance(r.get('profile'), dict) else None,
        'zip_ok': r.get('zip_ok'),
        'ai_key_configured': r.get('ai_key_configured'),
        'ai_ran': r.get('ai_ran'),
        'ai_skip_reason': r.get('ai_skip_reason'),
        'analysis_json_generated': has_body,
        'analysis_key_count': int(nkeys) if nkeys is not None else 0,
        'provider': r.get('provider'),
        'model': r.get('model'),
        'stage': r.get('stage'),
        'failure_category': r.get('failure_category'),
        'warning': r.get('warning'),
        'script_stderr_tail': (r.get('script_stderr_tail') or '')[-2500:],
        'user_hint': _insta_analyze_diagnostics_user_hint(r, has_body),
    }


def _insta_analyze_diagnostics_user_hint(r: dict, has_body: bool) -> str:
    category = (r.get('failure_category') or '').strip()
    if r.get('cached'):
        return 'Relatório reutilizado do cache em disco. Para forçar nova análise, o API aceita `force: true` no corpo (ou reimplementar no painel).'
    if r.get('ai_key_configured') is False:
        return 'Nenhuma chave GOOGLE/OPENAI chegou ao processo do instascrapper. Abra Configuração no painel e guarde a chave Gemini (o servidor injeta GOOGLE_API_KEY no script).'
    if category == 'profile_fetch_failed':
        return 'Falha ao ler o perfil base antes do scraping. Verifique se o username existe, se a sessão está válida e se o Instagram não bloqueou a leitura.'
    if category == 'scrape_failed':
        return 'O scraping do perfil falhou antes da IA. Normalmente é bloqueio do Instagram, perfil privado, timeout ou falha do Playwright ao gerar o ZIP.'
    if category == 'ai_key_missing':
        return 'A etapa de IA não rodou porque não havia chave do provider configurada no processo do scrapper.'
    if category == 'ai_provider_failed':
        return 'A etapa de IA falhou no provider/modelo escolhido. Verifique chave, rate limit, modelo selecionado e resposta de erro bruta.'
    if category == 'ai_json_parse_failed':
        return 'A IA respondeu, mas o JSON não veio no formato esperado pelo painel. Tente outro modelo ou veja o warning técnico.'
    if category == 'analysis_empty':
        return 'A IA rodou, mas a análise voltou vazia. Isso costuma indicar resposta incompleta, truncada ou incompatível com o schema.'
    if r.get('zip_ok') is False:
        return 'O passo de scrape não devolveu ZIP (bloqueio, privado, timeout). Veja script_stderr_tail e logs do servidor/Playwright.'
    if not has_body and (r.get('ai_ran') is False) and (r.get('ai_skip_reason') or ''):
        return f"Motivo técnico: {r.get('ai_skip_reason', '')}"
    if not has_body and r.get('ai_ran'):
        return 'A API de resposta da IA veio vazia ou o JSON não seguiu o schema. Verifique o modelo e os logs de ai_analyze.'
    if has_body:
        return f"OK: {r.get('analysis_key_count', 0)} chaves de análise (header, diagnosis, etc.)."
    return 'Sem dados extra para diagnosticar; veja chaves técnicas acima.'


def _parse_followers(raw) -> int:
    """Parse '13.5K', '1.2M', '45000' → int."""
    if isinstance(raw, int):
        return raw
    s = str(raw or '0').replace(',', '').replace('.', '').replace(' ', '').upper()
    try:
        if 'K' in s:
            return int(float(s.replace('K', '')) * 1000)
        if 'M' in s:
            return int(float(s.replace('M', '')) * 1000000)
        return int(float(s))
    except Exception:
        return 0


def load_meta_user_sessions() -> dict:
    return load_json(META_USER_SESSIONS_PATH, {}) or {}


def save_meta_user_sessions(data: dict):
    save_json(META_USER_SESSIONS_PATH, data or {})


def _normalize_panel_email(email: str = '') -> str:
    return (email or '').strip().lower()


def get_meta_session_for_panel_user(panel_user_email: str = '') -> dict:
    email = _normalize_panel_email(panel_user_email)
    if not email or email == 'legacy-admin':
        return load_json(META_SESSION_PATH, {}) or {}
    sessions = load_meta_user_sessions()
    if email in sessions:
        return sessions.get(email) or {}
    return {}


def save_meta_session_for_panel_user(panel_user_email: str, session: dict):
    email = _normalize_panel_email(panel_user_email)
    if not email or email == 'legacy-admin':
        save_json(META_SESSION_PATH, session or {})
        return
    sessions = load_meta_user_sessions()
    sessions[email] = session or {}
    save_meta_user_sessions(sessions)


def get_shareable_pages_from_admin() -> list:
    admin_session = load_json(META_SESSION_PATH, {}) or {}
    return admin_session.get('pages', []) if isinstance(admin_session, dict) else []


def get_shareable_ad_accounts_from_admin() -> list:
    admin_session = load_json(META_SESSION_PATH, {}) or {}
    return admin_session.get('ad_accounts', []) if isinstance(admin_session, dict) else []


def merge_ad_accounts_unique(*ad_accounts_lists) -> list:
    merged = []
    seen = set()
    for accounts in ad_accounts_lists:
        for acct in (accounts or []):
            acct_id = normalize_ad_account_id(str((acct or {}).get('id') or (acct or {}).get('account_id') or ''))
            if not acct_id or acct_id in seen:
                continue
            seen.add(acct_id)
            merged.append({**acct, 'id': acct_id})
    return merged


@lru_cache(maxsize=1)
def load_panel_template() -> str:
    return PANEL_TEMPLATE_PATH.read_text()


def _normalize_ai_settings(raw) -> dict:
    defaults = json.loads(json.dumps(DEFAULT_CONFIG.get('ai_settings') or {}))
    if not isinstance(raw, dict):
        return defaults
    for key, value in raw.items():
        if key not in defaults:
            continue
        if isinstance(value, dict):
            updates = {
                'provider': str(value.get('provider', defaults[key].get('provider', '')) or defaults[key].get('provider', '')).strip(),
                'model': str(value.get('model', defaults[key].get('model', '')) or '').strip(),
            }
            for extra_key in ['size', 'quality', 'background', 'output_format', 'moderation']:
                if extra_key in defaults[key] or extra_key in value:
                    updates[extra_key] = str(value.get(extra_key, defaults[key].get(extra_key, '')) or defaults[key].get(extra_key, '')).strip()
            defaults[key].update(updates)
    return defaults


def load_config():
    cfg = DEFAULT_CONFIG.copy()
    cfg.update(load_json(CONFIG_PATH, {}))
    cfg['ai_settings'] = _normalize_ai_settings(cfg.get('ai_settings'))
    return cfg


def save_config(cfg):
    save_json(CONFIG_PATH, cfg)


def load_secrets():
    return load_json(SECRETS_PATH, {})


def get_secret(name: str) -> str:
    return load_secrets().get(name, '')


def set_secret(name: str, value: str):
    secrets = load_secrets()
    secrets[name] = value
    SECRETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SECRETS_PATH.write_text(json.dumps(secrets, ensure_ascii=False, indent=2))



def append_ai_usage_log(entry: dict):
    payload = dict(entry or {})
    payload['ts'] = int(payload.get('ts') or time.time())
    AI_USAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with AI_USAGE_PATH.open('a', encoding='utf-8') as f:
        f.write(json.dumps(payload, ensure_ascii=False, default=str) + '\n')


def read_ai_usage_log(limit: int = 1000) -> list:
    if not AI_USAGE_PATH.exists():
        return []
    try:
        lines = AI_USAGE_PATH.read_text(encoding='utf-8', errors='replace').splitlines()
    except Exception:
        return []
    items = []
    for line in lines[-max(1, min(limit, 10000)):]:
        try:
            items.append(json.loads(line))
        except Exception:
            continue
    return items


def ai_settings_for(feature: str) -> dict:
    cfg = load_config()
    settings = _normalize_ai_settings((cfg.get('ai_settings') or {}).get(feature))
    if feature in (cfg.get('ai_settings') or {}):
        value = (cfg.get('ai_settings') or {}).get(feature) or {}
        if isinstance(value, dict):
            return {
                'provider': str(value.get('provider', settings[feature]['provider'] if feature in settings else 'gemini') or (cfg.get('ai_settings') or {}).get(feature, {}).get('provider', '')).strip() or ((DEFAULT_CONFIG.get('ai_settings') or {}).get(feature, {}) or {}).get('provider', 'gemini'),
                'model': str(value.get('model', '') or '').strip(),
            }
    defaults = (DEFAULT_CONFIG.get('ai_settings') or {}).get(feature, {})
    return {'provider': defaults.get('provider', 'gemini'), 'model': defaults.get('model', '')}


def _ai_route(feature: str) -> dict:
    cfg = load_config()
    route = ((cfg.get('ai_settings') or {}).get(feature) or {}).copy() if isinstance((cfg.get('ai_settings') or {}).get(feature), dict) else {}
    defaults = (DEFAULT_CONFIG.get('ai_settings') or {}).get(feature, {})
    provider = str(route.get('provider', defaults.get('provider', 'gemini')) or defaults.get('provider', 'gemini')).strip().lower()
    model = str(route.get('model', defaults.get('model', '')) or '').strip()
    return {'provider': provider, 'model': model}


def _estimate_text_tokens(text: str) -> int:
    text = str(text or '')
    if not text:
        return 0
    return max(1, int(len(text) / 4))


def _extract_json_block(raw: str):
    raw = str(raw or '').strip()
    if not raw:
        raise ValueError('empty_ai_response')
    if raw.startswith('```'):
        raw = re.sub(r'^```[a-zA-Z0-9_-]*\n?', '', raw)
        raw = re.sub(r'\n?```$', '', raw)
        raw = raw.strip()
    try:
        return json.loads(raw)
    except Exception:
        pass
    start = raw.find('{')
    if start == -1:
        raise ValueError(f'json_not_found_in_ai_response: {raw[:200]}')
    decoder = json.JSONDecoder()
    try:
        obj, _ = decoder.raw_decode(raw, start)
        return obj
    except Exception as e:
        raise ValueError(f'invalid_ai_json: {e}')


def _extract_usage_from_gemini_response(data: dict) -> dict:
    meta = data.get('usageMetadata') or {}
    prompt_tokens = int(meta.get('promptTokenCount') or meta.get('inputTokenCount') or 0)
    completion_tokens = int(meta.get('candidatesTokenCount') or meta.get('outputTokenCount') or 0)
    total_tokens = int(meta.get('totalTokenCount') or (prompt_tokens + completion_tokens))
    return {
        'input_tokens': prompt_tokens,
        'output_tokens': completion_tokens,
        'total_tokens': total_tokens,
    }


def _extract_usage_from_openai_response(data: dict) -> dict:
    usage = data.get('usage') or {}
    prompt_tokens = int(usage.get('prompt_tokens') or usage.get('input_tokens') or 0)
    completion_tokens = int(usage.get('completion_tokens') or usage.get('output_tokens') or 0)
    total_tokens = int(usage.get('total_tokens') or (prompt_tokens + completion_tokens))
    return {
        'input_tokens': prompt_tokens,
        'output_tokens': completion_tokens,
        'total_tokens': total_tokens,
    }


def _extract_usage_from_openai_responses(data: dict) -> dict:
    usage = data.get('usage') or {}
    input_tokens = int(usage.get('input_tokens') or 0)
    output_tokens = int(usage.get('output_tokens') or 0)
    total_tokens = int(usage.get('total_tokens') or (input_tokens + output_tokens))
    return {
        'input_tokens': input_tokens,
        'output_tokens': output_tokens,
        'total_tokens': total_tokens,
    }


def _extract_usage_from_claude_response(data: dict) -> dict:
    usage = data.get('usage') or {}
    prompt_tokens = int(usage.get('input_tokens') or 0)
    completion_tokens = int(usage.get('output_tokens') or 0)
    total_tokens = prompt_tokens + completion_tokens
    return {
        'input_tokens': prompt_tokens,
        'output_tokens': completion_tokens,
        'total_tokens': total_tokens,
    }


def _calculate_ai_cost(provider: str, model: str, usage: dict = None, image_count: int = 0) -> float:
    usage = usage or {}
    price = AI_PRICE_TABLE.get(model, {})
    if image_count:
        per_image = float(price.get('image_standard') or 0.0)
        return round(per_image * max(1, int(image_count)), 6)
    input_tokens = float(usage.get('input_tokens') or 0)
    output_tokens = float(usage.get('output_tokens') or 0)
    if not input_tokens and usage.get('total_tokens'):
        input_tokens = float(usage.get('total_tokens') or 0)
    return round(
        (input_tokens / 1_000_000.0) * float(price.get('input_per_million') or 0.0) +
        (output_tokens / 1_000_000.0) * float(price.get('output_per_million') or 0.0),
        6,
    )


def log_ai_usage(operation: str, provider: str, model: str, usage: dict = None, cost_usd: float = 0.0,
                 page_id: str = '', plan_id: str = '', post_id: str = '', item_type: str = '', extra: dict = None):
    entry = {
        'operation': operation,
        'provider': provider,
        'model': model,
        'page_id': str(page_id or ''),
        'plan_id': str(plan_id or ''),
        'post_id': str(post_id or ''),
        'item_type': str(item_type or ''),
        'input_tokens': int((usage or {}).get('input_tokens') or 0),
        'output_tokens': int((usage or {}).get('output_tokens') or 0),
        'total_tokens': int((usage or {}).get('total_tokens') or 0),
        'cost_usd': float(cost_usd or 0.0),
    }
    if isinstance(extra, dict):
        entry.update(extra)
    append_ai_usage_log(entry)
    return entry


def mask(value: str) -> str:
    if not value:
        return ''
    if len(value) <= 4:
        return '*' * len(value)
    return '*' * (len(value) - 4) + value[-4:]


def graph_get(url: str, timeout: int = 60):
    req = urllib.request.Request(url, headers={'User-Agent': 'meta-connection-panel/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        append_system_error_log('meta_http_error', 'Graph GET rejected', method='GET', url=url, status_code=e.code, detail=body)
        raise
    except Exception as e:
        append_system_error_log('external_request_error', 'Graph GET failed', method='GET', url=url, detail=str(e))
        raise


def graph_post(url: str, data: dict):
    encoded = {}
    for k, v in data.items():
        if v is None:
            continue
        if isinstance(v, bool):
            encoded[k] = 'true' if v else 'false'
        else:
            encoded[k] = str(v)
    payload = urllib.parse.urlencode(encoded, quote_via=urllib.parse.quote).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            'User-Agent': 'meta-connection-panel/1.0',
            'Content-Type': 'application/x-www-form-urlencoded',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        append_system_error_log('meta_http_error', 'Graph POST rejected', method='POST', url=url, status_code=e.code, payload=encoded, detail=body)
        raise
    except Exception as e:
        append_system_error_log('external_request_error', 'Graph POST failed', method='POST', url=url, payload=encoded, detail=str(e))
        raise


def graph_delete(url: str):
    req = urllib.request.Request(url, method='DELETE', headers={'User-Agent': 'meta-connection-panel/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        append_system_error_log('meta_http_error', 'Graph DELETE rejected', method='DELETE', url=url, status_code=e.code, detail=body)
        raise
    except Exception as e:
        append_system_error_log('external_request_error', 'Graph DELETE failed', method='DELETE', url=url, detail=str(e))
        raise


def exchange_code_for_token(cfg, code: str):
    app_secret = get_secret(cfg['app_secret_name'])
    callback_url = cfg['public_base_url'].rstrip('/') + cfg['oauth_callback_path']
    params = urllib.parse.urlencode({
        'client_id': cfg['app_id'],
        'redirect_uri': callback_url,
        'client_secret': app_secret,
        'code': code,
    })
    url = f"https://graph.facebook.com/{cfg['graph_api_version']}/oauth/access_token?{params}"
    return graph_get(url)



def fetch_me_accounts(cfg, access_token: str):
    params = urllib.parse.urlencode({
        'fields': 'id,name,access_token,category,tasks,instagram_business_account{id,username,name}',
        'access_token': access_token,
    })
    url = f"https://graph.facebook.com/{cfg['graph_api_version']}/me/accounts?{params}"
    return graph_get(url)


def fetch_ad_accounts(cfg, access_token: str):
    params = urllib.parse.urlencode({
        'fields': 'id,account_id,name,account_status,currency,timezone_name,business{name,id}',
        'access_token': access_token,
    })
    url = f"https://graph.facebook.com/{cfg['graph_api_version']}/me/adaccounts?{params}"
    return graph_get(url)


def get_meta_access_token() -> str:
    session = load_json(META_SESSION_PATH, {})
    return ((session.get('token') or {}).get('access_token')) or ''

def get_linkedin_session():
    return load_json(LINKEDIN_SESSION_PATH, {})


def get_linkedin_access_token() -> str:
    session = get_linkedin_session()
    return (session.get('access_token') or '')


def get_x_session():
    return load_json(X_SESSION_PATH, {})


def get_x_access_token() -> str:
    session = get_x_session()
    return (session.get('access_token') or '')


def _safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def _expiry_from_session(session: dict, issued_keys=None, expires_key: str = 'expires_in') -> dict:
    if not isinstance(session, dict):
        return {'expires_at': 0, 'expires_in': 0, 'expired': False, 'expires_soon': False}
    issued_keys = issued_keys or ['created_at', 'issued_at', 'saved_at', 'updated_at']
    expires_in = _safe_int(session.get(expires_key) or 0, 0)
    issued_at = 0
    for key in issued_keys:
        issued_at = _safe_int(session.get(key) or 0, 0)
        if issued_at:
            break
    expires_at = (issued_at + expires_in) if (issued_at and expires_in) else 0
    now = int(time.time())
    return {
        'expires_at': expires_at,
        'expires_in': expires_in,
        'expired': bool(expires_at and expires_at <= now),
        'expires_soon': bool(expires_at and 0 < (expires_at - now) <= 7 * 24 * 3600),
    }


def get_linkedin_author_urn() -> str:
    session = get_linkedin_session()
    for key in ['author_urn', 'person_urn', 'urn', 'member_urn']:
        v = session.get(key) or ''
        if v:
            return v
    me = session.get('me') or {}
    for key in ['urn', 'person_urn', 'author_urn']:
        v = me.get(key) or ''
        if v:
            return v
    raw_id = me.get('sub') or me.get('id') or session.get('sub') or session.get('id') or ''
    if raw_id:
        return f'urn:li:person:{raw_id}'
    return ''


def linkedin_graph_get(url: str, access_token: str):
    sep = '&' if '?' in url else '?'
    return graph_get(f"{url}{sep}oauth2_access_token={urllib.parse.quote(access_token)}")


def linkedin_graph_post(url: str, access_token: str, data: dict):
    payload = dict(data or {})
    payload['oauth2_access_token'] = access_token
    return graph_post(url, payload)



def _ad_builder_default_targeting(location: str = '', interests=None, gender: str = '', age_min: int = 21, age_max: int = 65):
    interests = [x for x in (interests or []) if x]
    geo = {'countries': ['BR']}
    if location:
        geo['cities'] = [{'key': '2420605', 'name': location, 'radius': 30, 'distance_unit': 'kilometer'}]
    targeting = {
        'age_min': age_min,
        'age_max': age_max,
        'geo_locations': geo,
        'publisher_platforms': ['facebook', 'instagram'],
        'facebook_positions': ['feed', 'marketplace', 'video_feeds', 'right_hand_column'],
        'instagram_positions': ['stream', 'story', 'reels'],
        'device_platforms': ['mobile', 'desktop'],
    }
    if gender == 'male':
        targeting['genders'] = [1]
    elif gender == 'female':
        targeting['genders'] = [2]
    if interests:
        targeting['flexible_spec'] = [{'interests': [{'name': i} for i in interests[:15]]}]
    return targeting

def fetch_ad_account_campaigns(cfg, ad_account_id: str, effective_status=None, limit: str = '100'):
    access_token = get_meta_access_token()
    params = {
        'fields': 'id,name,status,effective_status,objective,configured_status,start_time,stop_time,daily_budget,lifetime_budget',
        'access_token': access_token,
        'limit': limit,
    }
    if effective_status:
        params['effective_status'] = json.dumps(effective_status)
    url = f"https://graph.facebook.com/{cfg['graph_api_version']}/{ad_account_id}/campaigns?{urllib.parse.urlencode(params)}"
    return graph_get(url)


def fetch_ad_account_saved_audiences(cfg, ad_account_id: str, limit: str = '100'):
    access_token = get_meta_access_token()
    params = {
        'fields': 'id,name,description,approximate_count_lower_bound,approximate_count_upper_bound,time_created',
        'access_token': access_token,
        'limit': limit,
    }
    url = f"https://graph.facebook.com/{cfg['graph_api_version']}/{ad_account_id}/saved_audiences?{urllib.parse.urlencode(params)}"
    return graph_get(url)


def fetch_targeting_search(cfg, query: str = '', ad_account_id: str = '', limit: str = '20'):
    access_token = get_meta_access_token()
    params = {
        'type': 'adinterest',
        'q': query,
        'limit': limit,
        'access_token': access_token,
    }
    if ad_account_id:
        params['account_id'] = normalize_ad_account_id(ad_account_id)
    url = f"https://graph.facebook.com/{cfg['graph_api_version']}/search?{urllib.parse.urlencode(params)}"
    return graph_get(url)


def fetch_page_leadgen_forms(cfg, page_id: str, limit: str = '50', timeout: int = 60):
    token = get_page_access_token(page_id)
    params = {
        'fields': 'id,name,status,locale,created_time,follow_up_action_url,questions',
        'access_token': token,
        'limit': limit,
    }
    url = f"https://graph.facebook.com/{cfg['graph_api_version']}/{page_id}/leadgen_forms?{urllib.parse.urlencode(params)}"
    return graph_get(url, timeout=timeout)


def fetch_ad_account_pixels(cfg, ad_account_id: str, limit: str = '50'):
    access_token = get_meta_access_token()
    params = {
        'fields': 'id,name,pixel_id,owner_ad_account{name,id}',
        'access_token': access_token,
        'limit': limit,
    }
    url = f"https://graph.facebook.com/{cfg['graph_api_version']}/{ad_account_id}/adspixels?{urllib.parse.urlencode(params)}"
    return graph_get(url)


def create_campaign_draft(cfg, ad_account_id: str, name: str, objective: str, special_ad_categories=None, status: str = 'PAUSED'):
    access_token = get_meta_access_token()
    url = f"https://graph.facebook.com/{cfg['graph_api_version']}/{ad_account_id}/campaigns"
    data = {
        'name': name,
        'objective': objective,
        'status': status,
        'is_adset_budget_sharing_enabled': True,
        'special_ad_categories': json.dumps(special_ad_categories or []),
        'access_token': access_token,
    }
    return graph_post(url, data)


def create_adset_draft(cfg, ad_account_id: str, campaign_id: str, name: str, optimization_goal: str, billing_event: str, daily_budget: str, targeting: dict, status: str = 'PAUSED', promoted_object=None, bid_strategy: str = 'LOWEST_COST_WITHOUT_CAP'):
    access_token = get_meta_access_token()
    url = f"https://graph.facebook.com/{cfg['graph_api_version']}/{ad_account_id}/adsets"
    data = {
        'name': name,
        'campaign_id': campaign_id,
        'optimization_goal': optimization_goal,
        'billing_event': billing_event,
        'bid_strategy': bid_strategy,
        'daily_budget': daily_budget,
        'is_adset_budget_sharing_enabled': False,
        'targeting': json.dumps(targeting or {}),
        'status': status,
        'access_token': access_token,
    }
    if promoted_object:
        data['promoted_object'] = json.dumps(promoted_object)
    return graph_post(url, data)


def create_adcreative_draft(cfg, ad_account_id: str, name: str, page_id: str = '', instagram_actor_id: str = '', image_url: str = '', image_hash: str = '', message: str = '', link: str = '', call_to_action_type: str = 'LEARN_MORE'):
    access_token = get_meta_access_token()
    url = f"https://graph.facebook.com/{cfg['graph_api_version']}/{ad_account_id}/adcreatives"
    object_story_spec = {
        'page_id': page_id,
        'link_data': {
            'message': message,
            'link': link,
            'call_to_action': {
                'type': call_to_action_type,
                'value': {'link': link}
            }
        }
    }
    if instagram_actor_id:
        object_story_spec['instagram_actor_id'] = instagram_actor_id
    if image_hash:
        object_story_spec['link_data']['image_hash'] = image_hash
    elif image_url:
        object_story_spec['link_data']['picture'] = image_url
    data = {
        'name': name,
        'object_story_spec': json.dumps(object_story_spec),
        'access_token': access_token,
    }
    return graph_post(url, data)


def create_ad_draft(cfg, ad_account_id: str, name: str, adset_id: str, creative_id: str, status: str = 'PAUSED'):
    access_token = get_meta_access_token()
    url = f"https://graph.facebook.com/{cfg['graph_api_version']}/{ad_account_id}/ads"
    data = {
        'name': name,
        'adset_id': adset_id,
        'creative': json.dumps({'creative_id': creative_id}),
        'status': status,
        'access_token': access_token,
    }
    return graph_post(url, data)


def update_meta_object(cfg, object_id: str, fields: dict):
    access_token = get_meta_access_token()
    url = f"https://graph.facebook.com/{cfg['graph_api_version']}/{object_id}"
    data = dict(fields or {})
    data['access_token'] = access_token
    return graph_post(url, data)


def fetch_me(cfg, access_token: str):
    params = urllib.parse.urlencode({
        'fields': 'id,name',
        'access_token': access_token,
    })
    url = f"https://graph.facebook.com/{cfg['graph_api_version']}/me?{params}"
    return graph_get(url)


def get_page_access_token(page_id: str):
    session = load_json(META_SESSION_PATH, {})
    for page in session.get('pages', []):
        if str(page.get('id')) == str(page_id):
            return page.get('access_token', '')
    return ''


def get_page_record(page_id: str = '', ig_user_id: str = '', username: str = ''):
    session = load_json(META_SESSION_PATH, {})
    username = (username or '').lstrip('@').strip().lower()
    for page in session.get('pages', []):
        ig = page.get('instagram_business_account') or {}
        if page_id and str(page.get('id')) == str(page_id):
            return page
        if ig_user_id and str(ig.get('id')) == str(ig_user_id):
            return page
        if username and str(ig.get('username', '')).lower() == username:
            return page
    return None




def _meta_session_for_request(panel_user_email: str = '') -> dict:
    return get_meta_session_for_panel_user(panel_user_email) if panel_user_email else (load_json(META_SESSION_PATH, {}) or {})


def get_page_access_token_for_user(page_id: str, panel_user_email: str = ''):
    session = _meta_session_for_request(panel_user_email)
    for page in (session.get('pages') or []):
        if str((page or {}).get('id')) == str(page_id):
            return (page or {}).get('access_token', '')
    return get_page_access_token(page_id)


def get_page_record_for_user(page_id: str = '', ig_user_id: str = '', username: str = '', panel_user_email: str = ''):
    session = _meta_session_for_request(panel_user_email)
    username = (username or '').lstrip('@').strip().lower()
    for page in (session.get('pages') or []):
        ig = (page or {}).get('instagram_business_account') or {}
        if page_id and str((page or {}).get('id')) == str(page_id):
            return page
        if ig_user_id and str(ig.get('id')) == str(ig_user_id):
            return page
        if username and str(ig.get('username', '')).lower() == username:
            return page
    return get_page_record(page_id=page_id, ig_user_id=ig_user_id, username=username)


def _extract_text_from_graph_result(result: dict) -> str:
    lines = []
    items = []
    if isinstance(result, dict):
        items = result.get('data') or result.get('result', {}).get('data') or []
    for item in items if isinstance(items, list) else []:
        name = item.get('name') or item.get('title') or ''
        values = item.get('values') or []
        if values and isinstance(values, list):
            latest = values[-1] or {}
            val = latest.get('value')
        else:
            val = item.get('value')
        lines.append(f'- {name}: {val}')
    return '\n'.join(lines)


def analyze_brand_profile_with_ai(meta_context: dict) -> dict:
    prompt = (
        'Você é um estrategista de marca e social media sênior. '
        'Analise os dados reais vindos da Meta API e devolva SOMENTE JSON válido. '
        'Preencha campos práticos para um painel SaaS de brand profile. '
        'Não invente fatos muito específicos além do que os dados sugerem; quando inferir, faça inferências prudentes. '
        'Use português do Brasil. '
        'Retorne JSON com as chaves: '
        'brand_name, tagline, description, tone, target_audience, key_products, visual_style, colors, '
        'cta_style, best_offer, competitors, instagram_handle, facebook_page_name, insights_summary, '
        'recommended_posts, positioning, bio_summary, negative_rules, text_rule. '
        'As chaves key_products, colors, competitors e recommended_posts devem ser arrays. '
        'Dados de entrada: ' + json.dumps(meta_context, ensure_ascii=False)
    )
    result = _ai_generate_text('brand_analysis', prompt, 90, json_mode=True)
    raw = result.get('text', '')
    parsed = _extract_json_block(raw)
    if not isinstance(parsed, dict):
        raise ValueError('invalid_ai_json')
    parsed['_ai_model'] = result.get('model', '')
    parsed['_ai_provider'] = result.get('provider', '')
    parsed['_ai_usage'] = result.get('usage', {})
    parsed['_ai_cost_usd'] = result.get('cost_usd', 0.0)
    return parsed


def fetch_instagram_media_list(cfg, ig_user_id: str, access_token: str, limit: int = 12):
    params = urllib.parse.urlencode({
        'fields': 'id,caption,media_type,media_url,permalink,thumbnail_url,timestamp,like_count,comments_count',
        'limit': str(limit),
        'access_token': access_token,
    })
    url = f"https://graph.facebook.com/{cfg['graph_api_version']}/{ig_user_id}/media?{params}"
    return graph_get(url)


def collect_brand_meta_context(cfg, page_id: str, panel_user_email: str = '') -> dict:
    page = get_page_record_for_user(page_id=page_id, panel_user_email=panel_user_email) or {}
    if not page:
        raise ValueError('page_not_found')
    token = page.get('access_token') or get_page_access_token_for_user(page_id, panel_user_email)
    if not token:
        raise ValueError('page_access_token_not_found')
    context = {
        'page': {
            'id': page.get('id', ''),
            'name': page.get('name', ''),
            'category': page.get('category', ''),
            'tasks': page.get('tasks', []),
        },
        'instagram': {},
        'page_insights': {},
        'instagram_insights': {},
        'media_samples': [],
    }
    try:
        page_params = urllib.parse.urlencode({'fields': 'picture.type(large),name,fan_count,about,website,phone,location,category', 'access_token': token})
        page_url = f"https://graph.facebook.com/{cfg['graph_api_version']}/{page_id}?{page_params}"
        page_data = graph_get(page_url)
        context['page'].update(page_data)
    except Exception as e:
        context['page_error'] = str(e)
    try:
        page_ins = fetch_page_insights(
            cfg,
            page_id,
            'page_engagement,page_impressions,page_impressions_unique,page_engaged_users',
            'days_28',
        )
        context['page_insights'] = page_ins
        context['page_insights_summary'] = _extract_text_from_graph_result(page_ins)
    except Exception as e:
        context['page_insights_error'] = str(e)
    ig = page.get('instagram_business_account') or {}
    if ig.get('id'):
        context['instagram'] = ig
        try:
            ig_params = urllib.parse.urlencode({'fields': 'profile_picture_url,username,name,biography,followers_count,follows_count,media_count,website', 'access_token': token})
            ig_url = f"https://graph.facebook.com/{cfg['graph_api_version']}/{ig.get('id')}?{ig_params}"
            ig_data = graph_get(ig_url)
            context['instagram'].update(ig_data)
        except Exception as e:
            context['instagram_error'] = str(e)
        try:
            ig_ins = instagram_account_insights(cfg, ig.get('id', ''), token, 'reach,profile_views,impressions', 'days_28')
            context['instagram_insights'] = ig_ins
            context['instagram_insights_summary'] = _extract_text_from_graph_result(ig_ins)
        except Exception as e:
            context['instagram_insights_error'] = str(e)
        try:
            media = fetch_instagram_media_list(cfg, ig.get('id', ''), token, 9)
            context['media_samples'] = media.get('data', []) if isinstance(media, dict) else []
        except Exception as e:
            context['media_error'] = str(e)
    return context

def refresh_pages_from_general_token(cfg):
    access_token = get_meta_access_token()
    if not access_token:
        return []
    accounts = fetch_me_accounts(cfg, access_token).get('data', [])
    session = load_json(META_SESSION_PATH, {})
    session['pages'] = accounts
    save_json(META_SESSION_PATH, session)
    return accounts


def fetch_page_posts(cfg, page_id: str):
    token = get_page_access_token(page_id)
    params = urllib.parse.urlencode({
        'fields': 'id,created_time,message,permalink_url,attachments',
        'access_token': token,
    })
    url = f"https://graph.facebook.com/{cfg['graph_api_version']}/{page_id}/feed?{params}"
    return graph_get(url)


def create_page_post(cfg, page_id: str, message: str, link: str = '', published: str = 'true', scheduled_publish_time: str = ''):
    token = get_page_access_token(page_id)
    url = f"https://graph.facebook.com/{cfg['graph_api_version']}/{page_id}/feed"
    data = {
        'message': message,
        'link': link or None,
        'published': published,
        'scheduled_publish_time': scheduled_publish_time or None,
        'access_token': token,
    }
    return graph_post(url, data)


def create_page_photo_post(cfg, page_id: str, image_url: str, caption: str = '', published: str = 'true', scheduled_publish_time: str = ''):
    token = get_page_access_token(page_id)
    url = f"https://graph.facebook.com/{cfg['graph_api_version']}/{page_id}/photos"
    data = {
        'url': image_url,
        'caption': caption or None,
        'published': published,
        'scheduled_publish_time': scheduled_publish_time or None,
        'access_token': token,
    }
    return graph_post(url, data)


def update_page_post(cfg, post_id: str, message: str):
    session = load_json(META_SESSION_PATH, {})
    token = ((session.get('token') or {}).get('access_token')) or ''
    url = f"https://graph.facebook.com/{cfg['graph_api_version']}/{post_id}"
    return graph_post(url, {'message': message, 'access_token': token})


def delete_page_post(cfg, post_id: str):
    session = load_json(META_SESSION_PATH, {})
    token = ((session.get('token') or {}).get('access_token')) or ''
    params = urllib.parse.urlencode({'access_token': token})
    url = f"https://graph.facebook.com/{cfg['graph_api_version']}/{post_id}?{params}"
    return graph_delete(url)


def _call_gemini(api_key: str, model: str, prompt: str, timeout: int = 60):
    """Call a Gemini model and return parsed JSON {copy, image_prompt} or raise."""
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}'
    payload = {
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {'responseMimeType': 'application/json'},
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    text_parts = []
    for cand in data.get('candidates') or []:
        for part in ((cand.get('content') or {}).get('parts') or []):
            if part.get('text'):
                text_parts.append(part['text'])
    raw = '\n'.join(text_parts).strip()
    parsed = _extract_json_block(raw) if raw else {}
    copy = _coerce_text(parsed.get('copy'))
    image_prompt = _coerce_text(parsed.get('image_prompt'))
    if not copy or not image_prompt:
        raise ValueError('empty response from model')
    return copy, image_prompt


def _call_gemini_json(api_key: str, model: str, prompt: str, timeout: int = 60) -> tuple:
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}'
    payload = {
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {'responseMimeType': 'application/json'},
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    text_parts = []
    for cand in data.get('candidates') or []:
        for part in ((cand.get('content') or {}).get('parts') or []):
            if part.get('text'):
                text_parts.append(part['text'])
    raw = '\n'.join(text_parts).strip()
    return raw, _extract_usage_from_gemini_response(data)


def _call_gemini_text(api_key: str, model: str, prompt: str, timeout: int = 60) -> str:
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}'
    payload = {
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {'responseMimeType': 'text/plain'},
    }
    body_bytes = json.dumps(payload).encode('utf-8')
    data = None
    for attempt in range(4):
        req = urllib.request.Request(url, data=body_bytes, headers={'Content-Type': 'application/json'}, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            break
        except urllib.error.HTTPError as e:
            try:
                e.read()
            except Exception:
                pass
            if e.code in (429, 503) and attempt < 3:
                time.sleep(min(8.0, 1.2 * (2 ** attempt)))
                continue
            raise
    if not data:
        raise RuntimeError('resposta vazia da API Gemini')
    text_parts = []
    for cand in data.get('candidates') or []:
        for part in ((cand.get('content') or {}).get('parts') or []):
            if part.get('text'):
                text_parts.append(part['text'])
    return '\n'.join(text_parts).strip()


def _call_gemini_text_with_usage(api_key: str, model: str, prompt: str, timeout: int = 60) -> tuple:
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}'
    payload = {
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {'responseMimeType': 'text/plain'},
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    text_parts = []
    for cand in data.get('candidates') or []:
        for part in ((cand.get('content') or {}).get('parts') or []):
            if part.get('text'):
                text_parts.append(part['text'])
    return '\n'.join(text_parts).strip(), _extract_usage_from_gemini_response(data)


def _openai_api_key() -> str:
    return get_secret(OPENAI_API_KEY_NAME) or ''


def _openai_base_url() -> str:
    return (get_secret(OPENAI_BASE_URL_NAME) or 'https://api.openai.com/v1').rstrip('/')


def _anthropic_api_key() -> str:
    return get_secret(ANTHROPIC_API_KEY_NAME) or ''


def _fetch_gemini_models(api_key: str) -> list:
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models?key={urllib.parse.quote(api_key)}",
        headers={'Content-Type': 'application/json'},
        method='GET',
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    models = []
    for item in data.get('models') or []:
        name = str(item.get('name') or '')
        if not name:
            continue
        mid = name.replace('models/', '')
        methods = item.get('supportedGenerationMethods') or []
        if 'generateContent' in methods:
            models.append(mid)
    return sorted(set(models))


def _fetch_claude_models(api_key: str) -> list:
    req = urllib.request.Request(
        'https://api.anthropic.com/v1/models',
        headers={
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json',
        },
        method='GET',
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    models = []
    for item in data.get('data') or []:
        mid = str(item.get('id') or '').strip()
        if mid:
            models.append(mid)
    return sorted(set(models))


def _call_claude_chat(prompt: str, model: str, api_key: str, timeout: int = 90, system: str = '') -> tuple:
    payload = {
        'model': model,
        'max_tokens': 8192,
        'messages': [{'role': 'user', 'content': prompt}],
    }
    if system:
        payload['system'] = system
    body = json.dumps(payload).encode('utf-8')
    data = None
    last_err = None
    for attempt in range(4):
        req = urllib.request.Request(
            'https://api.anthropic.com/v1/messages',
            data=body,
            headers={
                'x-api-key': api_key,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            },
            method='POST',
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            break
        except urllib.error.HTTPError as e:
            last_err = e
            try:
                body_err = e.read().decode('utf-8', errors='replace')
            except Exception:
                body_err = str(e)
            if e.code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(min(10.0, 1.5 * (2 ** attempt)))
                continue
            raise RuntimeError(body_err)
    if data is None and last_err:
        raise last_err
    parts = []
    for item in data.get('content') or []:
        if item.get('type') == 'text' and item.get('text'):
            parts.append(item.get('text'))
    return '\n'.join(parts).strip(), _extract_usage_from_claude_response(data)


def _call_openai_chat(prompt: str, model: str, api_key: str, json_mode: bool = False, timeout: int = 90, system: str = '') -> tuple:
    messages = []
    if system:
        messages.append({'role': 'system', 'content': system})
    messages.append({'role': 'user', 'content': prompt})
    payload = {
        'model': model,
        'messages': messages,
    }
    if json_mode:
        payload['response_format'] = {'type': 'json_object'}
    body = json.dumps(payload).encode('utf-8')
    data = None
    last_err = None
    for attempt in range(4):
        req = urllib.request.Request(
            f"{_openai_base_url()}/chat/completions",
            data=body,
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            method='POST',
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            break
        except urllib.error.HTTPError as e:
            last_err = e
            try:
                body_err = e.read().decode('utf-8', errors='replace')
            except Exception:
                body_err = str(e)
            if e.code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(min(10.0, 1.5 * (2 ** attempt)))
                continue
            raise RuntimeError(body_err)
    if data is None and last_err:
        raise last_err
    content = (((data.get('choices') or [{}])[0].get('message') or {}).get('content') or '').strip()
    return content, _extract_usage_from_openai_response(data)


def _openai_model_uses_responses_api(model: str) -> bool:
    model = str(model or '').strip().lower()
    return model.startswith('gpt-5') or model.startswith('o')


def _extract_openai_responses_text(data: dict) -> str:
    text = str(data.get('output_text') or '').strip()
    if text:
        return text
    parts = []
    for item in data.get('output') or []:
        for content in item.get('content') or []:
            if content.get('type') in {'output_text', 'text'} and content.get('text'):
                parts.append(str(content.get('text')))
    return '\n'.join(parts).strip()


def _call_openai_responses(prompt: str, model: str, api_key: str, json_mode: bool = False, timeout: int = 90, system: str = '') -> tuple:
    payload = {
        'model': model,
        'input': [],
    }
    if system:
        payload['input'].append({
            'role': 'system',
            'content': [{'type': 'input_text', 'text': system}],
        })
    payload['input'].append({
        'role': 'user',
        'content': [{'type': 'input_text', 'text': prompt}],
    })
    if json_mode:
        payload['text'] = {'format': {'type': 'json_object'}}
    body = json.dumps(payload).encode('utf-8')
    data = None
    last_err = None
    for attempt in range(4):
        req = urllib.request.Request(
            f"{_openai_base_url()}/responses",
            data=body,
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            method='POST',
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            break
        except urllib.error.HTTPError as e:
            last_err = e
            try:
                body_err = e.read().decode('utf-8', errors='replace')
            except Exception:
                body_err = str(e)
            if e.code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(min(10.0, 1.5 * (2 ** attempt)))
                continue
            raise RuntimeError(body_err)
    if data is None and last_err:
        raise last_err
    content = _extract_openai_responses_text(data or {})
    return content, _extract_usage_from_openai_responses(data or {})


def _summarize_ai_exception(exc: Exception) -> str:
    if exc is None:
        return ''
    return f'{type(exc).__name__}: {exc}'


def _call_openai_image(prompt: str, model: str, api_key: str, size: str = '1024x1024', quality: str = 'standard', background: str = 'auto', output_format: str = 'png', moderation: str = 'auto', timeout: int = 180) -> dict:
    quality = _normalize_openai_image_quality(model, quality)
    payload = {
        'model': model,
        'prompt': prompt,
        'size': size,
        'n': 1,
    }
    if model == 'dall-e-3':
        payload['response_format'] = 'b64_json'
        payload['quality'] = quality
    elif model == 'dall-e-2':
        payload['response_format'] = 'b64_json'
    if model.startswith('gpt-image-'):
        payload['quality'] = quality
        payload['background'] = background or 'auto'
        payload['output_format'] = output_format or 'png'
        payload['moderation'] = moderation or 'auto'
    body = json.dumps(payload).encode('utf-8')
    last_err = None
    for attempt in range(4):
        req = urllib.request.Request(
            f"{_openai_base_url()}/images/generations",
            data=body,
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            method='POST',
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            last_err = e
            try:
                body_err = e.read().decode('utf-8', errors='replace')
            except Exception:
                body_err = str(e)
            if e.code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(min(12.0, 1.5 * (2 ** attempt)))
                continue
            raise RuntimeError(body_err)
    if last_err:
        raise last_err
    raise RuntimeError('openai_image_failed')


def _fit_openai_image_prompt(prompt: str, model: str) -> tuple[str, bool, int]:
    text = str(prompt or '').strip()
    limit = int(OPENAI_IMAGE_PROMPT_LIMITS.get(model, 1000))
    if len(text) <= limit:
        return text, False, limit
    clipped = text[:limit]
    for sep in ('\n\n', '\n', '. ', '; ', ', '):
        idx = clipped.rfind(sep)
        if idx >= int(limit * 0.7):
            clipped = clipped[: idx + len(sep)].strip()
            break
    if not clipped:
        clipped = text[:limit].strip()
    return clipped, True, limit


def _normalize_openai_image_quality(model: str, quality: str) -> str:
    value = str(quality or '').strip().lower()
    if model.startswith('gpt-image-'):
        return value if value in {'low', 'medium', 'high', 'auto'} else 'auto'
    if model == 'dall-e-3':
        return value if value in {'standard', 'hd'} else 'standard'
    return 'standard'


def _merge_usage(left: dict, right: dict) -> dict:
    left = left or {}
    right = right or {}
    return {
        'input_tokens': int(left.get('input_tokens', 0) or 0) + int(right.get('input_tokens', 0) or 0),
        'output_tokens': int(left.get('output_tokens', 0) or 0) + int(right.get('output_tokens', 0) or 0),
        'total_tokens': int(left.get('total_tokens', 0) or 0) + int(right.get('total_tokens', 0) or 0),
    }


def _fetch_openai_models(api_key: str) -> list:
    req = urllib.request.Request(
        f"{_openai_base_url()}/models",
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
        method='GET',
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    items = []
    for item in data.get('data') or []:
        mid = str(item.get('id') or '').strip()
        if not mid:
            continue
        items.append(mid)
    return sorted(items)


# Ordem: modelos estáveis primeiro; inclui Gemma (pode não existir na API — ignoramos com fallback)
GEMINI_TEXT_MODEL_FALLBACK = [
    ('gemini-2.0-flash', 60),
    ('gemini-2.0-flash-001', 60),
    ('gemini-2.5-flash', 60),
    ('gemini-2.5-flash-lite', 45),
    ('gemini-flash-latest', 45),
    ('gemini-1.5-flash', 55),
    ('gemini-1.5-flash-8b', 50),
    ('gemini-1.5-pro', 90),
    ('gemma-3-27b-it', 60),
    ('gemma-2-27b-it', 60),
    ('gemma-2-9b-it', 45),
]


def _call_gemini_text_with_fallback(api_key: str, prompt: str, timeout_default: int = 60) -> tuple:
    """Returns (text, model_used). Raises last error if all models fail."""
    last_err = None
    for model, tmo in GEMINI_TEXT_MODEL_FALLBACK:
        try:
            text = _call_gemini_text(api_key, model, prompt, min(timeout_default, tmo))
            if (text or '').strip():
                return text.strip(), model
        except Exception as e:
            last_err = e
            continue
    if last_err:
        raise last_err
    raise ValueError('empty response from all Gemini/Gemma models')


def _ai_generate_text(feature: str, prompt: str, timeout_default: int = 60, json_mode: bool = False, system: str = '') -> tuple:
    route = _ai_route(feature)
    provider = route.get('provider', 'gemini')
    model = route.get('model', '')
    if provider == 'openai':
        api_key = _openai_api_key()
        if not api_key:
            raise ValueError('openai_not_configured')
        chain = []
        if model:
            chain.append(model)
        for fallback_model in OPENAI_TEXT_MODEL_FALLBACK:
            if fallback_model not in chain:
                chain.append(fallback_model)
        last_err = None
        text = ''
        usage = {}
        selected_model = chain[0]
        attempts = []
        for selected_model in chain:
            try:
                if _openai_model_uses_responses_api(selected_model):
                    text, usage = _call_openai_responses(prompt, selected_model, api_key, json_mode=json_mode, timeout=timeout_default, system=system)
                else:
                    text, usage = _call_openai_chat(prompt, selected_model, api_key, json_mode=json_mode, timeout=timeout_default, system=system)
                if (text or '').strip():
                    break
                attempts.append({'model': selected_model, 'api': 'responses' if _openai_model_uses_responses_api(selected_model) else 'chat_completions', 'error': 'empty_response'})
            except Exception as e:
                last_err = e
                attempts.append({'model': selected_model, 'api': 'responses' if _openai_model_uses_responses_api(selected_model) else 'chat_completions', 'error': _summarize_ai_exception(e)})
                continue
        if not (text or '').strip():
            detail = last_err or ValueError('openai_empty_response')
            raise RuntimeError(json.dumps({
                'provider': 'openai',
                'feature': feature,
                'attempts': attempts,
                'final_error': _summarize_ai_exception(detail),
            }, ensure_ascii=False))
        return {
            'provider': 'openai',
            'model': selected_model,
            'text': text,
            'usage': usage,
            'cost_usd': _calculate_ai_cost('openai', selected_model, usage),
        }

    if provider == 'claude':
        api_key = _anthropic_api_key()
        if not api_key:
            raise ValueError('anthropic_not_configured')
        chain = []
        if model:
            chain.append(model)
        for fallback_model in CLAUDE_TEXT_MODEL_FALLBACK:
            if fallback_model not in chain:
                chain.append(fallback_model)
        last_err = None
        text = ''
        usage = {}
        selected_model = chain[0]
        attempts = []
        for selected_model in chain:
            try:
                text, usage = _call_claude_chat(prompt, selected_model, api_key, timeout=timeout_default, system=system)
                if (text or '').strip():
                    break
                attempts.append({'model': selected_model, 'error': 'empty_response'})
            except Exception as e:
                last_err = e
                attempts.append({'model': selected_model, 'error': _summarize_ai_exception(e)})
                continue
        if not (text or '').strip():
            detail = last_err or ValueError('claude_empty_response')
            raise RuntimeError(json.dumps({
                'provider': 'claude',
                'feature': feature,
                'attempts': attempts,
                'final_error': _summarize_ai_exception(detail),
            }, ensure_ascii=False))
        return {
            'provider': 'claude',
            'model': selected_model,
            'text': text,
            'usage': usage,
            'cost_usd': _calculate_ai_cost('claude', selected_model, usage),
        }

    api_key = get_secret(GEMINI_API_KEY_NAME) or get_secret('GOOGLE_API_KEY')
    if not api_key:
        raise ValueError('gemini_not_configured')
    if model:
        if json_mode:
            text, usage = _call_gemini_json(api_key, model, prompt, timeout_default)
        else:
            text, usage = _call_gemini_text_with_usage(api_key, model, prompt, timeout_default)
        return {
            'provider': 'gemini',
            'model': model,
            'text': text,
            'usage': usage,
            'cost_usd': _calculate_ai_cost('gemini', model, usage),
        }
    if json_mode:
        last_err = None
        for fallback_model, tmo in GEMINI_TEXT_MODEL_FALLBACK:
            try:
                text, usage = _call_gemini_json(api_key, fallback_model, prompt, min(timeout_default, tmo))
                return {
                    'provider': 'gemini',
                    'model': fallback_model,
                    'text': text,
                    'usage': usage,
                    'cost_usd': _calculate_ai_cost('gemini', fallback_model, usage),
                }
            except Exception as e:
                last_err = e
                continue
        raise last_err or ValueError('gemini_json_empty_response')
    text, model_used = _call_gemini_text_with_fallback(api_key, prompt, timeout_default)
    usage = {
        'input_tokens': _estimate_text_tokens(prompt),
        'output_tokens': _estimate_text_tokens(text),
        'total_tokens': _estimate_text_tokens(prompt) + _estimate_text_tokens(text),
    }
    return {
        'provider': 'gemini',
        'model': model_used,
        'text': text,
        'usage': usage,
        'cost_usd': _calculate_ai_cost('gemini', model_used, usage),
    }


def _coerce_text(value, fallback: str = '') -> str:
    if value is None:
        return fallback
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (dict, list, tuple)):
        try:
            return json.dumps(value, ensure_ascii=False).strip()
        except Exception:
            return fallback
    return str(value).strip()


def _compact_report_for_ai(report: dict) -> dict:
    """Reduz tokens no prompt da IA mantendo foco em resultados, custos e estrutura."""
    totals = report.get('totals') or {}
    actions = totals.get('actions') or {}

    def _f(v):
        try:
            return float(str(v).replace(',', ''))
        except Exception:
            return 0.0

    def _pick(*keys):
        total = 0.0
        found = []
        for k in keys:
            if k in actions:
                val = _f(actions.get(k))
                if val > 0:
                    total += val
                    found.append(k)
        return {'value': total, 'keys': found}

    result_groups = {
        'mensagens': _pick(
            'onsite_conversion.total_messaging_connection',
            'onsite_conversion.messaging_conversation_started_7d',
            'onsite_conversion.messaging_first_reply',
        ),
        'cadastros': _pick(
            'lead',
            'onsite_conversion.lead_grouped',
            'offsite_complete_registration_add_meta_leads',
            'offsite_search_add_meta_leads',
            'offsite_content_view_add_meta_leads',
        ),
        'compras': _pick(
            'purchase',
            'omni_purchase',
            'offsite_conversion.fb_pixel_purchase',
            'web_in_store_purchase',
            'onsite_web_purchase',
            'onsite_web_app_purchase',
            'web_app_in_store_purchase',
        ),
        'checkout': _pick(
            'initiate_checkout',
            'omni_initiated_checkout',
            'offsite_conversion.fb_pixel_initiate_checkout',
            'onsite_web_initiate_checkout',
        ),
        'add_to_cart': _pick(
            'add_to_cart',
            'omni_add_to_cart',
            'offsite_conversion.fb_pixel_add_to_cart',
            'onsite_web_add_to_cart',
            'onsite_web_app_add_to_cart',
        ),
        'landing_page_view': _pick(
            'landing_page_view',
            'omni_landing_page_view',
        ),
        'link_click': _pick('link_click'),
    }

    spend = _f(totals.get('spend'))
    headline = {}
    for name, meta in result_groups.items():
        value = meta.get('value', 0.0)
        if value > 0:
            headline[name] = {
                'value': value,
                'custo_por_resultado': round(spend / value, 2) if spend > 0 else 0,
                'source_keys': meta.get('keys', []),
            }

    ranked = []
    for k, v in actions.items():
        ranked.append((k, _f(v)))
    ranked.sort(key=lambda x: -x[1])
    top_actions = {k: v for k, v in ranked[:12] if v > 0}

    camps = report.get('campaigns') or []
    objective_mix = {}
    status_mix = {}
    active_count = 0
    paused_count = 0
    camp_sample = []
    for c in camps[:40]:
        obj = c.get('objective_label') or objective_label_pt(c.get('objective') or 'UNKNOWN')
        st = c.get('effective_status') or c.get('status') or 'UNKNOWN'
        objective_mix[obj] = objective_mix.get(obj, 0) + 1
        status_mix[st] = status_mix.get(st, 0) + 1
        if st == 'ACTIVE':
            active_count += 1
        if st == 'PAUSED':
            paused_count += 1
        camp_sample.append({
            'name': (c.get('name') or '')[:100],
            'objective': obj,
            'status': st,
            'daily_budget': c.get('daily_budget'),
            'leads': c.get('leads', 0),
            'messages': c.get('messages', 0),
            'purchases': c.get('purchases', 0),
            'spend_30d': c.get('spend_30d', 0),
            'ctr_30d': c.get('ctr_30d', 0),
            'cpc_30d': c.get('cpc_30d', 0),
        })

    return {
        'ad_account_id': report.get('ad_account_id'),
        'date_preset': report.get('date_preset'),
        'totals': {
            'spend': totals.get('spend'),
            'impressions': totals.get('impressions'),
            'reach': totals.get('reach'),
            'clicks': totals.get('clicks'),
            'ctr': totals.get('ctr'),
            'cpc': totals.get('cpc'),
            'cpm': totals.get('cpm'),
        },
        'headline_results': headline,
        'top_actions': top_actions,
        'counts': report.get('counts'),
        'campaign_objective_mix': objective_mix,
        'campaign_status_mix': status_mix,
        'campaign_status_summary': {
            'active': active_count,
            'paused': paused_count,
            'total_campaigns_seen': len(camps),
        },
        'campaigns_sample': camp_sample,
        'top_campaigns_by_leads': sorted([c for c in camp_sample if (c.get('leads') or 0) > 0], key=lambda x: -(x.get('leads') or 0))[:8],
        'note': 'Métricas agregadas da conta e métricas reais por campanha no período. Use os números reais de campanhas ativas, pausadas, mix de objetivos e resultados já puxados; não invente dados.',
    }




def load_ads_reports_history() -> dict:
    return load_json(ADS_REPORTS_HISTORY_PATH, {}) or {}

def save_ads_reports_history(data: dict):
    save_json(ADS_REPORTS_HISTORY_PATH, data or {})

def append_ads_report_history(ad_account_id: str, payload: dict):
    ad_account_id = normalize_ad_account_id(ad_account_id)
    if not ad_account_id:
        return
    db = load_ads_reports_history()
    items = db.get(ad_account_id, []) if isinstance(db.get(ad_account_id, []), list) else []
    items.append(payload)
    db[ad_account_id] = items[-50:]
    save_ads_reports_history(db)


def load_profile_followers_daily() -> dict:
    return load_json(PROFILE_FOLLOWERS_DAILY_PATH, {}) or {}


def save_profile_followers_daily(data: dict):
    save_json(PROFILE_FOLLOWERS_DAILY_PATH, data or {})


def store_profile_followers_snapshot(profile_key: str, followers_count, username: str = '', page_id: str = ''):
    if not profile_key:
        return
    today = time.strftime('%Y-%m-%d')
    db = load_profile_followers_daily()
    items = db.get(profile_key, []) if isinstance(db.get(profile_key, []), list) else []
    items = [x for x in items if x.get('date') != today]
    items.append({'date': today, 'followers_count': followers_count, 'username': username, 'page_id': page_id})
    db[profile_key] = items[-120:]
    save_profile_followers_daily(db)


def _pct_change(current, past):
    try:
        c = float(current)
        p = float(past)
        if p <= 0:
            return None
        return round(((c - p) / p) * 100.0, 2)
    except Exception:
        return None


def followers_growth_summary(profile_key: str, current_count):
    db = load_profile_followers_daily()
    items = db.get(profile_key, []) if isinstance(db.get(profile_key, []), list) else []
    weekly_base = items[-8]['followers_count'] if len(items) >= 8 else None
    monthly_base = items[-31]['followers_count'] if len(items) >= 31 else None
    return {
        'weekly_pct': _pct_change(current_count, weekly_base) if weekly_base is not None else None,
        'monthly_pct': _pct_change(current_count, monthly_base) if monthly_base is not None else None,
        'points': items[-31:],
    }

def load_ad_account_memory() -> dict:
    return load_json(AD_ACCOUNT_MEMORY_PATH, {}) or {}

def save_ad_account_memory(data: dict):
    save_json(AD_ACCOUNT_MEMORY_PATH, data or {})

def update_ad_account_memory_snapshot(ad_account_id: str, report: dict):
    ad_account_id = normalize_ad_account_id(ad_account_id)
    if not ad_account_id:
        return
    mem = load_ad_account_memory()
    entry = mem.get(ad_account_id, {}) if isinstance(mem, dict) else {}
    totals = (report or {}).get('totals') or {}
    campaigns = (report or {}).get('campaigns') or []
    actions = totals.get('actions') or {}
    demographics = (report or {}).get('demographics') or []

    def _f(v):
        try:
            return float(str(v).replace(',', ''))
        except Exception:
            return 0.0

    objective_summary = {}
    for c in campaigns:
        obj = objective_label_pt((c or {}).get('objective', ''))
        objective_summary[obj] = objective_summary.get(obj, 0) + 1

    top_demographics = sorted(demographics, key=lambda d: _f((d or {}).get('spend')), reverse=True)[:8]

    result_memory = {
        'mensagens': actions.get('onsite_conversion.total_messaging_connection') or actions.get('onsite_conversion.messaging_conversation_started_7d') or actions.get('onsite_conversion.messaging_first_reply') or '0',
        'cadastros': actions.get('lead') or actions.get('onsite_conversion.lead_grouped') or actions.get('offsite_complete_registration_add_meta_leads') or '0',
        'compras': actions.get('purchase') or actions.get('omni_purchase') or actions.get('offsite_conversion.fb_pixel_purchase') or '0',
        'checkout': actions.get('initiate_checkout') or actions.get('omni_initiated_checkout') or actions.get('offsite_conversion.fb_pixel_initiate_checkout') or '0',
    }

    history = entry.get('history', []) if isinstance(entry.get('history', []), list) else []
    history.append({
        'ts': int(time.time()),
        'spend': totals.get('spend'),
        'ctr': totals.get('ctr'),
        'cpc': totals.get('cpc'),
        'objective_labels': sorted(list(objective_summary.keys())),
        'results': result_memory,
    })
    history = history[-12:]

    entry.update({
        'ad_account_id': ad_account_id,
        'updated_at': int(time.time()),
        'objective_labels': sorted(list(objective_summary.keys())),
        'objective_mix': objective_summary,
        'top_campaign_names': [((c or {}).get('name') or '')[:100] for c in campaigns[:12]],
        'top_actions': actions,
        'top_demographics': top_demographics,
        'best_known_results': result_memory,
        'history': history,
        'totals': {
            'spend': totals.get('spend'),
            'clicks': totals.get('clicks'),
            'ctr': totals.get('ctr'),
            'cpc': totals.get('cpc'),
            'cpm': totals.get('cpm'),
        },
    })
    mem[ad_account_id] = entry
    save_ad_account_memory(mem)

def normalize_ad_account_id(ad_account_id: str) -> str:
    s = (ad_account_id or '').strip()
    if not s:
        return ''
    if s.startswith('act_'):
        return s
    return 'act_' + s.lstrip('act_')



def fetch_campaign_insights(cfg, campaign_id: str, date_preset: str = 'last_30d'):
    access_token = get_meta_access_token()
    params = {
        'fields': 'spend,impressions,reach,clicks,ctr,cpc,cpm,actions,action_values,cost_per_action_type,purchase_roas,website_purchase_roas',
        'date_preset': date_preset,
        'access_token': access_token,
        'limit': '50',
    }
    url = f"https://graph.facebook.com/{cfg['graph_api_version']}/{campaign_id}/insights?{urllib.parse.urlencode(params)}"
    return graph_get(url)


def _campaign_result_summary_from_insights(row: dict) -> dict:
    actions = row.get('actions') or []
    action_map = {}
    for item in actions:
        t = item.get('action_type')
        if t:
            action_map[t] = item.get('value')

    def _f(v):
        try:
            return float(str(v).replace(',', ''))
        except Exception:
            return 0.0

    leads = 0.0
    for k in ['lead', 'onsite_conversion.lead_grouped', 'offsite_complete_registration_add_meta_leads', 'offsite_search_add_meta_leads', 'offsite_content_view_add_meta_leads']:
        leads += _f(action_map.get(k))
    messages = 0.0
    for k in ['onsite_conversion.total_messaging_connection', 'onsite_conversion.messaging_conversation_started_7d', 'onsite_conversion.messaging_first_reply']:
        messages += _f(action_map.get(k))
    purchases = 0.0
    for k in ['purchase', 'omni_purchase', 'offsite_conversion.fb_pixel_purchase', 'web_in_store_purchase', 'onsite_web_purchase', 'onsite_web_app_purchase', 'web_app_in_store_purchase']:
        purchases += _f(action_map.get(k))
    return {
        'leads': leads,
        'messages': messages,
        'purchases': purchases,
        'spend': _f(row.get('spend')),
        'impressions': _f(row.get('impressions')),
        'clicks': _f(row.get('clicks')),
        'ctr': _f(row.get('ctr')),
        'cpc': _f(row.get('cpc')),
        'cpm': _f(row.get('cpm')),
        'actions': action_map,
    }

def fetch_ad_account_insights(cfg, ad_account_id: str, date_preset: str = 'last_30d'):
    access_token = get_meta_access_token()
    # Sem "level": em várias versões do Graph o parâmetro em /act_*/insights causa erro 400.
    params = {
        'fields': 'spend,impressions,reach,clicks,ctr,cpc,cpm,purchase_roas,website_purchase_roas,conversions,actions,action_values,cost_per_action_type',
        'breakdowns': 'age,gender',
        'date_preset': date_preset,
        'access_token': access_token,
        'limit': '200',
    }
    url = f"https://graph.facebook.com/{cfg['graph_api_version']}/{ad_account_id}/insights?{urllib.parse.urlencode(params)}"
    return graph_get(url)


def generate_ai_copy_and_prompt(description: str, art_direction: Optional[dict] = None, page_id: str = ''):
    description = (description or '').strip()
    if not description:
        raise ValueError('missing description')
    art_direction = art_direction or {}
    brand_colors = art_direction.get('colors') or []
    if isinstance(brand_colors, str):
        brand_colors = [c.strip() for c in brand_colors.split(',') if c.strip()]
    elif not isinstance(brand_colors, list):
        brand_colors = []
    visual_context = []
    if brand_colors:
        visual_context.append(f"Cores da marca: {', '.join(str(c).strip() for c in brand_colors[:8] if str(c).strip())}")
    if art_direction.get('visual_style'):
        visual_context.append(f"Estilo visual: {art_direction.get('visual_style')}")
    if art_direction.get('font_preference'):
        visual_context.append(f"Tipografia desejada: {art_direction.get('font_preference')}")
    if art_direction.get('reference_image_url'):
        visual_context.append(f"Referência visual: {art_direction.get('reference_image_url')}")
    if art_direction.get('use_reference_style') and art_direction.get('reference_style_prompt'):
        visual_context.append(f"Síntese visual prioritária das referências: {art_direction.get('reference_style_prompt')}")
    if isinstance(art_direction.get('references'), list) and art_direction.get('references'):
        visual_context.append(f"URLs de referências visuais: {' | '.join(str(u) for u in art_direction.get('references')[:6] if str(u).strip())}")
    image_prompt_template = """Crie uma arte para Instagram no formato 1:1 (1080x1080), com estilo moderno, tecnológico e minimalista, adaptado para o nicho: "{NICHO}".

🎯 OBJETIVO DA ARTE:
Transmitir "{OBJETIVO_DA_MENSAGEM}" com estética premium e alta percepção de valor.

---

🎨 ELEMENTOS VISUAIS:

- Fundo:
  Gradiente escuro com cores principais: "{CORES_PRINCIPAIS}"
  Iluminação suave, aparência premium, com profundidade

- Ambiente/Cenário (se aplicável):
  "{CENARIO_REALISTA}"
  (ex: escritório moderno, casa de luxo, praia, hospital, ambiente digital, etc.)

- Personagem (opcional):
  "{DESCRICAO_PERSONAGEM}"
  (ex: executivo, jovem usando app, mulher elegante, família, etc.)

- Elementos 3D:
  Objetos abstratos ou simbólicos relacionados ao nicho "{NICHO}"
  Estilo: vidro/acrílico translúcido + glow nas cores da marca
  (ex: gráficos → fintech, casa → imobiliário, avião → travel, cérebro → IA)

- Tipografia:
  Moderna, sans-serif, alto contraste, legível

---

📝 CONTEÚDO:

- Título: "{TITULO}"
- Subtítulo: "{SUBTITULO}"

- Canto inferior reservado para logo:
  Deixar área completamente limpa no canto inferior ESQUERDO, sem nenhum elemento visual, texto ou decoração.
  NÃO gerar, recriar, desenhar ou sugerir nenhuma logo, símbolo de marca ou logotipo em nenhum canto.
  A logo real será colada como overlay externo após a geração da imagem.

---

📐 DIREÇÃO DE DESIGN:

- Estilo visual: "{ESTILO_VISUAL}"
  (ex: corporativo, lifestyle, futurista, institucional, jovem, luxo)

- Combinação de:
  "{TIPO_DE_RENDER}"
  (ex: realismo + elementos 3D, UI digital + mockups, foto + overlay gráfico)

- Iluminação:
  "{TIPO_ILUMINACAO}"
  (ex: volumétrica, neon, sunset, studio light)

- Emoção transmitida:
  "{EMOCAO}"
  (ex: confiança, liberdade, urgência, inovação, exclusividade)

---

📊 HIERARQUIA:

- Subtítulo pequeno acima
- Título grande e dominante
- Destacar palavra-chave: "{PALAVRA_CHAVE_DESTACADA}"
  usando cor de destaque "{COR_DESTAQUE}"

---

🎯 ESTILO FINAL:

- Ultra realistic (quando aplicável)
- High-end marketing design
- 3D glass morphism
- Soft glow lighting
- Clean layout
- UI/UX inspired

---

🚫 RESTRIÇÕES:

- Sem poluição visual
- Sem excesso de elementos
- Sem distorção de texto
- Sem logos, marcas, logotipos ou símbolos de empresa desenhados na imagem
- Evitar elementos genéricos ou clichês

---

⚙️ PARÂMETROS:

--ar 1:1 --v 6 --style raw

(opcional)
--no logo, brand mark, watermark, bad typography, cluttered design"""
    custom_tpl = get_image_template(page_id)
    if custom_tpl:
        image_prompt_template = custom_tpl
    color_priority_rule = (
        f'Paleta prioritária da marca: {", ".join(str(c).strip() for c in brand_colors[:8] if str(c).strip())}. '
        'Essas cores devem dominar a peça. Não invente uma nova paleta principal. '
        'Só use neutros de apoio como preto, branco, cinza, grafite ou bege se precisar de contraste. '
        'Evite cores fora da paleta principal da marca.'
        if brand_colors else
        'Se a paleta da marca não estiver definida, escolha uma paleta coerente com o nicho e o posicionamento.'
    )

    image_focus = (art_direction.get('image_focus') or '').strip()
    copy_prompt = (
        'Você é um redator especialista em Instagram com olhar estratégico e voz autêntica. '
        'Escreva uma legenda REAL, pronta para publicar — nunca genérica, nunca com cara de IA. '
        'A legenda deve estar em português do Brasil. '
        '\n\n'
        'ESTRUTURA DA LEGENDA:\n'
        '1. Abertura com gancho: primeira linha forte que prende o scroll (pode ser pergunta, dado, afirmação ousada ou situação que o leitor se identifica).\n'
        '2. Desenvolvimento: 2-3 parágrafos curtos com quebra de linha entre cada um. Conteúdo útil, emocional ou que gera desejo.\n'
        '3. CTA natural: encerre com chamada para ação real — não genérica como "entre em contato", mas algo específico ao contexto (ex: "salva esse post", "manda pra quem precisa ver", "link na bio pra garantir").\n'
        '4. Hashtags: 5 a 10 hashtags específicas ao nicho, misturando populares e nichadas. Coloque em linha separada após o CTA.\n'
        '\n'
        'EMOJIS: Use emojis estrategicamente — 1 a 2 por parágrafo, integrados ao texto ou no início de linha para ritmo visual. '
        'Prefira emojis que reforçam a mensagem (não apenas decoração). Exemplos: 🏠 para imóveis, 🚀 para crescimento, ✅ para benefícios, 💡 para dicas.\n'
        '\n'
        'TOM: Natural, humano, com ritmo de Instagram real. '
        'NÃO use: travessão longo, listas artificiais, frases simétricas demais, estruturas engessadas de IA, "transforme sua vida", "clique aqui".\n'
        '\n'
        'TAMANHO: 600 a 1000 caracteres (sem contar hashtags), salvo se o briefing pedir algo mais curto.\n'
        '\n'
        'OUTPUT: SOMENTE JSON válido com as chaves "copy" (legenda completa com emojis, quebras de linha \\n e hashtags), '
        '"title" (título curto e forte para a arte, max 6 palavras) e '
        '"subtitle" (complemento do título, max 8 palavras). Sem markdown, sem explicações.\n'
        f'\nBriefing: {description}'
        + (f'\nBriefing adicional (prioridade máxima — inclua na legenda): {image_focus}.' if image_focus else '')
        + (f'\nContexto visual: {" | ".join(visual_context)}' if visual_context else '')
    )
    try:
        copy_result = _ai_generate_text('copy_generation', copy_prompt, 90, json_mode=True, system=get_agent_system_note('copy_generation', page_id))
        parsed = _extract_json_block(copy_result.get('text') or '')
        copy = normalize_caption_text(_coerce_text(parsed.get('copy')))
        title = _coerce_text(parsed.get('title'))
        subtitle = _coerce_text(parsed.get('subtitle'))
        # Step 2: AI generates the variable VALUES that fill the template
        vars_prompt = (
            'Você é um diretor de arte especialista em marketing digital para Instagram. '
            'Com base nos dados da marca abaixo, gere SOMENTE JSON válido com os valores '
            'para preencher um template de prompt de imagem. '
            'Retorne um JSON com exatamente estas chaves: '
            '"NICHO", "OBJETIVO_DA_MENSAGEM", "CORES_PRINCIPAIS", "CENARIO_REALISTA", '
            '"DESCRICAO_PERSONAGEM", "ESTILO_VISUAL", "TIPO_DE_RENDER", '
            '"TIPO_ILUMINACAO", "EMOCAO", "PALAVRA_CHAVE_DESTACADA", "COR_DESTAQUE". '
            'Cada valor deve ser uma string descritiva, específica à marca e ao conteúdo do post. '
            'Nao use emojis nos valores. Sem markdown, sem explicações. Apenas o JSON. '
            f'{color_priority_rule} '
            f'Dados da marca: '
            f'nicho={art_direction.get("niche", "negócio da marca")}; '
            f'ICP e público ideal={art_direction.get("icp_context", "")}; '
            f'cores da marca={", ".join(brand_colors[:6]) if brand_colors else art_direction.get("main_colors", "tons da marca")}; '
            f'estilo visual={art_direction.get("visual_style", "moderno, premium")}; '
            f'objetivo da mensagem={art_direction.get("message_objective", title or description[:160])}; '
            f'emoção desejada={art_direction.get("emotion", "confiança e percepção de valor")}; '
            f'cenário realista={art_direction.get("realistic_scenario", "coerente com o negócio")}; '
            f'descrição de personagem={art_direction.get("character_description", "sem personagem obrigatório")}; '
            f'tipo de render={art_direction.get("render_type", "realismo + elementos 3D sutis")}; '
            f'tipo de iluminação={art_direction.get("lighting_type", "soft glow lighting")}; '
            f'palavra-chave de destaque={art_direction.get("highlight_keyword", "")}; '
            f'cor de destaque={art_direction.get("highlight_color", brand_colors[0] if brand_colors else "#F06B02")}. '
            f'Briefing do post: {description} '
            + (f'Direção criativa da imagem (pedido do usuário — prioridade máxima): {art_direction.get("image_focus")}. ' if art_direction.get('image_focus') else '')
            + (f'Padrão visual das referências da marca (prioridade alta): {art_direction.get("reference_style_prompt")}. ' if art_direction.get('use_reference_style') and art_direction.get('reference_style_prompt') else '')
            + (f'Contexto visual adicional: {" | ".join(visual_context)}' if visual_context else '')
        )
        prompt_result = _ai_generate_text('prompt_generation', vars_prompt, 70, json_mode=True, system=get_agent_system_note('prompt_generation', page_id))
        vars_parsed = _extract_json_block(prompt_result.get('text') or '')

        # Step 3: substitute variables into the fixed template (Python does the assembly)
        template_vars = {
            'NICHO': vars_parsed.get('NICHO') or art_direction.get('niche', 'negócio da marca'),
            'OBJETIVO_DA_MENSAGEM': vars_parsed.get('OBJETIVO_DA_MENSAGEM') or art_direction.get('message_objective', title or description[:160]),
            'CORES_PRINCIPAIS': vars_parsed.get('CORES_PRINCIPAIS') or (', '.join(brand_colors[:6]) if brand_colors else 'tons da marca'),
            'CENARIO_REALISTA': vars_parsed.get('CENARIO_REALISTA') or art_direction.get('realistic_scenario', 'cenário coerente com o negócio'),
            'DESCRICAO_PERSONAGEM': vars_parsed.get('DESCRICAO_PERSONAGEM') or art_direction.get('character_description', 'sem personagem obrigatório'),
            'TITULO': title or 'Título principal',
            'SUBTITULO': subtitle or 'Subtítulo complementar',
            'ESTILO_VISUAL': vars_parsed.get('ESTILO_VISUAL') or art_direction.get('visual_style', 'moderno, premium e alinhado à marca'),
            'TIPO_DE_RENDER': vars_parsed.get('TIPO_DE_RENDER') or art_direction.get('render_type', 'realismo + elementos 3D sutis'),
            'TIPO_ILUMINACAO': vars_parsed.get('TIPO_ILUMINACAO') or art_direction.get('lighting_type', 'soft glow lighting'),
            'EMOCAO': vars_parsed.get('EMOCAO') or art_direction.get('emotion', 'confiança e percepção de valor'),
            'PALAVRA_CHAVE_DESTACADA': vars_parsed.get('PALAVRA_CHAVE_DESTACADA') or art_direction.get('highlight_keyword', title.split()[0] if title else ''),
            'COR_DESTAQUE': vars_parsed.get('COR_DESTAQUE') or art_direction.get('highlight_color', brand_colors[0] if brand_colors else '#F06B02'),
        }
        image_prompt = image_prompt_template
        for k, v in template_vars.items():
            image_prompt = image_prompt.replace('{' + k + '}', str(v).strip())
        image_prompt = image_prompt.strip()

        if copy and title and image_prompt:
            merged_usage = _merge_usage(copy_result.get('usage', {}), prompt_result.get('usage', {}))
            return {
                'copy': copy,
                'title': title,
                'subtitle': subtitle,
                'image_prompt': image_prompt,
                'provider': copy_result.get('provider', ''),
                'model': copy_result.get('model', ''),
                'prompt_provider': prompt_result.get('provider', ''),
                'prompt_model': prompt_result.get('model', ''),
                'copy_usage': copy_result.get('usage', {}),
                'copy_cost_usd': float(copy_result.get('cost_usd', 0.0) or 0.0),
                'prompt_usage': prompt_result.get('usage', {}),
                'prompt_cost_usd': float(prompt_result.get('cost_usd', 0.0) or 0.0),
                'usage': merged_usage,
                'cost_usd': float(copy_result.get('cost_usd', 0.0) or 0.0) + float(prompt_result.get('cost_usd', 0.0) or 0.0),
            }
    except Exception:
        pass

    # Fallback: compose a real caption from the briefing text
    sentences = [s.strip() for s in description.replace('\n', '.').split('.') if len(s.strip()) > 8]
    body = sentences[0] if sentences else description
    title = (body[:52] or 'Sua marca em destaque').strip()
    subtitle = 'Solução relevante para o seu público'
    fallback_vars = {
        'NICHO': art_direction.get('niche', 'negócio da marca'),
        'OBJETIVO_DA_MENSAGEM': title,
        'CORES_PRINCIPAIS': ', '.join(brand_colors[:6]) if brand_colors else 'tons da marca',
        'CENARIO_REALISTA': art_direction.get('realistic_scenario', 'cenário coerente com o negócio'),
        'DESCRICAO_PERSONAGEM': art_direction.get('character_description', 'sem personagem obrigatório'),
        'TITULO': title,
        'SUBTITULO': subtitle,
        'ESTILO_VISUAL': art_direction.get('visual_style', 'moderno, premium e alinhado à marca'),
        'TIPO_DE_RENDER': art_direction.get('render_type', 'realismo + elementos 3D sutis'),
        'TIPO_ILUMINACAO': art_direction.get('lighting_type', 'soft glow lighting'),
        'EMOCAO': art_direction.get('emotion', 'confiança e percepção de valor'),
        'PALAVRA_CHAVE_DESTACADA': title.split()[0] if title else '',
        'COR_DESTAQUE': art_direction.get('highlight_color', brand_colors[0] if brand_colors else '#F06B02'),
    }
    image_prompt = image_prompt_template
    for k, v in fallback_vars.items():
        image_prompt = image_prompt.replace('{' + k + '}', str(v).strip())
    image_prompt = image_prompt.strip()
    copy = (
        f'{body}.\n\n'
        'Essa é a proposta que está transformando a forma de quem já usa. '
        'Quer saber mais? Deixa seu comentário ou fala com a gente pelo direct.\n\n'
        '#marketing #inovacao #oportunidade #negociosdigitais'
    )
    return {'copy': copy, 'title': title, 'subtitle': subtitle, 'image_prompt': image_prompt, 'provider': 'fallback', 'model': 'fallback', 'usage': {}, 'cost_usd': 0.0}


def generate_image_local(image_prompt: str, post_id: str = '', prefix: str = 'igpost'):
    import random
    import string
    safe_post_id = ''.join(ch for ch in str(post_id or '') if ch.isalnum()).lower()[:24]
    if not safe_post_id:
        safe_post_id = ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(10))
    file_name = f"{prefix}_{safe_post_id}.png"
    out_path = f"/root/.openclaw/workspace/outputs/nano-banana/{file_name}"
    cmd = [
        'python3',
        '/root/.openclaw/workspace/skills/nano-banana-gen/scripts/generate_nano_banana.py',
        image_prompt,
        '--out',
        out_path,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(res.stdout.strip())
    data['requested_output'] = out_path
    data['post_id'] = safe_post_id
    return data


def _save_b64_image_to_generated(image_b64: str, file_name: str) -> str:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    dest = GENERATED_DIR / file_name
    dest.write_bytes(base64.b64decode(image_b64))
    return str(dest)


def _call_openai_image_with_refs(prompt: str, model: str, api_key: str, ref_image_paths: list, size: str = '1024x1024', quality: str = 'auto', timeout: int = 180) -> dict:
    """Call gpt-image-1 edit endpoint passing reference images as visual inspiration."""
    from io import BytesIO
    import uuid as _uuid

    def _to_png_bytes(path: str) -> bytes:
        with Image.open(path) as im:
            buf = BytesIO()
            im.convert('RGBA').save(buf, format='PNG')
            return buf.getvalue()

    full_prompt = (
        'Using the provided reference images as visual inspiration for the actual environment, '
        'product, or space shown, ' + prompt
    )
    boundary = _uuid.uuid4().hex
    b = boundary.encode('ascii')
    body = b''

    def _add_field(name: str, value: str):
        nonlocal body
        body += b'--' + b + b'\r\n'
        body += f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode('utf-8')
        body += value.encode('utf-8')
        body += b'\r\n'

    def _add_file(name: str, filename: str, data: bytes):
        nonlocal body
        body += b'--' + b + b'\r\n'
        body += f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode('utf-8')
        body += b'Content-Type: image/png\r\n\r\n'
        body += data
        body += b'\r\n'

    _add_field('model', model)
    _add_field('prompt', full_prompt[:32000])
    _add_field('size', size)
    _add_field('quality', quality or 'auto')
    for i, ref_path in enumerate(ref_image_paths[:4]):
        try:
            _add_file('image[]', f'ref{i}.png', _to_png_bytes(ref_path))
        except Exception:
            continue
    body += b'--' + b + b'--\r\n'

    last_err = None
    for attempt in range(3):
        req = urllib.request.Request(
            f'{_openai_base_url()}/images/edits',
            data=body,
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': f'multipart/form-data; boundary={boundary}',
            },
            method='POST',
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            last_err = e
            try:
                body_err = e.read().decode('utf-8', errors='replace')
            except Exception:
                body_err = str(e)
            if e.code in (429, 500, 502, 503, 504) and attempt < 2:
                time.sleep(min(12.0, 1.5 * (2 ** attempt)))
                continue
            raise RuntimeError(body_err)
    if last_err:
        raise last_err
    raise RuntimeError('openai_image_with_refs_failed')


def generate_image_asset(cfg, image_prompt: str, post_id: str = '', prefix: str = 'igpost', operation: str = 'image_generation', ref_image_paths: list = None) -> dict:
    route = _ai_route('image_generation')
    provider = route.get('provider', 'nano_banana')
    model = route.get('model', '')
    if provider == 'openai':
        api_key = _openai_api_key()
        if not api_key:
            raise ValueError('openai_not_configured')
        selected_model = model if model in OPENAI_IMAGE_MODELS else 'dall-e-3'
        fitted_prompt, prompt_truncated, prompt_limit = _fit_openai_image_prompt(image_prompt, selected_model)
        image_cfg = ((cfg.get('ai_settings') or {}).get('image_generation') or {}) if isinstance((cfg.get('ai_settings') or {}).get('image_generation'), dict) else {}
        size = str(image_cfg.get('size') or '1024x1024')
        quality = _normalize_openai_image_quality(selected_model, str(image_cfg.get('quality') or 'standard'))
        background = str(image_cfg.get('background') or 'auto')
        output_format = str(image_cfg.get('output_format') or 'png')
        moderation = str(image_cfg.get('moderation') or 'auto')
        import random
        import string
        safe_post_id = ''.join(ch for ch in str(post_id or '') if ch.isalnum()).lower()[:24]
        if not safe_post_id:
            safe_post_id = ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(10))
        file_name = f"{prefix}_{safe_post_id}.png"
        valid_refs = [p for p in (ref_image_paths or []) if p and Path(p).exists()]
        if valid_refs and selected_model.startswith('gpt-image-'):
            image_data = _call_openai_image_with_refs(fitted_prompt, selected_model, api_key, valid_refs, size=size, quality=quality)
        else:
            image_data = _call_openai_image(fitted_prompt, selected_model, api_key, size=size, quality=quality, background=background, output_format=output_format, moderation=moderation)
        items = image_data.get('data') or []
        if not items or not (items[0].get('b64_json') or '').strip():
            raise ValueError('empty_openai_image_response')
        local_path = _save_b64_image_to_generated(items[0]['b64_json'], file_name)
        public_url = build_public_media_url(cfg, local_path, post_id=safe_post_id, prefix=prefix)
        usage = _extract_usage_from_openai_response(image_data) if image_data.get('usage') else {'input_tokens': 0, 'output_tokens': 0, 'total_tokens': 0}
        cost = _calculate_ai_cost('openai', selected_model, usage, image_count=0 if usage.get('total_tokens') else 1)
        return {
            'provider': 'openai',
            'model': selected_model,
            'post_id': safe_post_id,
            'requested_output': local_path,
            'images': [{'path': local_path}],
            'public_url': public_url,
            'usage': usage,
            'cost_usd': cost,
            'size': size,
            'quality': quality,
            'background': background,
            'output_format': output_format,
            'moderation': moderation,
            'prompt_truncated': prompt_truncated,
            'prompt_limit': prompt_limit,
            'prompt_length_original': len(str(image_prompt or '')),
            'prompt_length_sent': len(fitted_prompt),
        }
    image = generate_image_local(image_prompt, post_id=post_id, prefix=prefix)
    local_path = image.get('requested_output') or image.get('path') or ''
    public_url = build_public_media_url(cfg, local_path, post_id=image.get('post_id', post_id), prefix=prefix) if local_path else ''
    return {
        **image,
        'provider': 'nano_banana',
        'model': 'nano_banana',
        'public_url': public_url,
        'usage': {},
        'cost_usd': 0.0,
    }


def ensure_local_jpeg(local_path: str):
    src = Path(local_path)
    if not src.exists():
        return ''
    dest = src.with_suffix('.jpg')
    try:
        with Image.open(src) as im:
            if im.mode in ('RGBA', 'LA', 'P'):
                im = im.convert('RGB')
            elif im.mode != 'RGB':
                im = im.convert('RGB')
            im.save(dest, format='JPEG', quality=95)
        return str(dest)
    except Exception:
        return str(src)


def publish_generated_file(cfg, local_path: str):
    src = Path(local_path)
    if not src.exists():
        return ''

    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    base_name = src.stem
    dest = GENERATED_DIR / f"{base_name}.jpg"

    try:
        with Image.open(src) as im:
            if im.mode in ('RGBA', 'LA', 'P'):
                im = im.convert('RGB')
            elif im.mode != 'RGB':
                im = im.convert('RGB')
            im.save(dest, format='JPEG', quality=95)
    except Exception:
        shutil.copy2(src, dest)

    freeimage_url = _upload_to_freeimage(str(dest))
    if freeimage_url:
        return freeimage_url
    cloudinary_url = _upload_to_cloudinary(str(dest), public_id=dest.stem)
    if cloudinary_url:
        return cloudinary_url
    return cfg['public_base_url'].rstrip('/') + f'/media/generated/{dest.name}'



def sanitize_public_media_name(name: str, fallback: str = 'igpost'):
    raw = (name or '').strip().lower()
    cleaned = ''.join(ch for ch in raw if ch.isalnum())
    cleaned = cleaned[:40] or fallback
    return cleaned


def normalize_caption_text(text: str):
    text = (text or '').replace('\r\n', '\n').replace('\r', '\n').strip()
    text = text.replace('—', '; ').replace('–', '; ')
    while '\n\n\n' in text:
        text = text.replace('\n\n\n', '\n\n')
    return text


def build_public_media_url(cfg, local_path: str, post_id: str = '', prefix: str = 'igpost'):
    src = Path(local_path)
    if not src.exists():
        return ''
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    token = sanitize_public_media_name(post_id, fallback=f'{prefix}asset')
    dest = GENERATED_DIR / f"{prefix}{token}.jpg"
    try:
        with Image.open(src) as im:
            if im.mode in ('RGBA', 'LA', 'P'):
                im = im.convert('RGB')
            elif im.mode != 'RGB':
                im = im.convert('RGB')
            im.save(dest, format='JPEG', quality=95)
    except Exception:
        shutil.copy2(src, dest)
    freeimage_url = _upload_to_freeimage(str(dest))
    if freeimage_url:
        return freeimage_url
    cloudinary_url = _upload_to_cloudinary(str(dest), public_id=dest.stem)
    if cloudinary_url:
        return cloudinary_url
    return cfg['public_base_url'].rstrip('/') + f'/media/generated/{dest.name}'


def _ensure_ig_accessible_url(image_url: str, cfg: dict) -> str:
    """If image_url is hosted on our own server, re-upload to freeimage/cloudinary so
    Instagram can fetch it (our domain may be blocked by Meta's crawlers).
    Returns the best public URL available."""
    if not image_url:
        return image_url
    own_base = cfg.get('public_base_url', '').rstrip('/')
    if own_base and image_url.startswith(own_base):
        filename = image_url.split('/')[-1]
        local = GENERATED_DIR / filename
        if local.exists():
            fi = _upload_to_freeimage(str(local))
            if fi:
                return fi
            cl = _upload_to_cloudinary(str(local), public_id=local.stem)
            if cl:
                return cl
        else:
            try:
                import tempfile, os
                req = urllib.request.Request(image_url)
                req.add_header('User-Agent', 'Mozilla/5.0')
                with urllib.request.urlopen(req, timeout=30) as resp:
                    suffix = '.jpg'
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                        tmp.write(resp.read())
                        tmp_path = tmp.name
                fi = _upload_to_freeimage(tmp_path)
                os.unlink(tmp_path)
                if fi:
                    return fi
            except Exception:
                pass
    return image_url


def _upload_to_freeimage(local_path: str) -> str:
    api_key = (get_secret(FREEIMAGE_API_KEY_NAME) or '').strip()
    if not api_key:
        return ''
    path = Path(local_path)
    if not path.exists():
        return ''
    boundary = '----MetaPanelFreeimageBoundary' + hashlib.md5(f'{time.time()}-{path.name}'.encode('utf-8')).hexdigest()
    body = bytearray()
    def add_field(name: str, value: str):
        body.extend(f'--{boundary}\r\n'.encode('utf-8'))
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode('utf-8'))
        body.extend(str(value).encode('utf-8'))
        body.extend(b'\r\n')
    add_field('key', api_key)
    add_field('action', 'upload')
    add_field('format', 'json')
    mime = mimetypes.guess_type(str(path))[0] or 'image/jpeg'
    body.extend(f'--{boundary}\r\n'.encode('utf-8'))
    body.extend(f'Content-Disposition: form-data; name="source"; filename="{path.name}"\r\n'.encode('utf-8'))
    body.extend(f'Content-Type: {mime}\r\n\r\n'.encode('utf-8'))
    body.extend(path.read_bytes())
    body.extend(b'\r\n')
    body.extend(f'--{boundary}--\r\n'.encode('utf-8'))
    req = urllib.request.Request(
        'https://freeimage.host/api/1/upload',
        data=bytes(body),
        headers={'Content-Type': f'multipart/form-data; boundary={boundary}'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        return str(((data.get('image') or {}).get('url')) or '')
    except Exception as e:
        append_system_error_log('freeimage_upload_failed', 'Freeimage upload failed', detail=str(e), local_path=str(path))
        return ''


def _upload_to_cloudinary(local_path: str, public_id: str = '') -> str:
    cloud_name = (get_secret(CLOUDINARY_CLOUD_NAME) or '').strip()
    api_key = (get_secret(CLOUDINARY_API_KEY_NAME) or '').strip()
    api_secret = (get_secret(CLOUDINARY_API_SECRET_NAME) or '').strip()
    if not (cloud_name and api_key and api_secret):
        return ''
    path = Path(local_path)
    if not path.exists():
        return ''
    timestamp = str(int(time.time()))
    params = {'timestamp': timestamp}
    if public_id:
        params['public_id'] = public_id
        params['overwrite'] = 'true'
    signature_base = '&'.join(f'{k}={params[k]}' for k in sorted(params)) + api_secret
    signature = hashlib.sha1(signature_base.encode('utf-8')).hexdigest()
    boundary = '----MetaPanelCloudinaryBoundary' + hashlib.md5(f'{time.time()}-{path.name}'.encode('utf-8')).hexdigest()
    body = bytearray()
    def add_field(name: str, value: str):
        body.extend(f'--{boundary}\r\n'.encode('utf-8'))
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode('utf-8'))
        body.extend(str(value).encode('utf-8'))
        body.extend(b'\r\n')
    add_field('api_key', api_key)
    add_field('timestamp', timestamp)
    add_field('signature', signature)
    if public_id:
        add_field('public_id', public_id)
        add_field('overwrite', 'true')
    mime = mimetypes.guess_type(str(path))[0] or 'image/jpeg'
    body.extend(f'--{boundary}\r\n'.encode('utf-8'))
    body.extend(f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'.encode('utf-8'))
    body.extend(f'Content-Type: {mime}\r\n\r\n'.encode('utf-8'))
    body.extend(path.read_bytes())
    body.extend(b'\r\n')
    body.extend(f'--{boundary}--\r\n'.encode('utf-8'))
    req = urllib.request.Request(
        f'https://api.cloudinary.com/v1_1/{cloud_name}/image/upload',
        data=bytes(body),
        headers={'Content-Type': f'multipart/form-data; boundary={boundary}'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        return str(data.get('secure_url') or data.get('url') or '')
    except Exception as e:
        append_system_error_log('cloudinary_upload_failed', 'Cloudinary upload failed', detail=str(e), local_path=str(path), public_id=public_id)
        return ''


def _probe_public_image_url(url: str, timeout: int = 20) -> dict:
    final_url = url
    content_type = ''
    content_length = 0
    status = 0
    try:
        req = urllib.request.Request(url, method='HEAD', headers={'User-Agent': 'meta-connection-panel/1.0'})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            final_url = resp.geturl()
            status = getattr(resp, 'status', 200) or 200
            content_type = str(resp.headers.get('Content-Type', '') or '').split(';')[0].strip().lower()
            try:
                content_length = int(resp.headers.get('Content-Length') or 0)
            except Exception:
                content_length = 0
    except Exception:
        pass
    if not content_type.startswith('image/'):
        req = urllib.request.Request(url, method='GET', headers={'User-Agent': 'meta-connection-panel/1.0'})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            final_url = resp.geturl()
            status = getattr(resp, 'status', 200) or 200
            content_type = str(resp.headers.get('Content-Type', '') or '').split(';')[0].strip().lower()
            sample = resp.read(64)
            if not content_length:
                try:
                    content_length = int(resp.headers.get('Content-Length') or 0)
                except Exception:
                    content_length = len(sample or b'')
            return {
                'ok': content_type.startswith('image/'),
                'status': status,
                'final_url': final_url,
                'content_type': content_type,
                'content_length': content_length,
                'sample_hex': (sample or b'').hex()[:64],
            }
    return {
        'ok': content_type.startswith('image/'),
        'status': status,
        'final_url': final_url,
        'content_type': content_type,
        'content_length': content_length,
    }


def _is_light_logo(logo_path: str) -> bool:
    try:
        with Image.open(logo_path) as im:
            rgba = im.convert('RGBA')
            pixels = list(rgba.getdata())
        visible = [(r, g, b) for (r, g, b, a) in pixels if a > 32]
        if not visible:
            return False
        avg = sum((r + g + b) / 3.0 for (r, g, b) in visible) / len(visible)
        return avg >= 160
    except Exception:
        return False


def _average_region_luma(im_rgba, box: tuple[int, int, int, int]) -> float:
    x1, y1, x2, y2 = box
    x1 = max(0, min(im_rgba.size[0], x1))
    y1 = max(0, min(im_rgba.size[1], y1))
    x2 = max(x1 + 1, min(im_rgba.size[0], x2))
    y2 = max(y1 + 1, min(im_rgba.size[1], y2))
    crop = im_rgba.crop((x1, y1, x2, y2)).convert('RGBA')
    pixels = list(crop.getdata())
    if not pixels:
        return 127.0
    visible = [(r, g, b) for (r, g, b, a) in pixels if a > 8]
    if not visible:
        return 127.0
    return sum((0.299 * r) + (0.587 * g) + (0.114 * b) for (r, g, b) in visible) / len(visible)


def _needs_logo_backdrop(base_rgba, logo_is_light: bool, box: tuple[int, int, int, int]) -> bool:
    luma = _average_region_luma(base_rgba, box)
    if logo_is_light:
        return luma > 150
    return luma < 120


def _build_corner_gradient(size: tuple[int, int], position: str, light_logo: bool):
    width, height = size
    from PIL import ImageDraw, ImageFilter
    overlay = Image.new('RGBA', size, (0, 0, 0, 0))
    grad = Image.new('L', size, 0)
    draw = ImageDraw.Draw(grad)
    max_radius = int(min(width, height) * 0.55)
    center = (0, height) if position != 'bottom_right' else (width, height)
    for radius in range(max_radius, 0, -12):
        alpha = int(155 * (radius / max_radius) ** 1.7)
        bbox = [center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius]
        draw.ellipse(bbox, fill=alpha)
    grad = grad.filter(ImageFilter.GaussianBlur(radius=max(24, int(min(width, height) * 0.03))))
    tint = (0, 0, 0, 255) if light_logo else (255, 255, 255, 255)
    overlay.paste(tint, (0, 0, width, height), grad)
    return overlay


def _apply_logo_overlay(base_image_path: str, logo_dark_path: str, logo_light_path: str = '', position: str = 'bottom_left') -> str:
    """
    Apply logo overlay using PIL.
    logo_dark_path  = version for light backgrounds (e.g. black logo)
    logo_light_path = version for dark backgrounds  (e.g. white logo)
    Automatically picks the right version based on background brightness.
    """
    src = Path(base_image_path)
    if not src.exists():
        return str(src)

    dark_src = Path(logo_dark_path) if logo_dark_path else None
    light_src = Path(logo_light_path) if logo_light_path else None

    if not (dark_src and dark_src.exists()) and not (light_src and light_src.exists()):
        return str(src)

    try:
        with Image.open(src) as base_im:
            base = base_im.convert('RGBA')

        bw, bh = base.size
        margin = max(18, int(min(bw, bh) * 0.035))

        # Need logo size to measure the right region — use whichever is available
        probe_path = dark_src if (dark_src and dark_src.exists()) else light_src
        with Image.open(probe_path) as probe_im:
            probe = probe_im.convert('RGBA')
        max_logo_w = int(bw * 0.22)
        max_logo_h = int(bh * 0.12)
        probe.thumbnail((max_logo_w, max_logo_h), Image.LANCZOS)
        lw, lh = probe.size

        x = margin if position != 'bottom_right' else bw - lw - margin
        y = bh - lh - margin
        pad_x = max(18, int(lw * 0.22))
        pad_y = max(14, int(lh * 0.30))
        focus_box = (
            max(0, x - pad_x), max(0, y - pad_y),
            min(bw, x + lw + pad_x), min(bh, y + lh + pad_y),
        )
        bg_luma = _average_region_luma(base, focus_box)

        # Choose logo version based on background brightness
        if bg_luma < 120 and light_src and light_src.exists():
            chosen_path = light_src   # dark bg → use light/white logo
        elif bg_luma >= 120 and dark_src and dark_src.exists():
            chosen_path = dark_src    # light bg → use dark/black logo
        else:
            chosen_path = (dark_src if (dark_src and dark_src.exists()) else light_src)

        with Image.open(chosen_path) as logo_im:
            logo = logo_im.convert('RGBA')
        logo.thumbnail((max_logo_w, max_logo_h), Image.LANCZOS)
        lw, lh = logo.size
        x = margin if position != 'bottom_right' else bw - lw - margin
        y = bh - lh - margin

        light_logo = _is_light_logo(str(chosen_path))
        pad_x = max(18, int(lw * 0.22))
        pad_y = max(14, int(lh * 0.30))
        focus_box = (
            max(0, x - pad_x), max(0, y - pad_y),
            min(bw, x + lw + pad_x), min(bh, y + lh + pad_y),
        )
        composed = base
        if _needs_logo_backdrop(base, light_logo, focus_box):
            overlay = _build_corner_gradient(base.size, position, light_logo)
            composed = Image.alpha_composite(base, overlay)
        composed.alpha_composite(logo, (x, y))
        final = composed.convert('RGB')
        out_path = src.with_name(f"{src.stem}_logo.jpg")
        final.save(out_path, format='JPEG', quality=95)
        return str(out_path)
    except Exception:
        return str(src)


def _apply_logo_overlay_gpt(base_image_path: str, logo_path: str, api_key: str, size: str = '1024x1024') -> str:
    """Use gpt-image-1 edit endpoint to composite logo into the base image with natural shading."""
    src = Path(base_image_path)
    logo_src = Path(logo_path)
    if not src.exists() or not logo_src.exists() or not api_key:
        return str(src)
    try:
        from io import BytesIO
        import uuid as _uuid

        def _to_png_bytes(path: Path) -> bytes:
            with Image.open(path) as im:
                buf = BytesIO()
                im.convert('RGBA').save(buf, format='PNG')
                return buf.getvalue()

        base_bytes = _to_png_bytes(src)
        logo_bytes = _to_png_bytes(logo_src)
        prompt = (
            'Place the logo (second image) in the bottom-left corner of the marketing artwork (first image). '
            'Add a subtle dark gradient or soft shadow behind the logo so it stands out clearly against the background. '
            'Keep all other elements of the artwork exactly as they are.'
        )
        boundary = _uuid.uuid4().hex
        b = boundary.encode('ascii')
        body = b''

        def _add_field(name: str, value: str):
            nonlocal body
            body += b'--' + b + b'\r\n'
            body += f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode('utf-8')
            body += value.encode('utf-8')
            body += b'\r\n'

        def _add_file(name: str, filename: str, data: bytes):
            nonlocal body
            body += b'--' + b + b'\r\n'
            body += f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode('utf-8')
            body += b'Content-Type: image/png\r\n\r\n'
            body += data
            body += b'\r\n'

        _add_field('model', 'gpt-image-1')
        _add_field('prompt', prompt)
        _add_field('size', size)
        _add_field('quality', 'auto')
        _add_file('image[]', 'base.png', base_bytes)
        _add_file('image[]', 'logo.png', logo_bytes)
        body += b'--' + b + b'--\r\n'

        req = urllib.request.Request(
            f'{_openai_base_url()}/images/edits',
            data=body,
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': f'multipart/form-data; boundary={boundary}',
            },
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=180) as resp:
            result = json.loads(resp.read().decode('utf-8'))

        items = result.get('data') or []
        if not items:
            return str(src)
        b64 = items[0].get('b64_json') or ''
        if not b64:
            return str(src)
        out_path = src.with_name(f'{src.stem}_logo.jpg')
        with Image.open(BytesIO(base64.b64decode(b64))) as im:
            im.convert('RGB').save(str(out_path), format='JPEG', quality=95)
        return str(out_path)
    except Exception:
        return str(src)


def _apply_logo_smart(base_image_path: str, logo_dark_path: str, logo_light_path: str = '') -> str:
    """Pick the right logo version for the background and apply via PIL."""
    return _apply_logo_overlay(base_image_path, logo_dark_path, logo_light_path, position='bottom_left')


def _describe_image_with_vision(image_path: str, api_key: str, timeout: int = 30) -> str:
    """Use GPT-4o-mini vision to generate a description of an uploaded image."""
    from io import BytesIO
    try:
        with Image.open(image_path) as im:
            buf = BytesIO()
            im.convert('RGB').save(buf, format='JPEG', quality=75)
            b64 = base64.b64encode(buf.getvalue()).decode('ascii')
    except Exception:
        return ''
    payload = {
        'model': 'gpt-4o-mini',
        'messages': [
            {
                'role': 'user',
                'content': [
                    {'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{b64}', 'detail': 'low'}},
                    {'type': 'text', 'text': (
                        'Descreva esta imagem em 1-2 frases em português do Brasil. '
                        'Foque nos elementos concretos visíveis: tipo de ambiente (sala, suíte, área de lazer, piscina, fachada, varanda, etc.), '
                        'quantidade de suítes/quartos se identificável, características do espaço, acabamentos, vista. '
                        'Seja objetivo e específico. Não use adjetivos vagos.'
                    )}
                ]
            }
        ],
        'max_tokens': 150,
    }
    body = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        f'{_openai_base_url()}/chat/completions',
        data=body,
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        return (((data.get('choices') or [{}])[0].get('message') or {}).get('content') or '').strip()
    except Exception:
        return ''


def _get_style_ref_paths(page_id: str, max_refs: int = 3) -> list:
    """
    Return local file paths for style reference images (designer refs + visual refs marked
    use_for_style). These are passed to gpt-image-1 so it maintains visual consistency.
    """
    paths = []
    profile = get_brand_profile(page_id) if page_id else {}

    # Visual references in brand profile marked for style
    for r in (profile.get('visual_references') or []):
        if not isinstance(r, dict) or not r.get('use_for_style'):
            continue
        p = str(r.get('path') or '')
        if p and Path(p).exists():
            paths.append(p)
        if len(paths) >= max_refs:
            return paths

    # Designer references from agents config (per-company first, then global)
    for ref in get_designer_references(page_id):
        if not isinstance(ref, dict):
            continue
        # Reconstruct path from filename stored in UPLOADS_DIR
        fname = ref.get('filename') or ''
        p = str(UPLOADS_DIR / fname) if fname else ''
        if p and Path(p).exists():
            paths.append(p)
        if len(paths) >= max_refs:
            return paths

    return paths


def _select_gallery_refs_for_briefing(gallery: list, briefing: str, max_refs: int = 4) -> list:
    """
    Select gallery photo paths relevant to the briefing via keyword matching.
    Returns empty list when there are no keyword matches — avoids forcing product
    photos into posts that don't need them.
    """
    valid = [r for r in gallery if isinstance(r, dict) and r.get('path') and Path(str(r['path'])).exists()]
    if not valid:
        return []
    briefing_words = {w.lower() for w in briefing.replace(',', ' ').split() if len(w) > 3}
    scored = []
    for r in valid:
        desc = ' '.join([str(r.get('description') or ''), str(r.get('original_name') or '')]).lower()
        score = sum(1 for w in briefing_words if w in desc)
        scored.append((score, r['path']))
    scored.sort(key=lambda x: -x[0])
    # Only include photos with at least one keyword match
    matched = [(s, p) for s, p in scored if s > 0]
    if not matched:
        return []
    return [path for _, path in matched[:max_refs]]


def fetch_page_insights(cfg, page_id: str, metrics: str, period: str = '', since: str = '', until: str = ''):
    token = get_page_access_token(page_id)
    params = {
        'metric': metrics,
        'access_token': token,
    }
    if period:
        params['period'] = period
    if since:
        params['since'] = since
    if until:
        params['until'] = until
    url = f"https://graph.facebook.com/{cfg['graph_api_version']}/{page_id}/insights?{urllib.parse.urlencode(params)}"
    return graph_get(url)


def list_instagram_accounts():
    session = load_json(META_SESSION_PATH, {})
    results = []
    for page in session.get('pages', []):
        ig = page.get('instagram_business_account') or {}
        if ig.get('id'):
            results.append({
                'page_id': page.get('id'),
                'page_name': page.get('name'),
                'page_access_token': page.get('access_token', ''),
                'instagram_business_account': ig,
            })
    return results


def get_instagram_account_by_username(username: str = '', ig_user_id: str = '', page_id: str = ''):
    username = (username or '').lstrip('@').strip().lower()
    for item in list_instagram_accounts():
        ig = item.get('instagram_business_account') or {}
        if ig_user_id and str(ig.get('id')) == str(ig_user_id):
            return item
        if page_id and str(item.get('page_id')) == str(page_id):
            return item
        if username and str(ig.get('username', '')).lower() == username:
            return item
    return None


def instagram_create_media(cfg, ig_user_id: str, access_token: str, image_url: str, caption: str, host: str = 'graph.facebook.com'):
    url = f"https://{host}/{cfg['graph_api_version']}/{ig_user_id}/media"
    params = urllib.parse.urlencode({
        'image_url': image_url,
        'caption': caption,
        'access_token': access_token,
    })
    req = urllib.request.Request(url, data=params.encode('utf-8'), method='POST')
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode('utf-8', errors='replace'))
        except Exception:
            return {'error': {'message': str(e)}}


def instagram_publish_media(cfg, ig_user_id: str, access_token: str, creation_id: str, host: str = 'graph.facebook.com'):
    url = f"https://{host}/{cfg['graph_api_version']}/{ig_user_id}/media_publish"
    params = urllib.parse.urlencode({
        'creation_id': creation_id,
        'access_token': access_token,
    })
    req = urllib.request.Request(url, data=params.encode('utf-8'), method='POST')
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode('utf-8', errors='replace'))
        except Exception:
            return {'error': {'message': str(e)}}


def get_instagram_direct_session():
    return load_json(INSTAGRAM_DIRECT_SESSION_PATH, {})


def get_instagram_direct_token():
    return (get_instagram_direct_session() or {}).get('access_token', '')


def get_instagram_direct_user_id():
    return str((get_instagram_direct_session() or {}).get('user_id', '') or '')


def instagram_account_insights(cfg, ig_user_id: str, access_token: str, metrics: str, period: str = '', since: str = '', until: str = '', host: str = 'graph.facebook.com'):
    params = {'metric': metrics, 'access_token': access_token}
    if period:
        params['period'] = period
    if since:
        params['since'] = since
    if until:
        params['until'] = until
    url = f"https://{host}/{cfg['graph_api_version']}/{ig_user_id}/insights?{urllib.parse.urlencode(params)}"
    return graph_get(url)


def instagram_media_insights(cfg, media_id: str, access_token: str, metrics: str, host: str = 'graph.facebook.com'):
    url = f"https://{host}/{cfg['graph_api_version']}/{media_id}/insights?{urllib.parse.urlencode({'metric': metrics, 'access_token': access_token})}"
    return graph_get(url)


def get_instagram_direct_config(cfg):
    app_id = get_secret(INSTAGRAM_APP_ID_NAME)
    app_secret = get_secret(INSTAGRAM_APP_SECRET_NAME)
    callback_url = cfg['public_base_url'].rstrip('/') + '/instagram/webhook'
    return {'app_id': app_id, 'app_secret': app_secret, 'callback_url': callback_url}


def instagram_direct_exchange_code(cfg, code: str):
    direct = get_instagram_direct_config(cfg)
    url = 'https://api.instagram.com/oauth/access_token'
    data = {
        'client_id': direct['app_id'],
        'client_secret': direct['app_secret'],
        'grant_type': 'authorization_code',
        'redirect_uri': direct['callback_url'],
        'code': code,
    }
    return graph_post(url, data)


def instagram_exchange_long_lived_token(cfg, short_lived_token: str):
    direct = get_instagram_direct_config(cfg)
    params = urllib.parse.urlencode({
        'grant_type': 'ig_exchange_from_short_lived_token',
        'client_secret': direct['app_secret'],
        'access_token': short_lived_token,
    })
    url = f"https://graph.instagram.com/access_token?{params}"
    return graph_get(url)


def load_instagram_web_accounts():
    data = load_json(INSTAGRAM_WEB_ACCOUNTS_PATH, {'accounts': []})
    if isinstance(data, dict) and 'accounts' in data and isinstance(data['accounts'], list):
        return data
    return {'accounts': []}


def save_instagram_web_accounts(data):
    save_json(INSTAGRAM_WEB_ACCOUNTS_PATH, data)


def upsert_instagram_web_account(account_key: str, username: str = '', note: str = ''):
    data = load_instagram_web_accounts()
    accounts = data['accounts']
    found = None
    for item in accounts:
        if item.get('account_key') == account_key:
            found = item
            break
    if not found:
        found = {'account_key': account_key}
        accounts.append(found)
    if username:
        found['username'] = username
    if note:
        found['note'] = note
    save_instagram_web_accounts(data)
    return found


def run_instagram_web_runner(args):
    cmd = ['node', '/root/.openclaw/workspace/projects/instagram-web-runner/runner.js'] + args
    res = subprocess.run(cmd, capture_output=True, text=True)
    stdout = (res.stdout or '').strip()
    if stdout:
        try:
            data = json.loads(stdout)
        except Exception:
            data = {'raw': stdout}
    else:
        data = {}
    if res.returncode != 0:
        raise RuntimeError(json.dumps({'stdout': stdout, 'stderr': (res.stderr or '').strip(), 'code': res.returncode}, ensure_ascii=False))
    return data


def load_instagram_browser_accounts():
    data = load_json(INSTAGRAM_BROWSER_ACCOUNTS_PATH, {'accounts': []})
    if isinstance(data, dict) and 'accounts' in data and isinstance(data['accounts'], list):
        return data
    return {'accounts': []}


def save_instagram_browser_accounts(data):
    save_json(INSTAGRAM_BROWSER_ACCOUNTS_PATH, data)


def upsert_instagram_browser_account(account_key: str, username: str = '', note: str = ''):
    data = load_instagram_browser_accounts()
    accounts = data['accounts']
    found = None
    for item in accounts:
        if item.get('account_key') == account_key:
            found = item
            break
    if not found:
        found = {'account_key': account_key}
        accounts.append(found)
    if username:
        found['username'] = username
    if note:
        found['note'] = note
    save_instagram_browser_accounts(data)
    return found


def run_instagram_browser_runner(args):
    cmd = ['node', '/root/.openclaw/workspace/projects/instagram-browser-fallback/runner.js'] + args
    res = subprocess.run(cmd, capture_output=True, text=True)
    stdout = (res.stdout or '').strip()
    if stdout:
        try:
            data = json.loads(stdout)
        except Exception:
            data = {'raw': stdout}
    else:
        data = {}
    if res.returncode != 0:
        raise RuntimeError(json.dumps({'stdout': stdout, 'stderr': (res.stderr or '').strip(), 'code': res.returncode}, ensure_ascii=False))
    return data


def load_instagram_browser_jobs():
    data = load_json(INSTAGRAM_BROWSER_JOBS_PATH, {'jobs': []})
    if isinstance(data, dict) and 'jobs' in data and isinstance(data['jobs'], list):
        return data
    return {'jobs': []}


def save_instagram_browser_jobs(data):
    save_json(INSTAGRAM_BROWSER_JOBS_PATH, data)


def create_instagram_browser_job(kind: str, account_key: str, command: list):
    jobs = load_instagram_browser_jobs()
    job_id = str(int(time.time() * 1000))
    log_path = f"/root/.openclaw/workspace/projects/instagram-browser-fallback/{job_id}.log"
    shell = ' '.join([shlex_quote(x) for x in ['node', '/root/.openclaw/workspace/projects/instagram-browser-fallback/runner.js'] + command])
    proc = subprocess.Popen(f"{shell} > {shlex_quote(log_path)} 2>&1", shell=True)
    job = {
        'job_id': job_id,
        'kind': kind,
        'account_key': account_key,
        'command': command,
        'pid': proc.pid,
        'log_path': log_path,
        'created_at': int(time.time()),
        'status': 'running',
    }
    jobs['jobs'].append(job)
    save_instagram_browser_jobs(jobs)
    return job


def shlex_quote(s: str):
    import shlex
    return shlex.quote(s)


def get_instagram_browser_job(job_id: str):
    jobs = load_instagram_browser_jobs()
    for job in jobs.get('jobs', []):
        if job.get('job_id') == job_id:
            return job
    return None


def fetch_post_insights(cfg, post_id: str, metrics: str, period: str = '', since: str = '', until: str = '', page_id: str = ''):
    token = get_page_access_token(page_id) if page_id else (((load_json(META_SESSION_PATH, {}).get('token') or {}).get('access_token')) or '')
    params = {
        'metric': metrics,
        'access_token': token,
    }
    if period:
        params['period'] = period
    if since:
        params['since'] = since
    if until:
        params['until'] = until
    url = f"https://graph.facebook.com/{cfg['graph_api_version']}/{post_id}/insights?{urllib.parse.urlencode(params)}"
    return graph_get(url)

PAGE_INSIGHTS_METRICS = [
    {
        'name': 'page_impressions',
        'description': 'Total number of times any content from the Page was shown.',
        'periods': ['day', 'week', 'days_28', 'lifetime'],
        'unit': 'count',
        'object': 'page',
    },
    {
        'name': 'page_impressions_unique',
        'description': 'The number of unique people who saw content from the Page.',
        'periods': ['day', 'week', 'days_28'],
        'unit': 'count',
        'object': 'page',
    },
    {
        'name': 'page_engagement',
        'description': 'Sum of all engagements (reactions, comments, shares, clicks).',
        'periods': ['day', 'week', 'days_28'],
        'unit': 'count',
        'object': 'page',
    },
    {
        'name': 'page_engaged_users',
        'description': 'Number of people who engaged with the Page in the period.',
        'periods': ['day', 'week', 'days_28'],
        'unit': 'count',
        'object': 'page',
    },
    {
        'name': 'page_consumptions',
        'description': 'Total number of clicks on post links, call-to-action buttons, etc.',
        'periods': ['day', 'week', 'days_28'],
        'unit': 'count',
        'object': 'page',
    },
    {
        'name': 'page_consumptions_unique',
        'description': 'Unique people who clicked on content from the Page.',
        'periods': ['day', 'week', 'days_28'],
        'unit': 'count',
        'object': 'page',
    },
    {
        'name': 'page_fans',
        'description': 'Total number of people who like the Page.',
        'periods': ['lifetime'],
        'unit': 'count',
        'object': 'page',
    },
    {
        'name': 'page_fan_adds',
        'description': 'How many new fans (likes) were added.',
        'periods': ['day', 'week', 'days_28'],
        'unit': 'count',
        'object': 'page',
    },
    {
        'name': 'page_fan_removes',
        'description': 'How many unlikes were recorded in the period.',
        'periods': ['day', 'week', 'days_28'],
        'unit': 'count',
        'object': 'page',
    },
    {
        'name': 'page_posts_impressions_organic',
        'description': 'Impressions for all organic posts.',
        'periods': ['day', 'week', 'days_28'],
        'unit': 'count',
        'object': 'page',
    },
]

AD_INSIGHTS_METRICS = [
    {
        'name': 'impressions',
        'description': 'Number of times the ad, ad set or campaign was shown.',
        'supported_objects': ['ad', 'adset', 'campaign', 'account'],
        'unit': 'count',
    },
    {
        'name': 'reach',
        'description': 'Unique people who saw the ad or campaign.',
        'supported_objects': ['ad', 'adset', 'campaign', 'account'],
        'unit': 'count',
    },
    {
        'name': 'clicks',
        'description': 'Total clicks on all attachments in the ad(s).',
        'supported_objects': ['ad', 'adset', 'campaign'],
        'unit': 'count',
    },
    {
        'name': 'inline_link_clicks',
        'description': 'Clicks on links that take people off Facebook or Instagram.',
        'supported_objects': ['ad', 'adset', 'campaign'],
        'unit': 'count',
    },
    {
        'name': 'spend',
        'description': 'Amount spent on the ads during the period (in account currency).',
        'supported_objects': ['ad', 'adset', 'campaign'],
        'unit': 'currency',
    },
    {
        'name': 'frequency',
        'description': 'Average number of times each person saw the ad across the period.',
        'supported_objects': ['ad', 'adset', 'campaign'],
        'unit': 'ratio',
    },
    {
        'name': 'cost_per_result',
        'description': 'Average cost paid for the optimization result (depends on objective).',
        'supported_objects': ['ad', 'adset', 'campaign'],
        'unit': 'currency',
    },
    {
        'name': 'cpc',
        'description': 'Cost per link click.',
        'supported_objects': ['ad', 'adset', 'campaign'],
        'unit': 'currency',
    },
    {
        'name': 'cpm',
        'description': 'Cost per thousand impressions.',
        'supported_objects': ['ad', 'adset', 'campaign'],
        'unit': 'currency',
    },
    {
        'name': 'actions',
        'description': 'Breakdown of actions (purchases, leads, adds to cart, etc.) available when the ad is optimized for the action.',
        'supported_objects': ['ad', 'adset', 'campaign'],
        'unit': 'list',
    },
]

# ── Dashboard HTML constants ──────────────────────────────────────────────────
# Split around the injected state JSON to avoid f-string/brace escaping issues.

# Panel assets moved to templates/panel.html and static/panel.{css,js}



# ── Panel auth helpers ────────────────────────────────────────────────────────

def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + '|' + password).encode()).hexdigest()


def _new_token(prefix: str = 'mkt') -> str:
    return prefix + '_' + base64.urlsafe_b64encode(hashlib.sha256(f"{time.time()}:{hashlib.sha256(str(time.time()).encode()).hexdigest()}".encode()).digest())[:32].decode().rstrip('=')


def load_users() -> dict:
    return load_json(USERS_PATH, {})


def save_users(data: dict):
    save_json(USERS_PATH, data)


def load_api_keys() -> dict:
    return load_json(API_KEYS_PATH, {})


def save_api_keys(data: dict):
    save_json(API_KEYS_PATH, data)


def load_companies() -> dict:
    return load_json(COMPANIES_PATH, {})


def save_companies(data: dict):
    save_json(COMPANIES_PATH, data)


# ── CRM LEADS SYNC ──────────────────────────────────────────────────────────

def load_crm_sync_state() -> dict:
    return load_json(CRM_SYNC_STATE_PATH, {})

def save_crm_sync_state(data: dict):
    save_json(CRM_SYNC_STATE_PATH, data)

_CRM_ALT_FIELD_NAMES = {
    'name':    ['full_name', 'nome', 'name', 'first_name'],
    'phone':   ['phone_number', 'telefone', 'celular', 'phone', 'mobile_phone', 'whatsapp'],
    'email':   ['email', 'e-mail'],
    'company': ['company_name', 'empresa', 'company'],
}

def _extract_lead_fields(lead: dict, field_map: dict) -> dict:
    raw = {item['name']: (item.get('values') or [''])[0] for item in (lead.get('field_data') or [])}
    result: dict = {}
    # apply explicit field_map
    for crm_field, meta_field in (field_map or {}).items():
        if meta_field and meta_field in raw:
            result[crm_field] = raw[meta_field]
    # auto-detect required fields not yet mapped
    for crm_field, alts in _CRM_ALT_FIELD_NAMES.items():
        if crm_field not in result:
            for alt in alts:
                if alt in raw:
                    result[crm_field] = raw[alt]
                    break
    # remaining Meta fields go to custom_fields
    mapped_meta = set((field_map or {}).values()) | {a for alts in _CRM_ALT_FIELD_NAMES.values() for a in alts}
    extras = {k: v for k, v in raw.items() if k not in mapped_meta}
    if extras:
        result.setdefault('custom_fields', {}).update(extras)
    return result

def _send_to_crm_webhook(webhook_url: str, payload: dict) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(webhook_url, data=body, headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return {'ok': True, 'status': resp.status}
    except urllib.error.HTTPError as e:
        return {'ok': False, 'error': f'HTTP {e.code}', 'detail': e.read().decode('utf-8', errors='replace')[:300]}
    except Exception as e:
        return {'ok': False, 'error': str(e)}

def sync_company_leads_to_crm(company_id: str, company: dict) -> dict:
    crm = (company.get('bindings') or {}).get('crm') or {}
    if not crm.get('enabled') or not crm.get('webhook_url'):
        return {'ok': False, 'skipped': True, 'reason': 'not_enabled'}
    page_id = str(((company.get('bindings') or {}).get('meta') or {}).get('page_id') or '')
    form_ids = [str(f) for f in (crm.get('form_ids') or []) if str(f).strip()]
    if not form_ids or not page_id:
        return {'ok': False, 'skipped': True, 'reason': 'no_forms_or_page'}
    cfg = load_config()
    access_token = get_page_access_token(page_id)
    if not access_token:
        return {'ok': False, 'error': 'no_access_token'}
    sync_state = load_crm_sync_state()
    webhook_url = crm['webhook_url']
    field_map = crm.get('field_map') or {}
    pipeline_id = crm.get('pipeline_id')
    stage_id = crm.get('stage_id')
    custom_fields_cfg = crm.get('custom_fields') or {}
    total_sent = 0
    total_skipped = 0
    send_errors = []
    for form_id in form_ids:
        state_key = f'{company_id}:{form_id}'
        sent_ids: set = set(sync_state.get(state_key) or [])
        fetched_leads: list = []
        after = None
        while True:
            params = {
                'fields': 'id,created_time,field_data,ad_name,campaign_name',
                'access_token': access_token,
                'limit': '100',
            }
            if after:
                params['after'] = after
            url = f"https://graph.facebook.com/{cfg['graph_api_version']}/{form_id}/leads?{urllib.parse.urlencode(params)}"
            try:
                result = graph_get(url)
                page_leads = result.get('data') or []
                fetched_leads.extend(page_leads)
                paging = result.get('paging') or {}
                if not paging.get('next') or not page_leads:
                    break
                after = (paging.get('cursors') or {}).get('after')
                if not after:
                    break
            except Exception as e:
                send_errors.append(f'form {form_id}: {e}')
                break
        for lead in fetched_leads:
            lead_id = lead.get('id', '')
            if not lead_id or lead_id in sent_ids:
                continue
            payload = _extract_lead_fields(lead, field_map)
            if not payload.get('name') and not payload.get('phone'):
                total_skipped += 1
                continue
            if pipeline_id is not None:
                payload['pipeline_id'] = pipeline_id
            if stage_id is not None:
                payload['stage_id'] = stage_id
            if custom_fields_cfg:
                payload.setdefault('custom_fields', {}).update(custom_fields_cfg)
            res = _send_to_crm_webhook(webhook_url, payload)
            if res.get('ok'):
                sent_ids.add(lead_id)
                total_sent += 1
            else:
                send_errors.append(f'lead {lead_id}: {res.get("error")}')
        sync_state[state_key] = list(sent_ids)
    save_crm_sync_state(sync_state)
    summary = f'{total_sent} leads enviados'
    if total_skipped:
        summary += f', {total_skipped} sem nome/telefone ignorados'
    if send_errors:
        summary += f', {len(send_errors)} erro(s)'
    return {'ok': True, 'sent': total_sent, 'skipped': total_skipped, 'errors': send_errors, 'summary': summary}

def check_and_run_crm_syncs():
    companies = load_companies()
    updated = False
    for company_id, company in list(companies.items()):
        crm = (company.get('bindings') or {}).get('crm') or {}
        if not crm.get('enabled') or not crm.get('webhook_url'):
            continue
        try:
            result = sync_company_leads_to_crm(company_id, company)
            if result.get('ok') and not result.get('skipped'):
                companies[company_id].setdefault('bindings', {}).setdefault('crm', {})['last_sync_at'] = int(time.time())
                companies[company_id]['bindings']['crm']['last_sync_result'] = result.get('summary', '')
                updated = True
        except Exception:
            pass
    if updated:
        save_companies(companies)


def ensure_auth_bootstrap():
    users = load_users()
    changed = False
    admin_email = 'luispessoa18@gmail.com'
    admin = users.get(admin_email)
    if not admin:
        salt = hashlib.sha256(f'{time.time()}|{admin_email}'.encode()).hexdigest()[:16]
        users[admin_email] = {
            'email': admin_email,
            'name': 'Luis Pessoa',
            'role': 'admin',
            'salt': salt,
            'password_hash': _hash_password('Luis@9669', salt),
            'created_at': int(time.time()),
            'updated_at': int(time.time()),
            'api_key_ids': [],
            'allowed_page_ids': [],
        }
        changed = True
    secrets = load_secrets()
    if not secrets.get(PANEL_ADMIN_TOKEN_NAME):
        set_secret(PANEL_ADMIN_TOKEN_NAME, _new_token('panel'))
    if not secrets.get('META_PANEL_SESSION_SECRET'):
        set_secret('META_PANEL_SESSION_SECRET', _new_token('session'))
    api_keys = load_api_keys()
    if not secrets.get('META_PANEL_DEFAULT_API_KEY'):
        raw_key = _new_token('mpk')
        key_id = hashlib.sha256(raw_key.encode()).hexdigest()[:16]
        api_keys[key_id] = {
            'id': key_id,
            'label': 'Default admin key',
            'user_email': admin_email,
            'key_hash': hashlib.sha256(raw_key.encode()).hexdigest(),
            'created_at': int(time.time()),
            'revoked': False,
            'last_used_at': 0,
        }
        users[admin_email].setdefault('api_key_ids', []).append(key_id)
        set_secret('META_PANEL_DEFAULT_API_KEY', raw_key)
        changed = True
        save_api_keys(api_keys)
    if changed:
        save_users(users)


def get_user_by_email(email: str) -> dict:
    return (load_users() or {}).get(email, {})


def is_admin_user(user: dict) -> bool:
    return (user or {}).get('role') == 'admin'


def get_allowed_page_ids_for_user(user: dict) -> list:
    if not user or is_admin_user(user):
        return []
    vals = user.get('allowed_page_ids') or []
    return [str(v) for v in vals if str(v).strip()]


def get_allowed_ad_account_ids_for_user(user: dict) -> list:
    if not user or is_admin_user(user):
        return []
    vals = user.get('allowed_ad_account_ids') or []
    return [normalize_ad_account_id(str(v)) for v in vals if normalize_ad_account_id(str(v))]


def page_allowed_for_user(user: dict, page_id: str) -> bool:
    if not page_id:
        return False
    if not user or is_admin_user(user):
        return True
    if str(page_id) in set(get_allowed_page_ids_for_user(user)):
        return True
    user_email = (user.get('email') or '').strip().lower()
    if user_email and user_email not in ('legacy-admin', ''):
        own_session = get_meta_session_for_panel_user(user_email)
        own_page_ids = {str(p.get('id', '')) for p in (own_session.get('pages') or [])}
        if str(page_id) in own_page_ids:
            return True
    return False


def ad_account_allowed_for_user(user: dict, ad_account_id: str) -> bool:
    ad_account_id = normalize_ad_account_id(ad_account_id)
    if not ad_account_id:
        return False
    if not user or is_admin_user(user):
        return True
    return ad_account_id in set(get_allowed_ad_account_ids_for_user(user))



def require_panel_auth(panel_auth: str = '', panel_user: str = '', request=None):
    authed = _panel_session_valid(panel_auth or '', panel_user or '')
    if not authed and request is not None:
        authed = _panel_auth_ok(request, panel_auth or '', panel_user or '')
    if not authed:
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    return None


def current_panel_user(panel_auth: str = '', panel_user: str = '', request=None) -> dict:
    # Accept either a valid session cookie OR a valid API key (via request object)
    authed = _panel_session_valid(panel_auth or '', panel_user or '')
    if not authed and request is not None:
        authed = _panel_auth_ok(request, panel_auth or '', panel_user or '')
    if not authed:
        return {}
    if panel_user and panel_user not in ('legacy-admin', ''):
        return get_user_by_email((panel_user or '').strip().lower()) or {'email': panel_user, 'role': 'admin'}
    return {'email': 'legacy-admin', 'name': 'Legacy Admin', 'role': 'admin'}


def filter_pages_for_user(user: dict, pages: list) -> list:
    if is_admin_user(user):
        return pages
    allowed = set(get_allowed_page_ids_for_user(user))
    return [p for p in (pages or []) if str((p or {}).get('id', '')) in allowed]


def filter_companies_for_user(user: dict, companies: dict) -> dict:
    if is_admin_user(user):
        return dict(companies or {})
    allowed = set(get_allowed_page_ids_for_user(user))
    user_email = (user.get('email') or '').strip().lower()
    if user_email and user_email not in ('legacy-admin', ''):
        own_session = get_meta_session_for_panel_user(user_email)
        for p in (own_session.get('pages') or []):
            own_id = str(p.get('id', ''))
            if own_id:
                allowed.add(own_id)
    out = {}
    for cid, company in (companies or {}).items():
        meta = ((company or {}).get('bindings') or {}).get('meta') or {}
        page_id = str(meta.get('page_id') or (company or {}).get('page_id') or (company or {}).get('id') or '')
        if page_id and page_id in allowed:
            out[cid] = company
    return out


def filter_brand_profiles_for_user(user: dict, profiles: dict) -> dict:
    if is_admin_user(user):
        return dict(profiles or {})
    allowed = set(get_allowed_page_ids_for_user(user))
    return {str(pid): prof for pid, prof in (profiles or {}).items() if str(pid) in allowed}


def merge_pages_unique(*pages_lists) -> list:
    merged = []
    seen = set()
    for pages in pages_lists:
        for p in (pages or []):
            pid = str((p or {}).get('id', '') or '')
            if not pid or pid in seen:
                continue
            seen.add(pid)
            merged.append(p)
    return merged


def verify_user_password(email: str, password: str) -> bool:
    user = get_user_by_email(email)
    if not user:
        return False
    return user.get('password_hash') == _hash_password(password, user.get('salt', ''))


def _panel_session_token_for_email(email: str) -> str:
    secret = get_secret('META_PANEL_SESSION_SECRET')
    if not secret or not email:
        return ''
    return hashlib.sha256(f'{secret}|{email}'.encode()).hexdigest()


def _panel_session_token() -> str:
    admin_token = get_secret(PANEL_ADMIN_TOKEN_NAME)
    if not admin_token:
        return ''
    return hashlib.sha256(admin_token.encode()).hexdigest()


def _panel_session_valid(token: str, user_email: str = '') -> bool:
    if user_email:
        expected = _panel_session_token_for_email(user_email)
        if expected and token == expected:
            return True
    expected = _panel_session_token()
    return bool(expected and token == expected)


def _api_key_from_request(request: Request) -> str:
    auth = request.headers.get('authorization', '')
    if auth.lower().startswith('bearer '):
        return auth.split(' ', 1)[1].strip()
    header_key = (request.headers.get('x-api-key', '') or '').strip()
    if header_key:
        return header_key
    # also accept api_key as query param
    return (request.query_params.get('api_key', '') or '').strip()


def _panel_auth_ok(request: Request, panel_auth: str = '', panel_user: str = '') -> bool:
    """Accept either a valid panel session cookie OR a valid API key."""
    if _panel_session_valid(panel_auth, panel_user):
        return True
    raw = _api_key_from_request(request)
    if not raw:
        return False
    key_hash = hashlib.sha256(raw.encode()).hexdigest()
    api_keys = load_api_keys()
    for meta in api_keys.values():
        if meta.get('revoked'):
            continue
        if meta.get('key_hash') == key_hash:
            return True
    return False


def _log_api_key_usage(request: Request, key_meta: dict, status_code: int):
    entry = {
        'ts': int(time.time()),
        'key_id': key_meta.get('id', ''),
        'user_email': key_meta.get('user_email', ''),
        'path': str(request.url.path),
        'method': request.method,
        'status_code': status_code,
        'client': (request.client.host if request.client else ''),
    }
    API_KEY_USAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with API_KEY_USAGE_PATH.open('a') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')


def authenticate_api_key(request: Request):
    raw = _api_key_from_request(request)
    if not raw:
        return None, JSONResponse({'ok': False, 'error': 'missing_api_key'}, status_code=401)
    key_hash = hashlib.sha256(raw.encode()).hexdigest()
    api_keys = load_api_keys()
    for meta in api_keys.values():
        if meta.get('revoked'):
            continue
        if meta.get('key_hash') == key_hash:
            meta['last_used_at'] = int(time.time())
            api_keys[meta.get('id')] = meta
            save_api_keys(api_keys)
            return meta, None
    return None, JSONResponse({'ok': False, 'error': 'invalid_api_key'}, status_code=401)


ensure_auth_bootstrap()


# ── Scheduled posts ───────────────────────────────────────────────────────────

def load_scheduled_posts() -> dict:
    return load_json(SCHEDULED_POSTS_PATH, {})

def save_scheduled_posts(data: dict):
    save_json(SCHEDULED_POSTS_PATH, data)

def load_content_plans() -> dict:
    return load_json(CONTENT_PLANS_PATH, {})

def save_content_plans(data: dict):
    save_json(CONTENT_PLANS_PATH, data)

def load_agents_config() -> dict:
    return load_json(AGENTS_CONFIG_PATH, {})

def save_agents_config(data: dict):
    save_json(AGENTS_CONFIG_PATH, data)

def get_agent_system_note(key: str, page_id: str = '') -> str:
    if page_id:
        profile = get_brand_profile(str(page_id))
        notes = profile.get('agent_system_notes') or {}
        if isinstance(notes, dict):
            note = (notes.get(key) or '').strip()
            if note:
                return note
    cfg = load_agents_config()
    agent = cfg.get(key) or {}
    return (agent.get('system_note') or '').strip()

def get_image_template(page_id: str = '') -> str:
    if page_id:
        profile = get_brand_profile(str(page_id))
        tpl = (profile.get('image_template') or '').strip()
        return tpl if tpl else DEFAULT_IMAGE_TEMPLATE
    cfg = load_agents_config()
    tpl = (cfg.get('image_template') or '').strip()
    return tpl if tpl else DEFAULT_IMAGE_TEMPLATE

def get_designer_references(page_id: str = '') -> list:
    if page_id:
        profile = get_brand_profile(str(page_id))
        refs = profile.get('designer_references')
        if isinstance(refs, list) and refs:
            return refs
    cfg = load_agents_config()
    return list(cfg.get('designer_references') or [])


def _build_company_agent_adjustments(page_id: str) -> dict:
    profile = get_brand_profile(page_id)
    brand_name = profile.get('brand_name') or profile.get('page_name') or 'a marca'
    description = profile.get('description') or ''
    visual_style = profile.get('visual_style') or 'moderno e profissional'
    target_audience = profile.get('target_audience') or ''
    tone = profile.get('tone') or 'profissional'
    colors = ', '.join(str(c) for c in (profile.get('colors') or [])[:6] if str(c).strip()) or 'cores da marca'
    icp = profile.get('icp_onboarding_text') or ''
    ref_style = profile.get('reference_style_prompt') or ''
    font_preference = profile.get('font_preference') or ''
    best_offer = profile.get('best_offer') or ''
    competitors = profile.get('competitors') or ''
    if isinstance(competitors, list):
        competitors = ', '.join(str(v).strip() for v in competitors if str(v).strip())

    brand_context = (
        f'Marca: {brand_name}\n'
        f'Descrição: {description}\n'
        f'Nicho/produto: {profile.get("key_products") or description}\n'
        f'Público-alvo: {target_audience}\n'
        f'Tom: {tone}\n'
        f'Oferta principal: {best_offer}\n'
        f'Estilo visual: {visual_style}\n'
        f'Paleta de cores: {colors}\n'
        + (f'Preferência tipográfica: {font_preference}\n' if font_preference else '')
        + (f'Síntese visual das referências: {ref_style}\n' if ref_style else '')
        + (f'Concorrentes / referências de mercado: {competitors}\n' if competitors else '')
        + (f'ICP: {icp}\n' if icp else '')
    )

    template_prompt = (
        'Você é um diretor de arte especialista em Instagram. '
        'Adapte o template de prompt de imagem abaixo para a marca descrita. '
        'REGRAS OBRIGATÓRIAS:\n'
        '1. Mantenha TODOS os placeholders {VARIAVEL} exatamente como estão\n'
        '2. Reescreva as partes descritivas (cenário, ambiente, personagem, estilo) para refletir a marca\n'
        '3. Mantenha a mesma estrutura de seções\n'
        '4. A reserva de logo DEVE ficar no canto inferior ESQUERDO\n'
        '5. Retorne SOMENTE o template adaptado, sem explicações\n\n'
        f'Perfil da marca:\n{brand_context}\n\n'
        f'Template base:\n{DEFAULT_IMAGE_TEMPLATE}'
    )
    director_prompt = (
        'Você é um diretor de arte especialista. '
        f'Crie instruções específicas e objetivas para o agente que preenche as variáveis do template de imagem da marca "{brand_name}". '
        'As instruções devem guiar cenário, personagem, estilo visual, iluminação e emoção. '
        'Seja específico ao negócio — evite generalismos. '
        'Formato: lista de regras curtas (SEMPRE / NUNCA / Preferir). Máx 10 linhas.\n\n'
        f'Perfil da marca:\n{brand_context}'
    )
    agent_specs = {
        'copy_generation': (
            f'Você é o redator da marca "{brand_name}". '
            'Crie instruções específicas para o agente de copy escrever legendas e chamadas coerentes com a marca, produto e ICP. '
            'Inclua tom, gatilhos, tipo de CTA, promessas permitidas e o que evitar. '
            'Formato: lista curta de regras práticas. Máx 10 linhas.\n\n'
            f'Perfil da marca:\n{brand_context}'
        ),
        'plan_generation': (
            f'Você é o estrategista editorial da marca "{brand_name}". '
            'Crie instruções para o agente que monta calendários e planos de conteúdo. '
            'Defina pilares editoriais, equilíbrio entre conteúdo e oferta, recorrência de temas e sazonalidade do produto. '
            'Formato: lista curta de regras práticas. Máx 10 linhas.\n\n'
            f'Perfil da marca:\n{brand_context}'
        ),
        'focus_suggestion': (
            f'Você é o estrategista de foco de campanha/post da marca "{brand_name}". '
            'Crie instruções para o agente sugerir ângulos e focos de conteúdo sempre ligados ao produto, ICP e momento da jornada. '
            'Formato: lista curta de regras práticas. Máx 10 linhas.\n\n'
            f'Perfil da marca:\n{brand_context}'
        ),
        'brand_analysis': (
            f'Você é o analista de marca da empresa "{brand_name}". '
            'Crie instruções para análises de posicionamento, diferenciação e consistência da marca. '
            'Formato: lista curta de regras práticas. Máx 10 linhas.\n\n'
            f'Perfil da marca:\n{brand_context}'
        ),
        'campaign_analysis': (
            f'Você é o analista de campanhas da marca "{brand_name}". '
            'Crie instruções para avaliar campanhas com foco no produto, qualidade do lead, aderência ao ICP e clareza da oferta. '
            'Formato: lista curta de regras práticas. Máx 10 linhas.\n\n'
            f'Perfil da marca:\n{brand_context}'
        ),
        'profile_analysis': (
            f'Você é o analista de perfil Instagram da marca "{brand_name}". '
            'Crie instruções para avaliar bio, feed, destaques, consistência visual e adequação ao ICP. '
            'Formato: lista curta de regras práticas. Máx 10 linhas.\n\n'
            f'Perfil da marca:\n{brand_context}'
        ),
        'icp_analysis': (
            f'Você é o analista de ICP da marca "{brand_name}". '
            'Crie instruções para revisar dores, desejos, objeções, estágio de consciência e perfil socioeconômico do cliente ideal. '
            'Formato: lista curta de regras práticas. Máx 10 linhas.\n\n'
            f'Perfil da marca:\n{brand_context}'
        ),
    }
    from concurrent.futures import ThreadPoolExecutor, as_completed as _as_completed
    _agent_feat_map = {
        'copy_generation': 'copy_generation', 'plan_generation': 'plan_generation',
        'focus_suggestion': 'focus_suggestion', 'brand_analysis': 'brand_analysis',
        'campaign_analysis': 'brand_analysis', 'profile_analysis': 'brand_analysis',
        'icp_analysis': 'brand_analysis',
    }
    all_tasks = {
        '_template': ('prompt_generation', template_prompt, 90),
        '_director': ('copy_generation', director_prompt, 60),
        **{k: (_agent_feat_map[k], v, 60) for k, v in agent_specs.items()},
    }
    ai_results: dict = {}
    with ThreadPoolExecutor(max_workers=len(all_tasks)) as _pool:
        _futures = {_pool.submit(_ai_generate_text, feat, prompt, tmo, False): key
                    for key, (feat, prompt, tmo) in all_tasks.items()}
        for _f in _as_completed(_futures):
            _k = _futures[_f]
            try:
                ai_results[_k] = _f.result()
            except Exception:
                ai_results[_k] = {}
    new_template = (ai_results.get('_template', {}).get('text') or '').strip()
    new_director = (ai_results.get('_director', {}).get('text') or '').strip()
    generated_notes: dict[str, str] = {}
    for key in agent_specs:
        note = (ai_results.get(key, {}).get('text') or '').strip()
        if note:
            generated_notes[key] = note
    notes = profile.get('agent_system_notes') or {}
    if not isinstance(notes, dict):
        notes = {}
    if new_director:
        notes['prompt_generation'] = new_director
    for key, note in generated_notes.items():
        notes[key] = note
    updates: dict = {}
    if new_template:
        updates['image_template'] = new_template
    if notes:
        updates['agent_system_notes'] = notes
    if updates:
        upsert_brand_profile(page_id, updates)
    return {'image_template': new_template, 'director_note': new_director, 'agent_notes': generated_notes}


def _build_art_agent_adjustments(page_id: str) -> dict:
    """Generate only image template + art director note, in parallel."""
    profile = get_brand_profile(page_id)
    brand_name = profile.get('brand_name') or profile.get('page_name') or 'a marca'
    description = profile.get('description') or ''
    visual_style = profile.get('visual_style') or 'moderno e profissional'
    target_audience = profile.get('target_audience') or ''
    tone = profile.get('tone') or 'profissional'
    colors = ', '.join(str(c) for c in (profile.get('colors') or [])[:6] if str(c).strip()) or 'cores da marca'
    icp = profile.get('icp_onboarding_text') or ''
    ref_style = profile.get('reference_style_prompt') or ''
    font_preference = profile.get('font_preference') or ''
    best_offer = profile.get('best_offer') or ''
    brand_context = (
        f'Marca: {brand_name}\nDescrição: {description}\n'
        f'Nicho/produto: {profile.get("key_products") or description}\n'
        f'Público-alvo: {target_audience}\nTom: {tone}\nOferta principal: {best_offer}\n'
        f'Estilo visual: {visual_style}\nPaleta de cores: {colors}\n'
        + (f'Preferência tipográfica: {font_preference}\n' if font_preference else '')
        + (f'Síntese visual das referências: {ref_style}\n' if ref_style else '')
        + (f'ICP: {icp}\n' if icp else '')
    )
    template_prompt = (
        'Você é um diretor de arte especialista em Instagram. '
        'Adapte o template de prompt de imagem abaixo para a marca descrita. '
        'REGRAS OBRIGATÓRIAS:\n'
        '1. Mantenha TODOS os placeholders {VARIAVEL} exatamente como estão\n'
        '2. Reescreva as partes descritivas (cenário, ambiente, personagem, estilo) para refletir a marca\n'
        '3. Mantenha a mesma estrutura de seções\n'
        '4. A reserva de logo DEVE ficar no canto inferior ESQUERDO\n'
        '5. Retorne SOMENTE o template adaptado, sem explicações\n\n'
        f'Perfil da marca:\n{brand_context}\n\nTemplate base:\n{DEFAULT_IMAGE_TEMPLATE}'
    )
    director_prompt = (
        'Você é um diretor de arte especialista. '
        f'Crie instruções específicas e objetivas para o agente que preenche as variáveis do template de imagem da marca "{brand_name}". '
        'As instruções devem guiar cenário, personagem, estilo visual, iluminação e emoção. '
        'Seja específico ao negócio — evite generalismos. '
        'Formato: lista de regras curtas (SEMPRE / NUNCA / Preferir). Máx 10 linhas.\n\n'
        f'Perfil da marca:\n{brand_context}'
    )
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as _pool:
        tpl_future = _pool.submit(_ai_generate_text, 'prompt_generation', template_prompt, 90, False)
        dir_future = _pool.submit(_ai_generate_text, 'copy_generation', director_prompt, 60, False)
        tpl_res = tpl_future.result()
        dir_res = dir_future.result()
    new_template = (tpl_res.get('text') or '').strip()
    new_director = (dir_res.get('text') or '').strip()
    notes = profile.get('agent_system_notes') or {}
    if not isinstance(notes, dict):
        notes = {}
    if new_director:
        notes['prompt_generation'] = new_director
    updates: dict = {}
    if new_template:
        updates['image_template'] = new_template
    if notes:
        updates['agent_system_notes'] = notes
    if updates:
        upsert_brand_profile(page_id, updates)
    return {'image_template': new_template, 'director_note': new_director}

def add_scheduled_post(ig_user_id: str, page_name: str, access_token: str,
                        image_url: str, caption: str, scheduled_at: int,
                        page_id: str = '', ig_username: str = '',
                        source: str = '', plan_id: str = '', plan_post_id: str = '') -> dict:
    posts = load_scheduled_posts()
    import random, string
    pid = ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(12))
    entry = {
        'id': pid,
        'ig_user_id': ig_user_id,
        'ig_username': ig_username,
        'page_id': page_id,
        'page_name': page_name,
        'access_token': access_token,
        'image_url': image_url,
        'caption': caption,
        'scheduled_at': scheduled_at,
        'status': 'pending',
        'created_at': int(time.time()),
        'published_at': None,
        'error': None,
        'source': source or 'manual',
        'plan_id': plan_id or '',
        'plan_post_id': plan_post_id or '',
    }
    posts[pid] = entry
    save_scheduled_posts(posts)
    return entry

def check_and_run_scheduled_posts():
    cfg = load_config()
    now = int(time.time())
    posts = load_scheduled_posts()
    changed = False
    for pid, post in list(posts.items()):
        if post.get('status') != 'pending':
            continue
        if post.get('scheduled_at', 9999999999) > now:
            continue
        try:
            ig_image_url = _ensure_ig_accessible_url(post['image_url'], cfg)
            result = instagram_create_media(cfg, post['ig_user_id'], post['access_token'], ig_image_url, post['caption'])
            if 'error' in result:
                raise Exception(str(result['error']))
            creation_id = result.get('id', '')
            pub = instagram_publish_media(cfg, post['ig_user_id'], post['access_token'], creation_id)
            if 'error' in pub:
                raise Exception(str(pub['error']))
            posts[pid]['status'] = 'published'
            posts[pid]['published_at'] = int(time.time())
            posts[pid]['result'] = pub
        except Exception as e:
            posts[pid]['status'] = 'failed'
            posts[pid]['error'] = str(e)
        changed = True
    if changed:
        save_scheduled_posts(posts)


# ── Brand profile helpers ─────────────────────────────────────────────────────

def load_brand_profiles() -> dict:
    return load_json(BRAND_PROFILES_PATH, {})


def save_brand_profiles(data: dict):
    save_json(BRAND_PROFILES_PATH, data)


def get_brand_profile(page_id: str) -> dict:
    return load_brand_profiles().get(str(page_id), {})


def _icp_analysis_update_is_empty(value) -> bool:
    """Evita apagar ICP gerado quando o cliente envia {}, [], null ou só metadados _* por engano."""
    if value is None:
        return True
    if isinstance(value, (list, tuple)) and len(value) == 0:
        return True
    if not isinstance(value, dict):
        return False
    return not any(not str(k).startswith('_') for k in value)


def upsert_brand_profile(page_id: str, updates: dict) -> dict:
    page_id = str(page_id)
    updates = dict(updates or {})
    if 'icp_analysis' in updates and _icp_analysis_update_is_empty(updates['icp_analysis']):
        updates.pop('icp_analysis', None)
    profiles = load_brand_profiles()
    profile = profiles.get(page_id, {'page_id': page_id})
    profile.update(updates)
    profile['updated_at'] = int(time.time())
    profiles[page_id] = profile
    save_brand_profiles(profiles)
    return profile


def normalize_plan_settings(profile: dict | None) -> dict:
    raw = ((profile or {}).get('plan_settings') or {}) if isinstance((profile or {}).get('plan_settings'), dict) else {}
    posts_per_week = max(1, min(7, _safe_int(raw.get('posts_per_week', 3), 3)))
    max_carousels_per_week = max(0, min(posts_per_week, _safe_int(raw.get('max_carousels_per_week', 1), 1)))
    stories_per_day = max(0, min(3, _safe_int(raw.get('stories_per_day', 1), 1)))
    return {
        'posts_per_week': posts_per_week,
        'max_carousels_per_week': max_carousels_per_week,
        'stories_per_day': stories_per_day,
    }


def _summarize_instagram_for_brand(username: str, profile: dict, analysis: dict) -> dict:
    p = profile if isinstance(profile, dict) else {}
    a = analysis if isinstance(analysis, dict) else {}

    def clip(s, n):
        s = str(s or '')
        return s[:n] + ('…' if len(s) > n else '')

    diag = a.get('diagnosis') if isinstance(a.get('diagnosis'), dict) else {}
    header = a.get('header') if isinstance(a.get('header'), dict) else {}
    return {
        'username': (username or '').lower().lstrip('@'),
        'updated_at': int(time.time()),
        'followers': p.get('followers'),
        'following': p.get('following'),
        'posts': p.get('posts'),
        'bio_excerpt': clip(p.get('bio'), 500),
        'header_subtitle': clip(header.get('subtitle'), 400),
        'positioning_verdict': clip(diag.get('positioning_verdict'), 800),
        'central_problem': clip(diag.get('central_problem'), 500),
    }


def _build_plan_generation_extra_context(page_id: str, profile: dict) -> str:
    """Texto extra para o plano dos agentes: ICP + resumo Instagram + snapshot own na BD."""
    parts: list[str] = []
    page_id = str(page_id or '')
    icp = profile.get('icp_analysis') if isinstance(profile.get('icp_analysis'), dict) else {}
    if icp:
        overview = str(icp.get('overview', '') or '')[:1500]
        at = str(icp.get('analysis_text', '') or '')[:2000]
        recs = icp.get('recommendations') or []
        recs_txt = ''
        if isinstance(recs, list):
            recs_txt = '; '.join(str(x) for x in recs[:10])
        parts.append(
            '=== ICP salvo (use como base de público e mensagem) ===\n'
            + (overview + '\n' if overview else '')
            + (at + '\n' if at else '')
            + (('Recomendações: ' + recs_txt[:1000] + '\n') if recs_txt else '')
        )
    igsum = profile.get('instagram_scraper_analysis_summary')
    if isinstance(igsum, dict) and igsum:
        parts.append(
            '=== Última análise Instagram (scraper) ===\n'
            f"@{igsum.get('username', '')} · seguidores: {igsum.get('followers', '—')}\n"
            f"Bio: {str(igsum.get('bio_excerpt', '') or '')[:600]}\n"
            f"Posicionamento: {str(igsum.get('positioning_verdict', '') or '')[:700]}\n"
        )
    try:
        comps = db_get_competitor_summary(page_id)
        own = next((c for c in comps if c.get('is_own')), None)
        if own:
            prof = own.get('profile') if isinstance(own.get('profile'), dict) else {}
            an = own.get('analysis') if isinstance(own.get('analysis'), dict) else {}
            if prof or an:
                parts.append(
                    '=== Perfil Instagram own (último snapshot) ===\n'
                    f"@{own.get('username', '')} · seguidores: {own.get('followers', '—')}\n"
                    f"Bio: {str(prof.get('bio') or '')[:400]}\n"
                )
                if an:
                    h = an.get('header') if isinstance(an.get('header'), dict) else {}
                    d = an.get('diagnosis') if isinstance(an.get('diagnosis'), dict) else {}
                    parts.append(
                        f"Resumo IA: {str(h.get('subtitle', '') or '')[:400]}\n"
                        f"Diagnóstico: {str(d.get('positioning_verdict', '') or '')[:600]}\n"
                    )
    except Exception:
        pass
    return '\n'.join(parts).strip()


def extract_palette_from_image(path: str, max_colors: int = 6) -> list:
    try:
        with Image.open(path) as im:
            im = im.convert('RGB')
            im.thumbnail((300, 300))
            pal = im.quantize(colors=max_colors, method=Image.MEDIANCUT)
            palette = pal.getpalette() or []
            counts = sorted(pal.getcolors() or [], reverse=True)
            out = []
            for count, idx in counts[:max_colors]:
                base = idx * 3
                rgb = palette[base:base+3]
                if len(rgb) == 3:
                    hexv = '#%02X%02X%02X' % tuple(rgb)
                    if hexv not in out:
                        out.append(hexv)
            return out
    except Exception:
        return []


def extract_palette_from_url(url: str, max_colors: int = 6) -> list:
    if not url:
        return []
    tmp_name = UPLOADS_DIR / f"palette_src_{hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]}.img"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'meta-connection-panel/1.0'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
        tmp_name.write_bytes(raw)
        return extract_palette_from_image(str(tmp_name), max_colors=max_colors)
    except Exception:
        return []
    finally:
        try:
            if tmp_name.exists():
                tmp_name.unlink()
        except Exception:
            pass


def _slugify(value: str) -> str:
    v = (value or '').strip().lower()
    out = []
    for ch in v:
        if ch.isalnum():
            out.append(ch)
        elif ch in [' ', '-', '_', '.']:
            out.append('-')
    s = ''.join(out)
    while '--' in s:
        s = s.replace('--', '-')
    return s.strip('-')


def _tokenize_match_text(value: str) -> set[str]:
    src = _slugify(value or '').replace('-', ' ')
    return {t for t in src.split() if len(t) >= 3}


def _score_ad_account_for_page(ad_account: dict, page: dict | None = None, company: dict | None = None, profile: dict | None = None, bound_ad_account_id: str = '') -> tuple[int, list[str]]:
    acct = ad_account or {}
    pg = page or {}
    comp = company or {}
    prof = profile or {}
    reasons: list[str] = []
    score = 0
    acct_id_norm = normalize_ad_account_id(str(acct.get('id') or acct.get('account_id') or ''))
    # Conta vinculada diretamente à empresa → maior prioridade
    if bound_ad_account_id and acct_id_norm == bound_ad_account_id:
        score += 2000
        reasons.append('conta de anúncios vinculada ao cliente')
    account_name = str(acct.get('name') or '').strip()
    haystack = _tokenize_match_text(' '.join([
        account_name,
        str(((acct.get('business') or {}).get('name') or '')).strip(),
    ]))
    page_tokens = set()
    for raw in [
        pg.get('name', ''),
        ((pg.get('instagram_business_account') or {}).get('username') or ''),
        comp.get('name', ''),
        prof.get('brand_name', ''),
        prof.get('instagram_handle', ''),
    ]:
        page_tokens |= _tokenize_match_text(str(raw or '').replace('@', ' '))
    overlap = sorted(page_tokens & haystack)
    if overlap:
        score += min(60, 20 * len(overlap))
        reasons.append('nome relacionado: ' + ', '.join(overlap[:3]))
    preferred = str(prof.get('preferred_ad_account_id') or '').strip()
    if preferred and normalize_ad_account_id(preferred) == acct_id_norm:
        score += 1000
        reasons.append('conta preferida salva para esta página')
    return score, reasons


def ensure_company_for_page(page: dict) -> dict:
    companies = load_companies()
    page_id = str((page or {}).get('id', '') or '')
    if not page_id:
        return {}
    if page_id in companies:
        return companies[page_id]
    ig = (page or {}).get('instagram_business_account') or {}
    name = (page or {}).get('name', '') or f'Empresa {page_id}'
    company = {
        'id': page_id,
        'name': name,
        'slug': _slugify(name) or page_id,
        'created_at': int(time.time()),
        'updated_at': int(time.time()),
        'bindings': {
            'meta': {
                'page_id': page_id,
                'instagram': {
                    'ig_user_id': str(ig.get('id', '') or ''),
                    'username': ig.get('username', ''),
                }
            },
            'linkedin': {
                'author_urn': '',
                'org_urn': '',
            },
            'x': {
                'username': '',
                'user_id': '',
            }
        }
    }
    companies[page_id] = company
    save_companies(companies)
    return company


def build_company_dashboard_status(panel_user_email: str = '') -> dict:
    meta_session = get_meta_session_for_panel_user(panel_user_email) if panel_user_email else load_json(META_SESSION_PATH, {})
    linkedin_session = get_linkedin_session()
    x_session = get_x_session()
    brands = load_brand_profiles()
    pages = meta_session.get('pages', []) if isinstance(meta_session, dict) else []

    # ensure companies exist for any meta pages
    for p in pages:
        try:
            ensure_company_for_page(p or {})
        except Exception:
            pass

    companies_store = load_companies()
    companies = []

    # join brand profile data into companies
    for cid, company in (companies_store or {}).items():
        company = company or {}
        page_id = (company.get('bindings') or {}).get('meta', {}).get('page_id', '') or company.get('id', '')
        profile = brands.get(str(page_id), {}) if page_id else {}
        companies.append({
            'company_id': company.get('id', cid),
            'company_key': company.get('id', cid),
            'company_name': company.get('name', ''),
            'slug': company.get('slug', ''),
            'page_id': page_id,
            'brand_profile': profile or {},
            'bindings': company.get('bindings', {}),
        })

    meta_token = ((meta_session.get('token') or {}).get('access_token')) if isinstance(meta_session, dict) else ''
    meta_expiry = _expiry_from_session((meta_session.get('token') or {}) if isinstance(meta_session, dict) else {})
    linkedin_expiry = _expiry_from_session(linkedin_session)
    x_expiry = _expiry_from_session(x_session)

    # status global
    summary = {
        'meta': {
            'connected': bool(meta_token),
            'pages_count': len(pages),
            'ad_accounts_count': len((meta_session.get('ad_accounts') or []) if isinstance(meta_session, dict) else []),
            'me': (meta_session.get('me') or {}) if isinstance(meta_session, dict) else {},
            **meta_expiry,
            'connect_url': '/meta/connect/start',
        },
        'linkedin': {
            'connected': bool(linkedin_session.get('access_token')),
            'me': linkedin_session.get('me', {}),
            'author_urn': get_linkedin_author_urn(),
            **linkedin_expiry,
            'connect_url': '/linkedin/connect/start',
        },
        'x': {
            'connected': bool(x_session.get('access_token')),
            'me': x_session.get('me', {}),
            'scope': x_session.get('scope', ''),
            **x_expiry,
            'connect_url': '/x/connect/start',
        },
        'companies_count': len(companies),
    }

    # compute per-company platform availability
    enriched = []
    for c in companies:
        b = c.get('bindings', {}) or {}
        page_id = ((b.get('meta') or {}).get('page_id') or c.get('page_id') or '')
        ig = ((b.get('meta') or {}).get('instagram') or {})
        li = (b.get('linkedin') or {})
        xx = (b.get('x') or {})
        linkedin_bound = bool(li.get('author_urn') or li.get('org_urn'))
        x_bound = bool(xx.get('username') or xx.get('user_id'))
        enriched.append({
            **c,
            'connections': {
                'facebook': {'connected': bool(summary['meta']['connected'] and page_id), 'page_id': page_id},
                'instagram': {'connected': bool(summary['meta']['connected'] and ig.get('ig_user_id')), 'ig_user_id': ig.get('ig_user_id',''), 'username': ig.get('username','')},
                'linkedin': {'connected': bool(summary['linkedin']['connected'] and linkedin_bound), 'author_urn': li.get('author_urn', ''), 'org_urn': li.get('org_urn', '')},
                'x': {'connected': bool(summary['x']['connected'] and x_bound), 'username': xx.get('username', ''), 'user_id': xx.get('user_id', '')},
            }
        })

    return {'ok': True, 'summary': summary, 'companies': enriched}


def instagram_create_carousel_item(cfg, ig_user_id: str, access_token: str, image_url: str, host: str = 'graph.facebook.com'):
    url = f"https://{host}/{cfg['graph_api_version']}/{ig_user_id}/media"
    cmd = [
        'curl', '-sS', '-X', 'POST', url,
        '-d', f"image_url={image_url}",
        '-d', 'is_carousel_item=true',
        '-d', f"access_token={access_token}",
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(res.stdout)
    except subprocess.CalledProcessError as e:
        try:
            return json.loads(e.stdout)
        except Exception:
            return {'error': {'message': e.stderr}}


def instagram_create_carousel_container(cfg, ig_user_id: str, access_token: str, children_ids: list, caption: str, host: str = 'graph.facebook.com'):
    url = f"https://{host}/{cfg['graph_api_version']}/{ig_user_id}/media"
    children_str = ','.join(children_ids)
    cmd = [
        'curl', '-sS', '-X', 'POST', url,
        '-d', 'media_type=CAROUSEL',
        '-d', f"children={children_str}",
        '--data-urlencode', f"caption={caption}",
        '-d', f"access_token={access_token}",
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(res.stdout)
    except subprocess.CalledProcessError as e:
        try:
            return json.loads(e.stdout)
        except Exception:
            return {'error': {'message': e.stderr}}


def instagram_create_story_container(cfg, ig_user_id: str, access_token: str, image_url: str, host: str = 'graph.facebook.com'):
    url = f"https://{host}/{cfg['graph_api_version']}/{ig_user_id}/media"
    cmd = [
        'curl', '-sS', '-X', 'POST', url,
        '-d', f"image_url={image_url}",
        '-d', 'media_type=STORIES',
        '-d', f"access_token={access_token}",
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(res.stdout)
    except subprocess.CalledProcessError as e:
        try:
            return json.loads(e.stdout)
        except Exception:
            return {'error': {'message': e.stderr}}


def instagram_create_reel_container(cfg, ig_user_id: str, access_token: str, video_url: str, caption: str, share_to_feed: bool = True, host: str = 'graph.facebook.com'):
    url = f"https://{host}/{cfg['graph_api_version']}/{ig_user_id}/media"
    cmd = [
        'curl', '-sS', '-X', 'POST', url,
        '-d', f"video_url={video_url}",
        '-d', 'media_type=REELS',
        '--data-urlencode', f"caption={caption}",
        '-d', f"share_to_feed={'true' if share_to_feed else 'false'}",
        '-d', f"access_token={access_token}",
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(res.stdout)
    except subprocess.CalledProcessError as e:
        try:
            return json.loads(e.stdout)
        except Exception:
            return {'error': {'message': e.stderr}}


def instagram_check_container_status(cfg, container_id: str, access_token: str, host: str = 'graph.facebook.com'):
    params = urllib.parse.urlencode({'fields': 'status_code,status', 'access_token': access_token})
    url = f"https://{host}/{cfg['graph_api_version']}/{container_id}?{params}"
    return graph_get(url)


def _resolve_ig_context(body_or_params: dict):
    """Resolve effective (ig_user_id, token, host) from request context.

    Priority:
    1. Explicit ig_user_id + access_token in body
    2. mode=instagram_direct forced
    3. Meta Business account matched by page_id / ig_user_id / username
    4. Instagram Direct session (fallback only when no Meta account found)
    """
    ig_user_id = body_or_params.get('ig_user_id', '')
    access_token_explicit = body_or_params.get('access_token', '')
    username = body_or_params.get('username', '')
    page_id = body_or_params.get('page_id', '')
    mode = (body_or_params.get('mode', '') or '').strip().lower()

    if access_token_explicit and ig_user_id:
        return ig_user_id, access_token_explicit, 'graph.facebook.com'

    if mode == 'instagram_direct':
        direct_token = get_instagram_direct_token()
        direct_user_id = get_instagram_direct_user_id()
        return direct_user_id, direct_token, 'graph.instagram.com'

    target = get_instagram_account_by_username(username=username, ig_user_id=ig_user_id, page_id=page_id)
    if target:
        ig = target.get('instagram_business_account', {})
        return ig.get('id', ''), target.get('page_access_token', ''), 'graph.facebook.com'

    direct_token = get_instagram_direct_token()
    direct_user_id = get_instagram_direct_user_id()
    if direct_user_id and direct_token:
        return direct_user_id, direct_token, 'graph.instagram.com'

    return '', '', 'graph.facebook.com'


def fetch_adsets(cfg, ad_account_id: str, campaign_id: str = '', limit: str = '100'):
    access_token = get_meta_access_token()
    params = {
        'fields': 'id,name,status,effective_status,campaign_id,optimization_goal,billing_event,bid_strategy,daily_budget,targeting,start_time,end_time',
        'access_token': access_token,
        'limit': limit,
    }
    if campaign_id:
        url = f"https://graph.facebook.com/{cfg['graph_api_version']}/{campaign_id}/adsets?{urllib.parse.urlencode(params)}"
    else:
        url = f"https://graph.facebook.com/{cfg['graph_api_version']}/{ad_account_id}/adsets?{urllib.parse.urlencode(params)}"
    return graph_get(url)


def fetch_ads(cfg, ad_account_id: str, adset_id: str = '', limit: str = '100'):
    access_token = get_meta_access_token()
    params = {
        'fields': 'id,name,status,effective_status,adset_id,campaign_id,creative{id,name}',
        'access_token': access_token,
        'limit': limit,
    }
    if adset_id:
        url = f"https://graph.facebook.com/{cfg['graph_api_version']}/{adset_id}/ads?{urllib.parse.urlencode(params)}"
    else:
        url = f"https://graph.facebook.com/{cfg['graph_api_version']}/{ad_account_id}/ads?{urllib.parse.urlencode(params)}"
    return graph_get(url)


def fetch_insights_for_object(cfg, object_id: str, fields: str, date_preset: str = '', time_range=None, level: str = '', limit: str = '100'):
    access_token = get_meta_access_token()
    params = {
        'fields': fields,
        'access_token': access_token,
        'limit': limit,
    }
    if date_preset:
        params['date_preset'] = date_preset
    if time_range:
        params['time_range'] = json.dumps(time_range)
    if level:
        params['level'] = level
    url = f"https://graph.facebook.com/{cfg['graph_api_version']}/{object_id}/insights?{urllib.parse.urlencode(params)}"
    return graph_get(url)


def _coerce_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def _coerce_int(value, default=0):
    try:
        return int(float(value))
    except Exception:
        return default


def _index_actions(actions):
    out = {}
    for item in actions or []:
        action_type = item.get('action_type')
        if not action_type:
            continue
        out[action_type] = out.get(action_type, 0.0) + _coerce_float(item.get('value'))
    return out


def build_spend_active_ads_tree(cfg, ad_account_id: str, date_preset: str = 'last_7d', since: str = '', until: str = '', limit: str = '250'):
    time_range = None
    if since and until:
        time_range = {'since': since, 'until': until}

    account_insights = fetch_insights_for_object(
        cfg,
        ad_account_id,
        'campaign_id,campaign_name,adset_id,adset_name,ad_id,ad_name,objective,impressions,reach,clicks,inline_link_clicks,spend,cpc,cpm,ctr,frequency,actions,cost_per_action_type,purchase_roas',
        date_preset='' if time_range else date_preset,
        time_range=time_range,
        level='ad',
        limit=limit,
    )

    campaigns_resp = fetch_ad_account_campaigns(cfg, ad_account_id, None, limit)
    adsets_resp = fetch_adsets(cfg, ad_account_id, '', limit)
    ads_resp = fetch_ads(cfg, ad_account_id, '', limit)

    campaigns_map = {c.get('id', ''): c for c in campaigns_resp.get('data', []) if c.get('id')}
    adsets_map = {a.get('id', ''): a for a in adsets_resp.get('data', []) if a.get('id')}
    ads_map = {a.get('id', ''): a for a in ads_resp.get('data', []) if a.get('id')}

    tree = {}
    summary = {
        'campaigns': 0,
        'adsets': 0,
        'ads': 0,
        'spend': 0.0,
        'impressions': 0,
        'reach': 0,
        'clicks': 0,
        'inline_link_clicks': 0,
        'leads': 0.0,
        'purchases': 0.0,
        'messages': 0.0,
    }

    for row in account_insights.get('data', []) or []:
        spend = _coerce_float(row.get('spend'))
        if spend <= 0:
            continue
        campaign_id = row.get('campaign_id', '')
        adset_id = row.get('adset_id', '')
        ad_id = row.get('ad_id', '')
        actions_map = _index_actions(row.get('actions'))
        leads = actions_map.get('lead', 0.0) or actions_map.get('onsite_conversion.lead_grouped', 0.0) or actions_map.get('offsite_complete_registration_add_meta_leads', 0.0)
        purchases = actions_map.get('purchase', 0.0) or actions_map.get('omni_purchase', 0.0)
        messages = actions_map.get('onsite_conversion.messaging_conversation_started_7d', 0.0) or actions_map.get('onsite_conversion.total_messaging_connection', 0.0)

        if campaign_id not in tree:
            meta = campaigns_map.get(campaign_id, {})
            tree[campaign_id] = {
                'campaign': {
                    'id': campaign_id,
                    'name': row.get('campaign_name') or meta.get('name') or 'Campanha sem nome',
                    'status': meta.get('status', ''),
                    'effective_status': meta.get('effective_status', ''),
                    'configured_status': meta.get('configured_status', ''),
                    'objective': row.get('objective') or meta.get('objective', ''),
                    'start_time': meta.get('start_time', ''),
                    'stop_time': meta.get('stop_time', ''),
                    'daily_budget': meta.get('daily_budget', ''),
                    'lifetime_budget': meta.get('lifetime_budget', ''),
                },
                'metrics': {
                    'spend': 0.0,
                    'impressions': 0,
                    'reach': 0,
                    'clicks': 0,
                    'inline_link_clicks': 0,
                    'leads': 0.0,
                    'purchases': 0.0,
                    'messages': 0.0,
                },
                'adsets': {},
            }
        camp_node = tree[campaign_id]
        camp_node['metrics']['spend'] += spend
        camp_node['metrics']['impressions'] += _coerce_int(row.get('impressions'))
        camp_node['metrics']['reach'] += _coerce_int(row.get('reach'))
        camp_node['metrics']['clicks'] += _coerce_int(row.get('clicks'))
        camp_node['metrics']['inline_link_clicks'] += _coerce_int(row.get('inline_link_clicks'))
        camp_node['metrics']['leads'] += leads
        camp_node['metrics']['purchases'] += purchases
        camp_node['metrics']['messages'] += messages

        if adset_id not in camp_node['adsets']:
            meta = adsets_map.get(adset_id, {})
            camp_node['adsets'][adset_id] = {
                'adset': {
                    'id': adset_id,
                    'name': row.get('adset_name') or meta.get('name') or 'Adset sem nome',
                    'status': meta.get('status', ''),
                    'effective_status': meta.get('effective_status', ''),
                    'campaign_id': meta.get('campaign_id', campaign_id),
                    'optimization_goal': meta.get('optimization_goal', ''),
                    'billing_event': meta.get('billing_event', ''),
                    'bid_strategy': meta.get('bid_strategy', ''),
                    'daily_budget': meta.get('daily_budget', ''),
                    'start_time': meta.get('start_time', ''),
                    'end_time': meta.get('end_time', ''),
                    'targeting': meta.get('targeting', {}),
                },
                'metrics': {
                    'spend': 0.0,
                    'impressions': 0,
                    'reach': 0,
                    'clicks': 0,
                    'inline_link_clicks': 0,
                    'leads': 0.0,
                    'purchases': 0.0,
                    'messages': 0.0,
                },
                'ads': [],
            }
        adset_node = camp_node['adsets'][adset_id]
        adset_node['metrics']['spend'] += spend
        adset_node['metrics']['impressions'] += _coerce_int(row.get('impressions'))
        adset_node['metrics']['reach'] += _coerce_int(row.get('reach'))
        adset_node['metrics']['clicks'] += _coerce_int(row.get('clicks'))
        adset_node['metrics']['inline_link_clicks'] += _coerce_int(row.get('inline_link_clicks'))
        adset_node['metrics']['leads'] += leads
        adset_node['metrics']['purchases'] += purchases
        adset_node['metrics']['messages'] += messages

        ad_meta = ads_map.get(ad_id, {})
        adset_node['ads'].append({
            'ad': {
                'id': ad_id,
                'name': row.get('ad_name') or ad_meta.get('name') or 'Anúncio sem nome',
                'status': ad_meta.get('status', ''),
                'effective_status': ad_meta.get('effective_status', ''),
                'adset_id': ad_meta.get('adset_id', adset_id),
                'campaign_id': ad_meta.get('campaign_id', campaign_id),
                'creative': ad_meta.get('creative', {}),
            },
            'metrics': {
                'spend': spend,
                'impressions': _coerce_int(row.get('impressions')),
                'reach': _coerce_int(row.get('reach')),
                'clicks': _coerce_int(row.get('clicks')),
                'inline_link_clicks': _coerce_int(row.get('inline_link_clicks')),
                'ctr': _coerce_float(row.get('ctr')),
                'cpc': _coerce_float(row.get('cpc')),
                'cpm': _coerce_float(row.get('cpm')),
                'frequency': _coerce_float(row.get('frequency')),
                'leads': leads,
                'purchases': purchases,
                'messages': messages,
                'actions': row.get('actions', []),
                'cost_per_action_type': row.get('cost_per_action_type', []),
                'purchase_roas': row.get('purchase_roas', []),
            },
        })

        summary['ads'] += 1
        summary['spend'] += spend
        summary['impressions'] += _coerce_int(row.get('impressions'))
        summary['reach'] += _coerce_int(row.get('reach'))
        summary['clicks'] += _coerce_int(row.get('clicks'))
        summary['inline_link_clicks'] += _coerce_int(row.get('inline_link_clicks'))
        summary['leads'] += leads
        summary['purchases'] += purchases
        summary['messages'] += messages

    campaigns = []
    for camp in tree.values():
        adsets = []
        for adset in camp['adsets'].values():
            adset['ads'] = sorted(adset['ads'], key=lambda x: x['metrics']['spend'], reverse=True)
            adsets.append(adset)
        adsets.sort(key=lambda x: x['metrics']['spend'], reverse=True)
        camp['adsets'] = adsets
        campaigns.append(camp)

    campaigns.sort(key=lambda x: x['metrics']['spend'], reverse=True)
    summary['campaigns'] = len(campaigns)
    summary['adsets'] = sum(len(c['adsets']) for c in campaigns)

    return {
        'date_preset': date_preset,
        'time_range': time_range,
        'summary': summary,
        'campaigns': campaigns,
    }


def delete_meta_object(cfg, object_id: str):
    access_token = get_meta_access_token()
    params = urllib.parse.urlencode({'access_token': access_token})
    url = f"https://graph.facebook.com/{cfg['graph_api_version']}/{object_id}?{params}"
    return graph_delete(url)


app = FastAPI(title='Marketing Inc.Digital')
app.mount('/static', StaticFiles(directory=str(STATIC_DIR)), name='static')
app.mount('/uploads', StaticFiles(directory=str(UPLOADS_DIR)), name='uploads')


import asyncio


@app.middleware('http')
async def system_error_log_middleware(request: Request, call_next):
    started_at = time.time()
    response = await call_next(request)
    loggable_prefixes = ('/auth', '/panel', '/meta', '/instagram', '/linkedin', '/x', '/schedule')
    if response.status_code >= 400 and request.url.path.startswith(loggable_prefixes):
        append_system_error_log(
            'api_error_response' if response.status_code < 500 else 'server_error_response',
            'API returned error response',
            status_code=response.status_code,
            duration_ms=int((time.time() - started_at) * 1000),
            **_request_context(request),
        )
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    append_system_error_log(
        'unhandled_exception',
        'FastAPI exception handler',
        detail=str(exc),
        traceback=traceback.format_exc(),
        **_request_context(request),
    )
    return JSONResponse({'ok': False, 'error': 'internal_server_error', 'detail': str(exc)}, status_code=500)

@app.on_event('startup')
async def start_scheduler():
    init_panel_db()
    async def _loop():
        _crm_last = 0.0
        while True:
            await asyncio.sleep(60)
            try:
                check_and_run_scheduled_posts()
            except Exception:
                pass
            now = time.time()
            if now - _crm_last > 300:
                _crm_last = now
                try:
                    check_and_run_crm_syncs()
                except Exception:
                    pass
    asyncio.create_task(_loop())


@app.head('/media/generated/{filename}')
@app.get('/media/generated/{filename}')
def media_generated(filename: str):
    path = GENERATED_DIR / filename
    if not path.exists():
        return PlainTextResponse('Not found', status_code=404)
    media_type = mimetypes.guess_type(str(path))[0] or 'application/octet-stream'
    headers = {
        'Content-Disposition': 'inline',
        'Cache-Control': 'public, max-age=300',
    }
    return FileResponse(str(path), media_type=media_type, headers=headers)


@app.get('/meta/examples.json')
def meta_examples_json():
    path = BASE_DIR / 'docs' / 'examples.json'
    if not path.exists():
        return JSONResponse({'ok': False, 'error': 'examples_json_not_found'}, status_code=404)
    return json.loads(path.read_text())


@app.get('/meta/examples')
def meta_examples_markdown():
    path = BASE_DIR / 'docs' / 'examples.md'
    if not path.exists():
        return PlainTextResponse('examples.md not found', status_code=404)
    return PlainTextResponse(path.read_text(), media_type='text/markdown; charset=utf-8')


@app.get('/internal/media-debug/{filename}')
def media_debug(filename: str):
    path = GENERATED_DIR / filename
    if not path.exists():
        return JSONResponse({'ok': False, 'error': 'not_found'}, status_code=404)
    stat = path.stat()
    return {
        'ok': True,
        'filename': filename,
        'path': str(path),
        'size': stat.st_size,
        'public_url': load_config()['public_base_url'].rstrip('/') + f'/media/generated/{filename}',
    }


@app.get('/health')
def health():
    cfg = load_config()
    return {
        'ok': True,
        'service': 'meta-connection-panel',
        'public_base_url': cfg['public_base_url'],
        'webhook_url': cfg['public_base_url'].rstrip('/') + cfg['webhook_path'],
        'oauth_callback_url': cfg['public_base_url'].rstrip('/') + cfg['oauth_callback_path'],
    }


@app.get('/api/v1/me')
def api_v1_me(request: Request):
    key_meta, err = authenticate_api_key(request)
    if err:
        return err
    user = get_user_by_email(key_meta.get('user_email', ''))
    _log_api_key_usage(request, key_meta, 200)
    return {'ok': True, 'user': {'email': user.get('email', ''), 'name': user.get('name', ''), 'role': user.get('role', 'user')}, 'key': {'id': key_meta.get('id', ''), 'label': key_meta.get('label', '')}}


@app.get('/api/v1/companies')
def api_v1_companies(request: Request):
    key_meta, err = authenticate_api_key(request)
    if err:
        return err
    data = build_company_dashboard_status(panel_user or '')
    _log_api_key_usage(request, key_meta, 200)
    return data


@app.get('/', response_class=HTMLResponse)
def index(panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    is_authed = _panel_session_valid(panel_auth or '', panel_user or '')
    cfg = load_config()
    app_secret = get_secret(cfg['app_secret_name'])
    verify_token_val = get_secret(cfg['verify_token_name'])
    linkedin_client_id = get_secret(LINKEDIN_CLIENT_ID_NAME) or cfg.get('linkedin_client_id', '')
    linkedin_client_secret = get_secret(LINKEDIN_CLIENT_SECRET_NAME) or cfg.get('linkedin_client_secret', '')
    x_client_id = get_secret(X_CLIENT_ID_NAME) or cfg.get('x_client_id', '')
    x_client_secret = get_secret(X_CLIENT_SECRET_NAME) or cfg.get('x_client_secret', '')
    gemini_api_key = get_secret(GEMINI_API_KEY_NAME) or get_secret('GOOGLE_API_KEY')
    openai_api_key = get_secret(OPENAI_API_KEY_NAME)
    openai_base_url = get_secret(OPENAI_BASE_URL_NAME) or 'https://api.openai.com/v1'
    anthropic_api_key = get_secret(ANTHROPIC_API_KEY_NAME)
    manus_api_key = get_secret(MANUS_API_KEY_NAME)
    admin_token = get_secret(PANEL_ADMIN_TOKEN_NAME) if is_authed else ''
    manus_key_available = bool(manus_api_key)
    webhook_url = cfg['public_base_url'].rstrip('/') + cfg['webhook_path']
    callback_url = cfg['public_base_url'].rstrip('/') + cfg['oauth_callback_path']
    session = load_json(META_SESSION_PATH, {})
    pages = session.get('pages', [])
    ad_accounts = session.get('ad_accounts', [])
    user = session.get('me', {})

    oauth_url = ''
    if cfg['app_id']:
        scopes = quote(cfg['default_scopes'])
        oauth_url = (
            f"https://www.facebook.com/{cfg['graph_api_version']}/dialog/oauth"
            f"?client_id={quote(cfg['app_id'])}"
            f"&redirect_uri={quote(callback_url, safe='')}"
            f"&scope={scopes}&response_type=code"
        )

    state = {
        'authed': is_authed,
        'cfg': {
            'public_base_url': cfg['public_base_url'],
            'app_id': cfg['app_id'],
            'graph_api_version': cfg['graph_api_version'],
            'default_scopes': cfg['default_scopes'],
            'linkedin_client_id': linkedin_client_id,
            'x_client_id': x_client_id,
            'ai_settings': cfg.get('ai_settings', {}),
        },
        'adminToken': admin_token,
        'manusKeyAvailable': manus_key_available,
        'webhookUrl': webhook_url,
        'callbackUrl': callback_url,
        'oauthUrl': oauth_url,
        'appSecretMasked': mask(app_secret),
        'verifyTokenMasked': mask(verify_token_val),
        'linkedinClientSecretMasked': mask(linkedin_client_secret),
        'xClientSecretMasked': mask(x_client_secret),
        'geminiApiKeyMasked': mask(gemini_api_key),
        'openaiApiKeyMasked': mask(openai_api_key),
        'openaiBaseUrl': openai_base_url,
        'anthropicApiKeyMasked': mask(anthropic_api_key),
        'manusApiKeyMasked': mask(manus_api_key),
        'pagesCount': len(pages),
        'adAccountsCount': len(ad_accounts),
        'connectedUser': user,
    }
    state_json = json.dumps(state, ensure_ascii=False)
    # Evita que "<" ou "</script>" dentro de strings JSON fechem a tag <script> no HTML (SyntaxError: Unexpected string)
    state_json = state_json.replace('<', '\\u003c')
    html = load_panel_template().replace('__PANEL_STATE_JSON__', state_json)
    return HTMLResponse(html)


def _serve_panel(panel_auth, panel_user):
    return index(panel_auth=panel_auth, panel_user=panel_user)


@app.get('/campanhas', response_class=HTMLResponse)
@app.get('/conteudo', response_class=HTMLResponse)
@app.get('/analise', response_class=HTMLResponse)
@app.get('/icp', response_class=HTMLResponse)
@app.get('/configuracoes', response_class=HTMLResponse)
@app.get('/admin', response_class=HTMLResponse)
@app.get('/agentes', response_class=HTMLResponse)
@app.get('/performance', response_class=HTMLResponse)
def panel_spa_route(panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    return _serve_panel(panel_auth, panel_user)


@app.post('/config/save')
def config_save(
    public_base_url: str = Form(...),
    app_id: str = Form(''),
    app_secret: str = Form(''),
    verify_token: str = Form(''),
    linkedin_client_id: str = Form(''),
    linkedin_client_secret: str = Form(''),
    x_client_id: str = Form(''),
    x_client_secret: str = Form(''),
    gemini_api_key: str = Form(''),
    openai_api_key: str = Form(''),
    openai_base_url: str = Form(''),
    anthropic_api_key: str = Form(''),
    manus_api_key: str = Form(''),
    graph_api_version: str = Form('v23.0'),
    default_scopes: str = Form(''),
):
    cfg = load_config()
    cfg['public_base_url'] = public_base_url.strip().rstrip('/')
    cfg['app_id'] = app_id.strip()
    cfg['graph_api_version'] = graph_api_version.strip() or 'v23.0'
    cfg['default_scopes'] = default_scopes.strip()
    cfg['linkedin_client_id'] = linkedin_client_id.strip()
    cfg['x_client_id'] = x_client_id.strip()
    save_config(cfg)

    secrets = load_secrets()
    if app_secret.strip():
        secrets[cfg['app_secret_name']] = app_secret.strip()
    if verify_token.strip():
        secrets[cfg['verify_token_name']] = verify_token.strip()
    if linkedin_client_secret.strip():
        secrets[LINKEDIN_CLIENT_SECRET_NAME] = linkedin_client_secret.strip()
    if x_client_secret.strip():
        secrets[X_CLIENT_SECRET_NAME] = x_client_secret.strip()
    if gemini_api_key.strip():
        secrets[GEMINI_API_KEY_NAME] = gemini_api_key.strip()
    if openai_api_key.strip():
        secrets[OPENAI_API_KEY_NAME] = openai_api_key.strip()
    if openai_base_url.strip():
        secrets[OPENAI_BASE_URL_NAME] = openai_base_url.strip().rstrip('/')
    if anthropic_api_key.strip():
        secrets[ANTHROPIC_API_KEY_NAME] = anthropic_api_key.strip()
    if manus_api_key.strip():
        secrets[MANUS_API_KEY_NAME] = manus_api_key.strip()
    save_json(SECRETS_PATH, secrets)
    return RedirectResponse('/', status_code=303)


# ── Config save JSON (for SPA panel) ──────────────────────────────────────────

@app.post('/config/save-json')
async def config_save_json(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    body = await request.json()
    cfg = load_config()
    for field in ['public_base_url', 'app_id', 'graph_api_version', 'default_scopes', 'linkedin_client_id', 'x_client_id']:
        if field in body and body[field]:
            cfg[field] = body[field].strip().rstrip('/') if field == 'public_base_url' else body[field].strip()
    if isinstance(body.get('ai_settings'), dict):
        cfg['ai_settings'] = _normalize_ai_settings(body.get('ai_settings'))
    if not cfg.get('graph_api_version'):
        cfg['graph_api_version'] = 'v23.0'
    save_config(cfg)
    secrets = load_secrets()
    if body.get('app_secret', '').strip():
        secrets[cfg['app_secret_name']] = body['app_secret'].strip()
    if body.get('verify_token', '').strip():
        secrets[cfg['verify_token_name']] = body['verify_token'].strip()
    if body.get('linkedin_client_secret', '').strip():
        secrets[LINKEDIN_CLIENT_SECRET_NAME] = body['linkedin_client_secret'].strip()
    if body.get('x_client_secret', '').strip():
        secrets[X_CLIENT_SECRET_NAME] = body['x_client_secret'].strip()
    if body.get('gemini_api_key', '').strip():
        secrets[GEMINI_API_KEY_NAME] = body['gemini_api_key'].strip()
    if body.get('openai_api_key', '').strip():
        secrets[OPENAI_API_KEY_NAME] = body['openai_api_key'].strip()
    if body.get('openai_base_url', '').strip():
        secrets[OPENAI_BASE_URL_NAME] = body['openai_base_url'].strip().rstrip('/')
    if body.get('anthropic_api_key', '').strip():
        secrets[ANTHROPIC_API_KEY_NAME] = body['anthropic_api_key'].strip()
    if body.get('freeimage_api_key', '').strip():
        secrets[FREEIMAGE_API_KEY_NAME] = body['freeimage_api_key'].strip()
    if body.get('cloudinary_cloud_name', '').strip():
        secrets[CLOUDINARY_CLOUD_NAME] = body['cloudinary_cloud_name'].strip()
    if body.get('cloudinary_api_key', '').strip():
        secrets[CLOUDINARY_API_KEY_NAME] = body['cloudinary_api_key'].strip()
    if body.get('cloudinary_api_secret', '').strip():
        secrets[CLOUDINARY_API_SECRET_NAME] = body['cloudinary_api_secret'].strip()
    if body.get('manus_api_key', '').strip():
        secrets[MANUS_API_KEY_NAME] = body['manus_api_key'].strip()
    save_json(SECRETS_PATH, secrets)
    return {'ok': True}


# ── Panel auth routes ─────────────────────────────────────────────────────────

@app.post('/panel/login')
async def panel_login(request: Request, response: Response):
    body = await request.json()
    email = (body.get('email', '') or '').strip().lower()
    password = body.get('password', '')
    if email and verify_user_password(email, password):
        session_token = _panel_session_token_for_email(email)
        response.set_cookie('panel_auth', session_token, httponly=True, samesite='lax', max_age=86400 * 30)
        response.set_cookie('panel_user', email, httponly=True, samesite='lax', max_age=86400 * 30)
        u = get_user_by_email(email)
        return {'ok': True, 'user': {'email': email, 'name': u.get('name', ''), 'role': u.get('role', 'user')}}
    admin_token = get_secret(PANEL_ADMIN_TOKEN_NAME)
    if not admin_token or password != admin_token:
        return JSONResponse({'ok': False, 'error': 'invalid_credentials'}, status_code=401)
    session_token = _panel_session_token()
    response.set_cookie('panel_auth', session_token, httponly=True, samesite='lax', max_age=86400 * 30)
    response.set_cookie('panel_user', 'legacy-admin', httponly=True, samesite='lax', max_age=86400 * 30)
    return {'ok': True, 'user': {'email': email or 'legacy-admin', 'role': 'admin'}}


@app.get('/panel/logout')
def panel_logout():
    response = RedirectResponse('/', status_code=302)
    response.delete_cookie('panel_auth', path='/')
    response.delete_cookie('panel_user', path='/')
    return response


# --- Compatibilidade com documentação (/auth/*, /studio/context, /scheduled/*) ---
@app.post('/auth/login')
async def auth_login_alias(request: Request, response: Response):
    return await panel_login(request, response)


@app.post('/auth/logout')
def auth_logout_alias():
    response = JSONResponse({'ok': True})
    response.delete_cookie('panel_auth', path='/')
    response.delete_cookie('panel_user', path='/')
    return response


@app.get('/auth/me')
def auth_me_alias(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    return panel_users_me(request, panel_auth, panel_user)


@app.get('/studio/context')
def studio_context_compat(request: Request, 
    date: str = '',
    panel_auth: Optional[str] = Cookie(default=None),
    panel_user: Optional[str] = Cookie(default=None),
):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not user:
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    meta_session = load_json(META_SESSION_PATH, {})
    pages = filter_pages_for_user(user, meta_session.get('pages', []))
    page_list = []
    for p in pages:
        ig = p.get('instagram_business_account') or {}
        page_list.append({
            'id': str(p.get('id')),
            'name': p.get('name'),
            'instagram': ig.get('username'),
        })
    return {
        'ok': True,
        'scheduled_date_hint': date or None,
        'pages': page_list,
        'companies': load_companies(),
    }


def _scheduled_posts_merged(page_ids_filter: Optional[set], include_graph: bool, include_local: bool):
    cfg = load_config()
    items = []
    if include_local:
        posts = load_scheduled_posts()
        for p in posts.values():
            pid = str(p.get('page_id', '') or '')
            if page_ids_filter is not None and pid and pid not in page_ids_filter:
                continue
            if page_ids_filter is not None and not pid:
                continue
            row = dict(p)
            row['source'] = 'local_queue'
            row['scheduled_publish_time'] = p.get('scheduled_at')
            items.append(row)
    if include_graph:
        for page in load_json(META_SESSION_PATH, {}).get('pages', []) or []:
            pid = str(page.get('id', ''))
            if page_ids_filter is not None and pid not in page_ids_filter:
                continue
            token = page.get('access_token', '')
            if not token:
                continue
            try:
                params = urllib.parse.urlencode({
                    'fields': 'id,message,scheduled_publish_time,created_time,permalink_url',
                    'access_token': token,
                    'limit': '80',
                })
                url = f"https://graph.facebook.com/{cfg['graph_api_version']}/{pid}/feed?{params}"
                data = graph_get(url)
                for row in data.get('data', []) or []:
                    st = row.get('scheduled_publish_time')
                    if not st:
                        continue
                    st_int = int(st) if str(st).isdigit() else 0
                    items.append({
                        'source': 'facebook_graph',
                        'page_id': pid,
                        'page_name': page.get('name'),
                        'post_id': row.get('id'),
                        'message': row.get('message'),
                        'scheduled_publish_time': st_int,
                        'created_time': row.get('created_time'),
                        'permalink_url': row.get('permalink_url'),
                    })
            except Exception as e:
                items.append({'source': 'facebook_graph', 'page_id': pid, 'error': str(e)})
    items.sort(key=lambda x: int(x.get('scheduled_publish_time') or x.get('scheduled_at') or 0))
    return items


@app.get('/scheduled/posts')
def scheduled_posts_compat(request: Request, 
    page_ids: str = '',
    include_graph: bool = True,
    include_local: bool = True,
    panel_auth: Optional[str] = Cookie(default=None),
    panel_user: Optional[str] = Cookie(default=None),
):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    want = None
    if page_ids.strip():
        want = {p.strip() for p in page_ids.split(',') if p.strip()}
    items = _scheduled_posts_merged(want, include_graph, include_local)
    return {'ok': True, 'filter': {'page_ids': list(want) if want is not None else 'all'}, 'count': len(items), 'items': items}


@app.post('/scheduled/posts')
async def scheduled_posts_add_compat(
    request: Request,
    panel_auth: Optional[str] = Cookie(default=None),
    panel_user: Optional[str] = Cookie(default=None),
):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    body = await request.json()
    channel = (body.get('channel') or 'instagram').lower()
    page_id = str(body.get('page_id', '') or '')
    scheduled_at = int(body.get('scheduled_at', 0) or body.get('scheduled_publish_time', 0) or 0)
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not page_id or not page_allowed_for_user(user, page_id):
        return JSONResponse({'ok': False, 'error': 'forbidden_or_missing_page'}, status_code=403)
    if channel == 'facebook':
        msg = (body.get('message') or '').strip()
        if not msg:
            return JSONResponse({'ok': False, 'error': 'missing_message'}, status_code=400)
        if not scheduled_at:
            return JSONResponse({'ok': False, 'error': 'missing_scheduled_at'}, status_code=400)
        cfg = load_config()
        try:
            result = create_page_post(cfg, page_id, msg, '', 'false', str(scheduled_at))
            return {'ok': True, 'result': result}
        except Exception as e:
            return JSONResponse({'ok': False, 'error': str(e)}, status_code=400)
    image_url = (body.get('image_url') or '').strip()
    caption = (body.get('caption') or body.get('message') or '').strip()
    if not scheduled_at:
        return JSONResponse({'ok': False, 'error': 'missing_scheduled_at'}, status_code=400)
    acc = get_instagram_account_by_username(page_id=page_id)
    if not acc:
        return JSONResponse({'ok': False, 'error': 'page_has_no_instagram'}, status_code=400)
    ig = acc.get('instagram_business_account') or {}
    ig_id = ig.get('id', '')
    token = acc.get('page_access_token', '')
    if not image_url:
        return JSONResponse({'ok': False, 'error': 'instagram_requires_image_url'}, status_code=400)
    entry = add_scheduled_post(
        ig_user_id=ig_id,
        page_name=acc.get('page_name', ''),
        access_token=token,
        image_url=image_url,
        caption=caption,
        scheduled_at=scheduled_at,
        page_id=page_id,
        ig_username=ig.get('username', ''),
    )
    return {'ok': True, 'item': entry}


@app.post('/panel/brand-profile/sync-meta')
async def panel_brand_profile_sync_meta(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    body = await request.json()
    page_id = str(body.get('page_id', '') or '')
    if not page_id:
        return JSONResponse({'ok': False, 'error': 'missing_page_id'}, status_code=400)
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not page_allowed_for_user(user, page_id):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    cfg = load_config()
    token = get_page_access_token(page_id)
    if not token:
        session = get_meta_session_for_panel_user(panel_user or '')
        for p in (session.get('pages') or []):
            if str((p or {}).get('id', '')) == str(page_id):
                token = (p or {}).get('access_token', '')
                break
    if not token:
        return JSONResponse({'ok': False, 'error': 'no_token'}, status_code=400)
    updates = {}
    try:
        params = urllib.parse.urlencode({'fields': 'picture.type(large),name,fan_count,about', 'access_token': token})
        url = f"https://graph.facebook.com/{cfg['graph_api_version']}/{page_id}?{params}"
        data = graph_get(url)
        picture_url = ((data.get('picture') or {}).get('data') or {}).get('url', '')
        updates['facebook_page_name'] = data.get('name', '')
        updates['facebook_picture_url'] = picture_url
    except Exception as e:
        updates['facebook_sync_error'] = str(e)
    target = get_instagram_account_by_username(page_id=page_id)
    if not target:
        session = get_meta_session_for_panel_user(panel_user or '')
        for p in (session.get('pages') or []):
            if str((p or {}).get('id', '')) == str(page_id):
                ig = (p or {}).get('instagram_business_account') or {}
                if ig:
                    target = {
                        'page_id': str((p or {}).get('id', '')),
                        'page_name': (p or {}).get('name', ''),
                        'page_access_token': (p or {}).get('access_token', ''),
                        'instagram_business_account': ig,
                    }
                    break
    if target:
        ig = target.get('instagram_business_account') or {}
        ig_id = ig.get('id', '')
        ptok = target.get('page_access_token', '')
        if ig_id and ptok:
            try:
                params = urllib.parse.urlencode({
                    'fields': 'profile_picture_url,username,name,biography,followers_count',
                    'access_token': ptok,
                })
                url = f"https://graph.facebook.com/{cfg['graph_api_version']}/{ig_id}?{params}"
                igd = graph_get(url)
                un = igd.get('username', '')
                updates['instagram_username'] = un
                updates['instagram_handle'] = f'@{un}' if un else ''
                updates['instagram_profile_picture_url'] = igd.get('profile_picture_url', '')
                updates['instagram_biography'] = igd.get('biography', '')
                updates['instagram_followers_count'] = igd.get('followers_count')
                updates['instagram_name'] = igd.get('name', '')
                store_profile_followers_snapshot(ig_id or un or page_id, igd.get('followers_count', 0), un, page_id)
            except Exception as e:
                updates['instagram_sync_error'] = str(e)
    profile = upsert_brand_profile(page_id, updates)
    return {'ok': True, 'profile': profile}


@app.get('/panel/users/me')
def panel_users_me(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    user = get_user_by_email((panel_user or '').strip().lower()) if panel_user and panel_user != 'legacy-admin' else {'email': 'legacy-admin', 'role': 'admin', 'allowed_page_ids': []}
    return {
        'ok': True,
        'user': {
            'email': user.get('email', ''),
            'name': user.get('name', ''),
            'role': user.get('role', 'user'),
            'username': user.get('username', ''),
            'allowed_page_ids': user.get('allowed_page_ids', []),
            'meta_connection_enabled': user.get('meta_connection_enabled', True),
        },
    }


@app.get('/panel/system-error-logs')
def panel_system_error_logs(request: Request, limit: int = 200, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not user or not is_admin_user(user):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    return {
        'ok': True,
        'log_path': str(SYSTEM_ERRORS_LOG_PATH),
        'items': read_system_error_logs(limit=limit),
    }


@app.post('/panel/system-error-logs/clear')
async def panel_system_error_logs_clear(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not user or not is_admin_user(user):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    clear_system_error_logs()
    append_system_error_log('system_action', 'Error log cleared', user=user.get('email', ''))
    return {'ok': True}


@app.get('/panel/pages')
def panel_pages(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    user = current_panel_user(panel_auth or '', panel_user or '', request=request) or {'email': 'legacy-admin', 'role': 'admin'}
    if is_admin_user(user):
        sessions = load_meta_user_sessions()
        own_pages = get_shareable_pages_from_admin()
        user_pages = []
        for email, sess in (sessions or {}).items():
            for p in (sess.get('pages', []) if isinstance(sess, dict) else []):
                user_pages.append({**p, '_owner_email': email})
        pages = merge_pages_unique(own_pages, user_pages)
        return {'ok': True, 'pages': pages}
    own_session = get_meta_session_for_panel_user(panel_user or '')
    own_pages = own_session.get('pages', []) if isinstance(own_session, dict) else []
    shared_pages = filter_pages_for_user(user, get_shareable_pages_from_admin())
    pages = merge_pages_unique(own_pages, shared_pages)
    return {'ok': True, 'pages': pages}



@app.get('/panel/users')
def panel_users(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not user:
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    if not is_admin_user(user):
        safe = dict(user)
        safe.pop('password_hash', None)
        safe.pop('salt', None)
        return {'ok': True, 'users': [safe]}
    users = load_users()
    safe = []
    for u in users.values():
        row = dict(u)
        row.pop('password_hash', None)
        row.pop('salt', None)
        row['allowed_ad_account_ids'] = [normalize_ad_account_id(str(x)) for x in (row.get('allowed_ad_account_ids') or []) if normalize_ad_account_id(str(x))]
        safe.append(row)
    return {'ok': True, 'users': safe}


@app.post('/panel/users/upsert')
async def panel_users_upsert(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    actor = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not actor or not is_admin_user(actor):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    body = await request.json()
    email = (body.get('email', '') or '').strip().lower()
    if not email:
        return JSONResponse({'ok': False, 'error': 'missing_email'}, status_code=400)
    users = load_users()
    existing = users.get(email) or {'email': email, 'created_at': int(time.time()), 'api_key_ids': []}
    existing['name'] = (body.get('name', '') or existing.get('name') or email).strip()
    existing['role'] = 'admin' if (body.get('role', '') == 'admin') else 'user'
    existing['allowed_page_ids'] = [str(x) for x in (body.get('allowed_page_ids') or []) if str(x).strip()]
    existing['allowed_ad_account_ids'] = [normalize_ad_account_id(str(x)) for x in (body.get('allowed_ad_account_ids') or []) if normalize_ad_account_id(str(x))]
    existing['meta_connection_enabled'] = bool(body.get('meta_connection_enabled', existing.get('meta_connection_enabled', True)))
    password = (body.get('password', '') or '').strip()
    if password:
        salt = existing.get('salt') or hashlib.sha256(f'{time.time()}|{email}'.encode()).hexdigest()[:16]
        existing['salt'] = salt
        existing['password_hash'] = _hash_password(password, salt)
    elif not existing.get('password_hash'):
        return JSONResponse({'ok': False, 'error': 'missing_password_for_new_user'}, status_code=400)
    existing['updated_at'] = int(time.time())
    users[email] = existing
    save_users(users)
    safe = dict(existing)
    safe.pop('password_hash', None)
    safe.pop('salt', None)
    return {'ok': True, 'user': safe}


@app.get('/panel/ad-accounts')
def panel_ad_accounts(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    user = current_panel_user(panel_auth or '', panel_user or '', request=request) or {'email': 'legacy-admin', 'role': 'admin'}
    if is_admin_user(user):
        sessions = load_meta_user_sessions()
        own_accounts = get_shareable_ad_accounts_from_admin()
        user_accounts = []
        for email, sess in (sessions or {}).items():
            for acct in (sess.get('ad_accounts', []) if isinstance(sess, dict) else []):
                user_accounts.append({**acct, '_owner_email': email})
        accounts = merge_ad_accounts_unique(own_accounts, user_accounts)
        return {'ok': True, 'ad_accounts': accounts}
    shared_accounts = get_shareable_ad_accounts_from_admin()
    allowed = set(get_allowed_ad_account_ids_for_user(user))
    accounts = [acct for acct in merge_ad_accounts_unique(shared_accounts) if str(acct.get('id') or '') in allowed]
    return {'ok': True, 'ad_accounts': accounts}


@app.post('/panel/users/delete')
async def panel_users_delete(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    actor = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not actor or not is_admin_user(actor):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    body = await request.json()
    email = (body.get('email', '') or '').strip().lower()
    users = load_users()
    if email not in users:
        return JSONResponse({'ok': False, 'error': 'not_found'}, status_code=404)
    if email == 'luispessoa18@gmail.com':
        return JSONResponse({'ok': False, 'error': 'cannot_delete_default_admin'}, status_code=400)
    users.pop(email, None)
    save_users(users)
    return {'ok': True}


@app.get('/panel/api-keys')
def panel_api_keys(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    email = (panel_user or '').strip().lower()
    api_keys = load_api_keys()
    items = [v for v in api_keys.values() if email in ['', 'legacy-admin'] or v.get('user_email') == email]
    return {'ok': True, 'api_keys': items}


@app.post('/panel/api-keys/create')
async def panel_api_keys_create(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    body = await request.json()
    email = ((panel_user or '').strip().lower() or 'luispessoa18@gmail.com')
    label = (body.get('label', '') or 'Generated key').strip()
    raw_key = _new_token('mpk')
    key_id = hashlib.sha256(raw_key.encode()).hexdigest()[:16]
    api_keys = load_api_keys()
    api_keys[key_id] = {
        'id': key_id,
        'label': label,
        'user_email': email,
        'key_hash': hashlib.sha256(raw_key.encode()).hexdigest(),
        'created_at': int(time.time()),
        'revoked': False,
        'last_used_at': 0,
    }
    save_api_keys(api_keys)
    users = load_users()
    if email in users:
        users[email].setdefault('api_key_ids', []).append(key_id)
        users[email]['updated_at'] = int(time.time())
        save_users(users)
    return {'ok': True, 'api_key': raw_key, 'meta': api_keys[key_id]}


@app.post('/panel/api-keys/revoke')
async def panel_api_keys_revoke(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    body = await request.json()
    key_id = (body.get('key_id', '') or '').strip()
    api_keys = load_api_keys()
    meta = api_keys.get(key_id)
    if not meta:
        return JSONResponse({'ok': False, 'error': 'not_found'}, status_code=404)
    meta['revoked'] = True
    meta['revoked_at'] = int(time.time())
    api_keys[key_id] = meta
    save_api_keys(api_keys)
    return {'ok': True, 'meta': meta}


@app.get('/panel/api-keys/usage')
def panel_api_keys_usage(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None), limit: int = 100):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    email = (panel_user or '').strip().lower()
    rows = []
    if API_KEY_USAGE_PATH.exists():
        for line in API_KEY_USAGE_PATH.read_text().splitlines()[-limit:]:
            try:
                row = json.loads(line)
                if email in ['', 'legacy-admin'] or row.get('user_email') == email:
                    rows.append(row)
            except Exception:
                pass
    return {'ok': True, 'usage': rows}


@app.get('/panel/ai/usage-summary')
def panel_ai_usage_summary(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None), page_id: str = '', limit: int = 1000):
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not user:
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    rows = read_ai_usage_log(limit=limit)
    if page_id:
        rows = [r for r in rows if str(r.get('page_id', '')) == str(page_id)]
    elif not is_admin_user(user):
        allowed = set(get_allowed_page_ids_for_user(user))
        rows = [r for r in rows if not r.get('page_id') or str(r.get('page_id', '')) in allowed]
    by_provider = {}
    by_operation = {}
    by_post = {}
    total_cost = 0.0
    total_tokens = 0
    for row in rows:
        provider = row.get('provider') or 'unknown'
        operation = row.get('operation') or 'unknown'
        post_key = row.get('post_id') or ''
        cost = float(row.get('cost_usd') or 0.0)
        tokens = int(row.get('total_tokens') or 0)
        total_cost += cost
        total_tokens += tokens
        for bucket, key in ((by_provider, provider), (by_operation, operation)):
            if key not in bucket:
                bucket[key] = {'count': 0, 'cost_usd': 0.0, 'tokens': 0}
            bucket[key]['count'] += 1
            bucket[key]['cost_usd'] += cost
            bucket[key]['tokens'] += tokens
        if post_key:
            if post_key not in by_post:
                by_post[post_key] = {'count': 0, 'cost_usd': 0.0, 'tokens': 0, 'operations': []}
            by_post[post_key]['count'] += 1
            by_post[post_key]['cost_usd'] += cost
            by_post[post_key]['tokens'] += tokens
            by_post[post_key]['operations'].append(operation)
    return {
        'ok': True,
        'summary': {
            'entries': len(rows),
            'total_cost_usd': round(total_cost, 6),
            'total_tokens': total_tokens,
        },
        'by_provider': by_provider,
        'by_operation': by_operation,
        'by_post': by_post,
        'recent': list(reversed(rows[-50:])),
    }


@app.get('/panel/ai/models')
def panel_ai_models(request: Request, provider: str = 'openai', panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not user or not is_admin_user(user):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    provider = (provider or 'openai').strip().lower()
    try:
        if provider == 'openai':
            api_key = _openai_api_key()
            if not api_key:
                return JSONResponse({'ok': False, 'error': 'openai_not_configured'}, status_code=400)
            models = _fetch_openai_models(api_key)
            text_models = [m for m in models if m.startswith('gpt-') or m.startswith('o')]
            image_models = [m for m in models if m in OPENAI_IMAGE_MODELS or m.startswith('gpt-image-')]
            return {'ok': True, 'provider': provider, 'models': models, 'text_models': text_models, 'image_models': sorted(set(image_models) | OPENAI_IMAGE_MODELS)}
        if provider == 'gemini':
            api_key = get_secret(GEMINI_API_KEY_NAME) or get_secret('GOOGLE_API_KEY')
            if not api_key:
                return JSONResponse({'ok': False, 'error': 'gemini_not_configured'}, status_code=400)
            models = _fetch_gemini_models(api_key)
            return {'ok': True, 'provider': provider, 'models': models, 'text_models': models, 'image_models': []}
        if provider == 'claude':
            api_key = _anthropic_api_key()
            if not api_key:
                return JSONResponse({'ok': False, 'error': 'anthropic_not_configured'}, status_code=400)
            models = _fetch_claude_models(api_key)
            return {'ok': True, 'provider': provider, 'models': models, 'text_models': models, 'image_models': []}
        return JSONResponse({'ok': False, 'error': 'unsupported_provider'}, status_code=400)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'ai_models_failed', 'detail': str(e)}, status_code=400)


@app.get('/panel/openai/models')
def panel_openai_models_compat(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    return panel_ai_models(request, provider='openai', panel_auth=panel_auth, panel_user=panel_user)


# ── Panel data routes ─────────────────────────────────────────────────────────

@app.get('/panel/companies')
def panel_companies(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not user:
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    return {'ok': True, 'companies': filter_companies_for_user(user, load_companies())}


@app.post('/panel/companies/upsert')
async def panel_companies_upsert(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not user:
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    body = await request.json()
    company_id = (body.get('id', '') or body.get('company_id', '') or '').strip()
    name = (body.get('name', '') or '').strip()
    if not company_id:
        company_id = _slugify(name) or hashlib.sha256((name or str(time.time())).encode()).hexdigest()[:10]
    companies = load_companies()
    existing = companies.get(company_id) or {'id': company_id, 'created_at': int(time.time())}
    existing['name'] = name or existing.get('name', company_id)
    existing['slug'] = _slugify(existing['name'])
    existing['updated_at'] = int(time.time())
    existing.setdefault('bindings', {'meta': {'page_id': '', 'instagram': {'ig_user_id': '', 'username': ''}}, 'linkedin': {'author_urn': '', 'org_urn': ''}, 'x': {'username': '', 'user_id': ''}})
    # allow bindings updates (deep merge per platform so partial updates don't wipe existing fields)
    for plat in ['meta', 'linkedin', 'x']:
        if plat in body:
            existing['bindings'][plat] = body.get(plat) or existing['bindings'].get(plat)
    if 'bindings' in body and isinstance(body.get('bindings'), dict):
        for plat, val in body['bindings'].items():
            if isinstance(val, dict) and isinstance(existing['bindings'].get(plat), dict):
                existing['bindings'][plat].update(val)
            else:
                existing['bindings'][plat] = val
    target_page_id = str((((existing.get('bindings') or {}).get('meta') or {}).get('page_id') or body.get('page_id') or '')).strip()
    if target_page_id and not page_allowed_for_user(user, target_page_id):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    companies[company_id] = existing
    save_companies(companies)
    return {'ok': True, 'company': existing}


@app.get('/panel/company-dashboard')
def panel_company_dashboard(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not user:
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    data = build_company_dashboard_status(panel_user or '')
    if not is_admin_user(user):
        allowed = set(get_allowed_page_ids_for_user(user))
        data['companies'] = [c for c in (data.get('companies') or []) if str(c.get('page_id', '')) in allowed]
        data['summary']['companies_count'] = len(data['companies'])
    data['manus_key_available'] = bool(get_secret(MANUS_API_KEY_NAME))
    return data


@app.get('/panel/brand-profiles')
def panel_brand_profiles(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not user:
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    return {'ok': True, 'profiles': filter_brand_profiles_for_user(user, load_brand_profiles()), 'manus_key_available': bool(get_secret(MANUS_API_KEY_NAME))}


@app.post('/panel/brand-profile/save')
async def panel_brand_profile_save(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    body = await request.json()
    page_id = body.get('page_id', '')
    if not page_id:
        return JSONResponse({'ok': False, 'error': 'missing_page_id'}, status_code=400)
    allowed = ['page_name', 'brand_name', 'tagline', 'description', 'tone', 'target_audience',
               'key_products', 'visual_style', 'colors', 'nano_banana_style_prompt',
               'cta_style', 'best_offer', 'competitors', 'instagram_handle', 'facebook_url',
               'linkedin_handle', 'x_handle', 'art_direction', 'logo_url', 'logo_path',
               'reference_image_url', 'reference_image_path', 'font_preference', 'preferred_aspect_ratio',
               'text_rule', 'negative_rules', 'visual_references', 'palette_source',
               'use_reference_style', 'reference_style_prompt', 'icp_onboarding_text',
               'icp_compare_notes', 'icp_adjustment_notes', 'icp_analysis', 'icp_analysis_history']
    updates = {k: v for k, v in body.items() if k in allowed}
    if 'icp_analysis' in updates and _icp_analysis_update_is_empty(updates.get('icp_analysis')):
        updates.pop('icp_analysis', None)
    profile = upsert_brand_profile(page_id, updates)
    return {'ok': True, 'profile': profile}


@app.post('/panel/brand-profile/upload-logo')
async def panel_brand_profile_upload_logo(request: Request,
    page_id: str = Form(...),
    file: UploadFile = File(...),
    variant: str = Form(default='dark'),
    panel_auth: Optional[str] = Cookie(default=None),
    panel_user: Optional[str] = Cookie(default=None),
):
    """
    Upload a logo version.
    variant='dark'  → logo para fundos claros (versão escura/preta da logo)
    variant='light' → logo para fundos escuros (versão clara/branca da logo)
    """
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if page_id and user and not page_allowed_for_user(user, str(page_id)):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    ext = Path(file.filename or '').suffix.lower() or '.png'
    if ext not in ['.png', '.jpg', '.jpeg', '.webp', '.svg']:
        return JSONResponse({'ok': False, 'error': 'invalid_file_type'}, status_code=400)
    variant = 'light' if str(variant or '').strip().lower() == 'light' else 'dark'
    suffix = f'_light' if variant == 'light' else ''
    dest = UPLOADS_DIR / f"logo_{page_id}{suffix}{ext}"
    content = await file.read()
    dest.write_bytes(content)
    cfg = load_config()
    logo_url = cfg['public_base_url'].rstrip('/') + f'/uploads/logo_{page_id}{suffix}{ext}'
    palette = extract_palette_from_image(str(dest), max_colors=6) if ext != '.svg' else []
    updates: dict = {}
    if variant == 'light':
        updates = {'logo_light_url': logo_url, 'logo_light_path': str(dest)}
    else:
        updates = {'logo_url': logo_url, 'logo_path': str(dest), 'colors': palette or [],
                   'art_direction': {'logo_url': logo_url, 'colors': palette or []}}
    profile = upsert_brand_profile(page_id, updates)
    return {'ok': True, 'logo_url': logo_url, 'variant': variant, 'palette': palette if variant == 'dark' else [], 'profile': profile}


@app.post('/panel/brand-profile/use-instagram-logo')
async def panel_brand_profile_use_instagram_logo(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    body = await request.json()
    page_id = str(body.get('page_id', '') or '')
    if not page_id:
        return JSONResponse({'ok': False, 'error': 'missing_page_id'}, status_code=400)
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if user and not page_allowed_for_user(user, str(page_id)):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    profile = get_brand_profile(page_id)
    ig_pic_url = profile.get('instagram_profile_picture_url', '')
    if not ig_pic_url:
        return JSONResponse({'ok': False, 'error': 'instagram_picture_not_found'}, status_code=404)
    try:
        req = urllib.request.Request(ig_pic_url, headers={'User-Agent': 'meta-connection-panel/1.0'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read()
    except Exception as e:
        return JSONResponse({'ok': False, 'error': f'download_failed: {e}'}, status_code=400)
    dest = UPLOADS_DIR / f'logo_{page_id}.jpg'
    dest.write_bytes(content)
    cfg = load_config()
    logo_url = cfg['public_base_url'].rstrip('/') + f'/uploads/logo_{page_id}.jpg'
    palette = extract_palette_from_image(str(dest), max_colors=6)
    updates = {'logo_url': logo_url, 'logo_path': str(dest)}
    if palette:
        updates['colors'] = palette
        updates['art_direction'] = {'logo_url': logo_url, 'colors': palette}
    saved = upsert_brand_profile(page_id, updates)
    return {'ok': True, 'logo_url': logo_url, 'palette': palette, 'profile': saved}


@app.post('/panel/brand-profile/upload-reference')
async def panel_brand_profile_upload_reference(request: Request, 
    page_id: str = Form(...),
    file: UploadFile = File(...),
    panel_auth: Optional[str] = Cookie(default=None),
    panel_user: Optional[str] = Cookie(default=None),
):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if page_id and user and not page_allowed_for_user(user, str(page_id)):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    ext = Path(file.filename or '').suffix.lower() or '.jpg'
    if ext not in ['.png', '.jpg', '.jpeg', '.webp']:
        return JSONResponse({'ok': False, 'error': 'invalid_file_type'}, status_code=400)
    dest = UPLOADS_DIR / f"reference_{page_id}{ext}"
    content = await file.read()
    dest.write_bytes(content)
    cfg = load_config()
    ref_url = cfg['public_base_url'].rstrip('/') + f'/uploads/reference_{page_id}{ext}'
    palette = extract_palette_from_image(str(dest), max_colors=6)
    profile = get_brand_profile(page_id)
    existing_refs = profile.get('visual_references') if isinstance(profile.get('visual_references'), list) else []
    normalized_refs = []
    for ref in existing_refs:
        if isinstance(ref, dict):
            normalized_refs.append(ref)
        elif isinstance(ref, str) and ref:
            normalized_refs.append({'id': hashlib.sha256(ref.encode('utf-8')).hexdigest()[:12], 'url': ref, 'label': 'referência', 'kind': 'brand_reference', 'use_for_style': True})
    main_ref = {
        'id': 'main-reference',
        'url': ref_url,
        'path': str(dest),
        'filename': file.filename or dest.name,
        'label': 'Arte principal',
        'kind': 'brand_reference',
        'use_for_style': True,
        'created_at': int(time.time()),
    }
    normalized_refs = [r for r in normalized_refs if str((r or {}).get('id', '')) != 'main-reference']
    normalized_refs.insert(0, main_ref)
    art_direction = profile.get('art_direction') if isinstance(profile.get('art_direction'), dict) else {}
    art_direction.update({'reference_image_url': ref_url, 'references': [r.get('url', '') for r in normalized_refs if isinstance(r, dict) and r.get('use_for_style')], 'colors': palette or art_direction.get('colors', [])})
    profile = upsert_brand_profile(page_id, {'reference_image_url': ref_url, 'reference_image_path': str(dest), 'visual_references': normalized_refs, 'art_direction': art_direction})
    return {'ok': True, 'reference_image_url': ref_url, 'palette': palette, 'profile': profile}


@app.post('/panel/brand-profile/upload-visual-reference')
async def panel_brand_profile_upload_visual_reference(
    request: Request,
    page_id: str = Form(...),
    kind: str = Form('brand_reference'),
    files: list[UploadFile] = File(...),
    panel_auth: Optional[str] = Cookie(default=None),
    panel_user: Optional[str] = Cookie(default=None),
):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if page_id and user and not page_allowed_for_user(user, str(page_id)):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    cfg = load_config()
    profile = get_brand_profile(page_id)
    existing_refs = profile.get('visual_references') if isinstance(profile.get('visual_references'), list) else []
    normalized_refs = []
    for ref in existing_refs:
        if isinstance(ref, dict):
            normalized_refs.append(ref)
        elif isinstance(ref, str) and ref:
            normalized_refs.append({'id': hashlib.sha256(ref.encode('utf-8')).hexdigest()[:12], 'url': ref, 'label': 'referência', 'kind': 'brand_reference', 'use_for_style': True})
    added = []
    for idx, file in enumerate(files or []):
        ext = Path(file.filename or '').suffix.lower() or '.jpg'
        if ext not in ['.png', '.jpg', '.jpeg', '.webp']:
            continue
        ref_id = hashlib.sha256(f"{page_id}-{kind}-{file.filename}-{time.time()}-{idx}".encode('utf-8')).hexdigest()[:12]
        dest = UPLOADS_DIR / f"visual_ref_{page_id}_{ref_id}{ext}"
        content = await file.read()
        dest.write_bytes(content)
        ref_url = cfg['public_base_url'].rstrip('/') + f'/uploads/{dest.name}'
        item = {
            'id': ref_id,
            'url': ref_url,
            'path': str(dest),
            'filename': file.filename or dest.name,
            'label': Path(file.filename or f'referencia-{idx+1}').stem,
            'kind': kind,
            'use_for_style': True,
            'created_at': int(time.time()),
        }
        normalized_refs.append(item)
        added.append(item)
    art_direction = profile.get('art_direction') if isinstance(profile.get('art_direction'), dict) else {}
    art_direction['references'] = [r.get('url', '') for r in normalized_refs if isinstance(r, dict) and r.get('use_for_style')]
    profile = upsert_brand_profile(page_id, {'visual_references': normalized_refs, 'art_direction': art_direction})
    return {'ok': True, 'references': added, 'profile': profile}


def _call_openai_visual_reference_summary(image_urls: list[str], api_key: str, model: str = 'gpt-5.2') -> tuple[str, dict]:
    base = (_openai_base_url() or 'https://api.openai.com/v1').rstrip('/')
    content = [{
        'type': 'input_text',
        'text': (
            'Analise estas referências visuais para marketing de Instagram. '
            'Responda SOMENTE com JSON válido contendo: '
            '"style_prompt", "visual_style", "font_preference", "color_palette", "composition_rules", "negative_rules". '
            'O campo style_prompt deve ser um parágrafo em português com instruções práticas para geração de imagem. '
            'Se houver semelhança entre as referências, sintetize o padrão. '
            'Nao invente nome de fonte específica se não der para inferir; descreva a tipografia.'
        )
    }]
    for url in image_urls[:6]:
        if url:
            content.append({'type': 'input_image', 'image_url': url})
    payload = {
        'model': model,
        'input': [{'role': 'user', 'content': content}],
        'text': {'format': {'type': 'json_object'}},
    }
    req = urllib.request.Request(
        f'{base}/responses',
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read().decode('utf-8', 'ignore')
        data = json.loads(raw)
    text = _extract_openai_responses_text(data)
    usage = _extract_usage_from_openai_responses(data)
    return text, usage


@app.post('/panel/brand-profile/analyze-visual-references')
async def panel_brand_profile_analyze_visual_references(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    body = await request.json()
    page_id = str(body.get('page_id', '') or '')
    if not page_id:
        return JSONResponse({'ok': False, 'error': 'missing_page_id'}, status_code=400)
    if user and not page_allowed_for_user(user, str(page_id)):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    profile = get_brand_profile(page_id)
    refs = profile.get('visual_references') if isinstance(profile.get('visual_references'), list) else []
    enabled_refs = [r for r in refs if isinstance(r, dict) and r.get('use_for_style')]
    image_urls = [str(r.get('url', '') or '') for r in enabled_refs if str(r.get('url', '') or '')]
    if profile.get('reference_image_url'):
        image_urls.insert(0, str(profile.get('reference_image_url')))
    deduped = []
    for url in image_urls:
        if url and url not in deduped:
            deduped.append(url)
    if not deduped:
        return JSONResponse({'ok': False, 'error': 'no_visual_references'}, status_code=400)
    api_key = _openai_api_key()
    if not api_key:
        return JSONResponse({'ok': False, 'error': 'openai_not_configured'}, status_code=400)
    try:
        text, usage = _call_openai_visual_reference_summary(deduped, api_key, model='gpt-5.2')
        parsed = _extract_json_block(text or '')
        if not isinstance(parsed, dict):
            raise ValueError('invalid_visual_reference_analysis')
        colors = parsed.get('color_palette') if isinstance(parsed.get('color_palette'), list) else []
        style_prompt = str(parsed.get('style_prompt', '') or '').strip()
        art_direction = profile.get('art_direction') if isinstance(profile.get('art_direction'), dict) else {}
        art_direction.update({
            'visual_style': parsed.get('visual_style') or profile.get('visual_style', ''),
            'font_preference': parsed.get('font_preference') or profile.get('font_preference', ''),
            'composition_rules': parsed.get('composition_rules') or '',
            'negative_rules': parsed.get('negative_rules') or profile.get('negative_rules', ''),
            'references': deduped[:6],
            'style_prompt': style_prompt,
        })
        saved = upsert_brand_profile(page_id, {
            'visual_style': parsed.get('visual_style') or profile.get('visual_style', ''),
            'font_preference': parsed.get('font_preference') or profile.get('font_preference', ''),
            'reference_style_prompt': style_prompt,
            'use_reference_style': True,
            'colors': colors or profile.get('colors', []),
            'negative_rules': parsed.get('negative_rules') or profile.get('negative_rules', ''),
            'art_direction': art_direction,
        })
        log_ai_usage('brand_analysis', 'openai', 'gpt-5.2', usage, _calculate_ai_cost('openai', 'gpt-5.2', usage), page_id=page_id, item_type='visual_reference_analysis')
        return {'ok': True, 'analysis': parsed, 'profile': saved}
    except Exception as e:
        append_system_error_log('visual_reference_analysis_failed', {
            'page_id': page_id,
            'detail': str(e),
            'reference_urls': deduped[:6],
        })
        return JSONResponse({'ok': False, 'error': 'visual_reference_analysis_failed', 'detail': str(e)}, status_code=400)


@app.post('/panel/brand-profile/extract-palette')
async def panel_brand_profile_extract_palette(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    body = await request.json()
    page_id = str(body.get('page_id', '') or '')
    source = str(body.get('source', 'logo') or 'logo')
    reference_id = str(body.get('reference_id', '') or '')
    if not page_id:
        return JSONResponse({'ok': False, 'error': 'missing_page_id'}, status_code=400)
    profile = get_brand_profile(page_id)
    palette = []
    if source == 'logo':
        path = profile.get('logo_path', '')
        if path and Path(path).exists():
            palette = extract_palette_from_image(path, max_colors=6)
    elif source == 'reference':
        path = profile.get('reference_image_path', '')
        if path and Path(path).exists():
            palette = extract_palette_from_image(path, max_colors=6)
    elif source == 'instagram_profile':
        palette = extract_palette_from_url(profile.get('instagram_profile_picture_url', ''), max_colors=6)
    elif source == 'facebook_profile':
        palette = extract_palette_from_url(profile.get('facebook_picture_url', ''), max_colors=6)
    elif source == 'visual_reference':
        refs = profile.get('visual_references') if isinstance(profile.get('visual_references'), list) else []
        match = next((r for r in refs if str((r or {}).get('id', '')) == reference_id), None)
        if match:
            path = str((match or {}).get('path', '') or '')
            if path and Path(path).exists():
                palette = extract_palette_from_image(path, max_colors=6)
            else:
                palette = extract_palette_from_url(str((match or {}).get('url', '') or ''), max_colors=6)
    if not palette:
        return JSONResponse({'ok': False, 'error': 'source_image_not_found'}, status_code=404)
    profile = upsert_brand_profile(page_id, {'colors': palette or profile.get('colors', []), 'palette_source': source})
    return {'ok': True, 'palette': palette, 'profile': profile}


@app.get('/panel/page-picture')
def panel_page_picture(request: Request, page_id: str = '', panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not page_id:
        return JSONResponse({'ok': False, 'error': 'missing_page_id'}, status_code=400)
    if user and not page_allowed_for_user(user, str(page_id)):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    cfg = load_config()
    token = get_page_access_token(page_id)
    if not token:
        session = get_meta_session_for_panel_user(panel_user or '')
        token = ((session.get('token') or {}).get('access_token')) or get_meta_access_token()
    if not token:
        return JSONResponse({'ok': False, 'error': 'no_token'}, status_code=400)
    try:
        params = urllib.parse.urlencode({'fields': 'picture.type(large),name,fan_count,about,website,phone', 'access_token': token})
        url = f"https://graph.facebook.com/{cfg['graph_api_version']}/{page_id}?{params}"
        data = graph_get(url)
        picture_url = ((data.get('picture') or {}).get('data') or {}).get('url', '')
        return {'ok': True, 'page_id': page_id, 'name': data.get('name', ''),
                'picture_url': picture_url, 'fan_count': data.get('fan_count', 0), 'about': data.get('about', ''),
                'website': data.get('website', ''), 'phone': data.get('phone', '')}
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=400)


@app.get('/panel/instagram-picture')
def panel_instagram_picture(request: Request, ig_user_id: str = '', username: str = '', page_id: str = '', panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if page_id and user and not page_allowed_for_user(user, str(page_id)):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    cfg = load_config()
    target = get_instagram_account_by_username(username=username, ig_user_id=ig_user_id, page_id=page_id)
    if not target and page_id:
        session = get_meta_session_for_panel_user(panel_user or '')
        for p in (session.get('pages') or []):
            if str((p or {}).get('id', '')) == str(page_id):
                ig = (p or {}).get('instagram_business_account') or {}
                if ig and (not ig_user_id or str(ig.get('id', '')) == str(ig_user_id)):
                    target = {
                        'page_id': str((p or {}).get('id', '')),
                        'page_name': (p or {}).get('name', ''),
                        'page_access_token': (p or {}).get('access_token', ''),
                        'instagram_business_account': ig,
                    }
                    break
    if not target:
        return JSONResponse({'ok': False, 'error': 'not_found'}, status_code=404)
    ig = target.get('instagram_business_account', {})
    token = target.get('page_access_token', '')
    ig_id = ig.get('id', '')
    if not ig_id or not token:
        return JSONResponse({'ok': False, 'error': 'missing_ig_data'}, status_code=400)
    try:
        params = urllib.parse.urlencode({'fields': 'profile_picture_url,username,name,biography,followers_count,media_count,website', 'access_token': token})
        url = f"https://graph.facebook.com/{cfg['graph_api_version']}/{ig_id}?{params}"
        data = graph_get(url)
        profile_key = ig_id or data.get('username', '') or page_id or username
        store_profile_followers_snapshot(profile_key, data.get('followers_count', 0), data.get('username', ''), page_id)
        growth = followers_growth_summary(profile_key, data.get('followers_count', 0))
        return {'ok': True, **data, 'growth': growth}
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=400)


@app.get('/panel/insights/overview')
def panel_insights_overview(request: Request, page_id: str = '', panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not user:
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    if not page_id:
        return JSONResponse({'ok': False, 'error': 'missing_page_id'}, status_code=400)
    if not page_allowed_for_user(user, str(page_id)):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    cfg = load_config()
    try:
        context = collect_brand_meta_context(cfg, page_id, panel_user or '')
        return {'ok': True, 'page_id': page_id, 'context': context}
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'insights_overview_failed', 'detail': str(e)}, status_code=400)


@app.post('/panel/brand-profile/analyze-ai')
async def panel_brand_profile_analyze_ai(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not user:
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    body = await request.json()
    page_id = str(body.get('page_id', '') or '')
    if not page_id:
        return JSONResponse({'ok': False, 'error': 'missing_page_id'}, status_code=400)
    if not page_allowed_for_user(user, str(page_id)):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    cfg = load_config()
    try:
        context = collect_brand_meta_context(cfg, page_id, panel_user or '')
        analysis = analyze_brand_profile_with_ai(context)
        log_ai_usage('brand_analysis', analysis.get('_ai_provider', ''), analysis.get('_ai_model', ''), analysis.get('_ai_usage', {}), analysis.get('_ai_cost_usd', 0.0), page_id=page_id, item_type='brand')
        suggested = {
            'brand_name': analysis.get('brand_name', ''),
            'tagline': analysis.get('tagline', ''),
            'description': analysis.get('description', ''),
            'tone': analysis.get('tone', ''),
            'target_audience': analysis.get('target_audience', ''),
            'key_products': analysis.get('key_products', []),
            'visual_style': analysis.get('visual_style', ''),
            'colors': analysis.get('colors', []),
            'cta_style': analysis.get('cta_style', ''),
            'best_offer': analysis.get('best_offer', ''),
            'competitors': analysis.get('competitors', []),
            'instagram_handle': analysis.get('instagram_handle', ''),
            'facebook_page_name': analysis.get('facebook_page_name', ''),
            'negative_rules': analysis.get('negative_rules', ''),
            'text_rule': analysis.get('text_rule', ''),
            'insights_summary': analysis.get('insights_summary', ''),
            'positioning': analysis.get('positioning', ''),
            'bio_summary': analysis.get('bio_summary', ''),
            'recommended_posts': analysis.get('recommended_posts', []),
            'meta_context': context,
            'ai_model': analysis.get('_ai_model', ''),
        }
        saved = upsert_brand_profile(page_id, {
            'brand_name': suggested['brand_name'],
            'tagline': suggested['tagline'],
            'description': suggested['description'],
            'tone': suggested['tone'],
            'target_audience': suggested['target_audience'],
            'key_products': suggested['key_products'],
            'visual_style': suggested['visual_style'],
            'colors': suggested['colors'],
            'cta_style': suggested['cta_style'],
            'best_offer': suggested['best_offer'],
            'competitors': suggested['competitors'],
            'instagram_handle': suggested['instagram_handle'],
            'negative_rules': suggested['negative_rules'],
            'text_rule': suggested['text_rule'],
            'facebook_page_name': suggested['facebook_page_name'],
            'meta_auto_analysis': suggested,
            'art_direction': {
                'colors': suggested['colors'],
                'visual_style': suggested['visual_style'],
                'text_rule': suggested['text_rule'],
                'negative_rules': suggested['negative_rules'],
            },
        })
        return {'ok': True, 'page_id': page_id, 'analysis': suggested, 'profile': saved}
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'brand_ai_analysis_failed', 'detail': str(e)}, status_code=400)


@app.post('/panel/manus-analyze')
async def panel_manus_analyze(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    body = await request.json()
    page_id = body.get('page_id', '')
    u = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if page_id and u and not page_allowed_for_user(u, str(page_id)):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    analysis_type = (body.get('analysis_type', 'profile') or 'profile').strip().lower()
    if analysis_type not in ['profile', 'competitors']:
        analysis_type = 'profile'
    analysis = {
        'analysis_type': analysis_type,
        'platform': body.get('platform', 'instagram'),
        'handle': body.get('handle', ''),
        'competitors': body.get('competitors', ''),
        'goal': body.get('goal', 'improve_profile'),
        'manual_notes': body.get('manual_notes', ''),
        'analyzed_at': int(time.time()),
    }
    manus_key = get_secret(MANUS_API_KEY_NAME)
    if manus_key:
        analysis['manus_key_available'] = True
    if page_id:
        profile_key = 'manus_competitor_analysis' if analysis_type == 'competitors' else 'manus_profile_analysis'
        upsert_brand_profile(page_id, {profile_key: analysis, 'manus_analysis': analysis})
    return {'ok': True, 'analysis': analysis, 'manus_key_available': bool(manus_key)}


# ── Agent: Social Media Plan Generator ───────────────────────────────────────

@app.post('/panel/agents/generate-plan')
async def panel_agents_generate_plan(
    request: Request,
    panel_auth: Optional[str] = Cookie(default=None),
    panel_user: Optional[str] = Cookie(default=None),
):
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not user:
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    body = await request.json()
    page_id = str(body.get('page_id', '') or '')
    if not page_id:
        return JSONResponse({'ok': False, 'error': 'missing_page_id'}, status_code=400)
    if not page_allowed_for_user(user, page_id):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    import re, datetime, random, string
    mode = str(body.get('mode', 'monthly') or 'monthly').strip().lower()
    if mode not in ['monthly', 'single']:
        mode = 'monthly'
    weeks = max(1, min(12, _safe_int(body.get('weeks', 4 if mode == 'monthly' else 1), 4 if mode == 'monthly' else 1)))
    ppw = max(1, min(7, _safe_int(body.get('posts_per_week', 3 if mode == 'monthly' else 1), 3 if mode == 'monthly' else 1)))
    focus = str(body.get('focus', '') or '').strip()
    if not focus and body.get('suggest_focus'):
        try:
            suggestion_prompt = (
                'Você é um estrategista de conteúdo. '
                'Com base nos dados da marca, sugira um único foco de período curto, claro e acionável em português do Brasil. '
                'Responda somente com JSON: {"focus":"..."}'
            )
            suggestion_payload = f"{suggestion_prompt}\n\nDados da marca: {json.dumps(load_brand_profiles().get(str(page_id), {}), ensure_ascii=False)}"
            suggestion = _ai_generate_text('focus_suggestion', suggestion_payload, 60, json_mode=True)
            focus = (json.loads(suggestion.get('text') or '{}').get('focus') or '').strip()
            log_ai_usage('focus_suggestion', suggestion.get('provider', ''), suggestion.get('model', ''), suggestion.get('usage', {}), suggestion.get('cost_usd', 0.0), page_id=page_id, item_type=mode)
        except Exception as e:
            append_system_error_log(
                'plan_focus_suggestion_failed',
                'Focus suggestion failed',
                detail=str(e),
                page_id=page_id,
                mode=mode,
                provider=ai_settings_for('focus_suggestion').get('provider', ''),
                model=ai_settings_for('focus_suggestion').get('model', ''),
                prompt_preview=suggestion_payload[:1200],
                request=_request_context(request),
            )
            focus = focus or ''
        return JSONResponse({'ok': True, 'focus': focus})
    profiles = load_brand_profiles()
    profile = profiles.get(str(page_id), {})
    plan_settings = normalize_plan_settings(profile)
    stories_per_day = max(0, min(3, _safe_int(body.get('stories_per_day', plan_settings.get('stories_per_day', 1)), plan_settings.get('stories_per_day', 1))))
    max_carousels_per_week = max(0, min(ppw, _safe_int(body.get('max_carousels_per_week', plan_settings.get('max_carousels_per_week', 0)), plan_settings.get('max_carousels_per_week', 0))))
    total = weeks * ppw
    brand = '\n'.join([
        f"Marca: {profile.get('brand_name', '')}",
        f"Descrição: {profile.get('description', '')}",
        f"Tom de voz: {profile.get('tone', 'profissional')}",
        f"Público-alvo: {profile.get('target_audience', '')}",
        f"Produtos/Serviços: {profile.get('key_products', '')}",
        f"Estilo visual: {profile.get('visual_style', '')}",
        f"Melhor oferta: {profile.get('best_offer', '')}",
    ])
    extra_ctx = _build_plan_generation_extra_context(page_id, profile)
    extra_block = f"\n{extra_ctx}\n" if extra_ctx else ''

    start = datetime.datetime.now()
    weekdays = [0, 2, 4]  # Mon, Wed, Fri

    def next_dates(n_posts, n_weeks):
        dates = []
        d = start + datetime.timedelta(days=(7 - start.weekday()) % 7)
        for w in range(n_weeks):
            for wd in weekdays[:n_posts]:
                day = d + datetime.timedelta(days=wd)
                dates.append(day.strftime('%Y-%m-%d'))
            if len(dates) >= n_posts * n_weeks:
                break
            d += datetime.timedelta(weeks=1)
        return dates[:n_posts * n_weeks]

    dates = next_dates(ppw, weeks)
    hours = ['11:00','13:00','17:00','19:00','20:00']

    prompt = f"""Você é um especialista em Social Media Marketing.
Crie um calendário editorial para a marca abaixo.

{brand}
{extra_block}
{f'Foco do período: {focus}' if focus else ''}
Modo solicitado: {'plano mensal completo' if mode == 'monthly' else 'conteúdo avulso para teste'}

Gere EXATAMENTE {total} posts de feed. Responda SOMENTE com JSON puro, sem markdown.

{{
  "posts": [
    {{
      "id": "p1",
      "title": "Título curto do post",
      "theme": "Tema central (1 linha)",
      "format": "static|carousel",
      "suggested_date": "YYYY-MM-DD",
      "suggested_time": "HH:MM",
      "brief": "Briefing detalhado para designer e copywriter. Descreva o visual, tom, objetivo e detalhes criativos.",
      "cta": "Call to action",
      "hashtag_theme": "Tema para hashtags",
      "carousel_slides": ["Slide 1", "Slide 2", "Slide 3"],
      "story_script": ["Story 1", "Story 2", "Story 3"]
    }}
  ],
  "daily_story_scripts": [
    {{
      "id": "s1",
      "date": "YYYY-MM-DD",
      "title": "Título curto do roteiro",
      "theme": "Tema do dia",
      "format": "story_script",
      "suggested_time": "HH:MM",
      "story_script": ["Story 1", "Story 2", "Story 3"],
      "cta": "Call to action"
    }}
  ]
}}

Datas sugeridas: {', '.join(dates[:total])}
Regras:
- Nos posts de feed, use apenas formatos "static" e "carousel".
- Gere no máximo {max_carousels_per_week} carrossel(is) por semana para os posts de feed.
- Se houver 3 posts por semana, normalmente apenas 1 deles deve ser carrossel.
- Para "static", deixe "carousel_slides" e "story_script" vazios.
- Para "carousel", preencha de 3 a 5 tópicos curtos em "carousel_slides".
- Varie temas: educativo, produto, bastidores, depoimento, promoção, engajamento."""
    if mode == 'monthly' and stories_per_day > 0:
        story_dates = []
        day_cursor = start
        for _ in range(max(1, weeks * 7)):
            story_dates.append(day_cursor.strftime('%Y-%m-%d'))
            day_cursor += datetime.timedelta(days=1)
        prompt += f"""

Além dos posts de feed, gere também um roteiro diário de stories para cada data a seguir:
{', '.join(story_dates)}

Regras para daily_story_scripts:
- Gere EXATAMENTE {len(story_dates)} roteiros diários.
- Cada roteiro deve ter entre 1 e {stories_per_day} story(s)/tela(s).
- Use sempre format = "story_script".
- Os roteiros devem reforçar o tema do dia com bastidor, prova social, enquete, dica curta ou CTA."""

    try:
        ai_result = _ai_generate_text('plan_generation', prompt, 90, json_mode=False)
        text = ai_result.get('text', '')
        model_used = ai_result.get('model', '')
        json_match = re.search(r'\{[\s\S]*\}', text)
        if not json_match:
            append_system_error_log(
                'plan_generation_invalid_ai_response',
                'Plan generation returned no JSON block',
                page_id=page_id,
                mode=mode,
                model=model_used,
                provider=ai_result.get('provider', ''),
                response_preview=text[:1200],
                prompt_preview=prompt[:1200],
                request=_request_context(request),
            )
            return JSONResponse({'ok': False, 'error': 'invalid_ai_response'}, status_code=400)
        plan_data = json.loads(json_match.group())
        posts = plan_data.get('posts', [])
        daily_story_scripts = plan_data.get('daily_story_scripts', []) if isinstance(plan_data.get('daily_story_scripts'), list) else []
        # Ensure dates/times are filled
        for i, p in enumerate(posts):
            fmt = str(p.get('format', 'static') or 'static').strip().lower()
            if fmt not in ['static', 'carousel']:
                fmt = 'static'
            p['format'] = fmt
            if not p.get('suggested_date') and i < len(dates):
                p['suggested_date'] = dates[i]
            if not p.get('suggested_time'):
                p['suggested_time'] = hours[i % len(hours)]
            if not p.get('id'):
                p['id'] = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
            p['carousel_slides'] = p.get('carousel_slides') if isinstance(p.get('carousel_slides'), list) else []
            p['story_script'] = p.get('story_script') if isinstance(p.get('story_script'), list) else []
        for i, p in enumerate(daily_story_scripts):
            p['format'] = 'story_script'
            if not p.get('date'):
                p['date'] = (start + datetime.timedelta(days=i)).strftime('%Y-%m-%d')
            p['suggested_date'] = p.get('date')
            if not p.get('suggested_time'):
                p['suggested_time'] = '12:00'
            if not p.get('id'):
                p['id'] = 'story_' + ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
            p['carousel_slides'] = []
            lines = p.get('story_script') if isinstance(p.get('story_script'), list) else []
            p['story_script'] = lines[:max(1, stories_per_day)] or [p.get('theme') or p.get('title') or 'Story do dia']
        posts.extend(daily_story_scripts)
        log_ai_usage('plan_generation', ai_result.get('provider', ''), model_used, ai_result.get('usage', {}), ai_result.get('cost_usd', 0.0), page_id=page_id, item_type=mode)
        return {'ok': True, 'posts': posts, 'model': model_used, 'provider': ai_result.get('provider', ''), 'total': len(posts), 'focus': focus, 'mode': mode, 'cost_usd': ai_result.get('cost_usd', 0.0), 'plan_settings': {'stories_per_day': stories_per_day, 'max_carousels_per_week': max_carousels_per_week}}
    except json.JSONDecodeError as e:
        append_system_error_log(
            'plan_generation_json_parse_error',
            'Plan generation JSON parse failed',
            detail=str(e),
            page_id=page_id,
            mode=mode,
            prompt_preview=prompt[:1200],
            request=_request_context(request),
        )
        return JSONResponse({'ok': False, 'error': 'json_parse_error', 'detail': str(e)}, status_code=400)
    except Exception as e:
        append_system_error_log(
            'plan_generation_failed',
            'Plan generation failed',
            detail=str(e),
            page_id=page_id,
            mode=mode,
            focus=focus,
            provider=ai_settings_for('plan_generation').get('provider', ''),
            model=ai_settings_for('plan_generation').get('model', ''),
            prompt_preview=prompt[:1200],
            request=_request_context(request),
        )
        return JSONResponse({'ok': False, 'error': 'plan_generation_failed', 'detail': str(e)}, status_code=400)


# ── InstaScrapper: profile analysis & competitor tracking ────────────────────

@app.get('/panel/insta/sessions')
def panel_insta_sessions(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    sessions = _insta_saved_sessions()
    default = _insta_default_session_username()
    eff = _insta_effective_as_user('')
    return {
        'ok': True,
        'sessions': sessions,
        'default_session': default,
        'login_session': eff,
    }


@app.post('/panel/insta/profile')
async def panel_insta_profile(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    """Get profile data (fast, no AI). Saves snapshot if page_id provided."""
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not user:
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    body = await request.json()
    username = (body.get('username', '') or '').strip().lstrip('@')
    page_id = str(body.get('page_id', '') or '')
    as_user = _insta_effective_as_user((body.get('as_user', '') or '').strip())
    if not username:
        return JSONResponse({'ok': False, 'error': 'missing_username'}, status_code=400)
    r = _run_insta_script_with_session_fallback('get_profile_json.py', username=username, as_user=as_user, timeout=120)
    if r.get('ok') and page_id:
        profile = r.get('profile', {})
        followers = _parse_followers(profile.get('followers', 0))
        following = _parse_followers(profile.get('following', 0))
        posts_count = _parse_followers(profile.get('posts', 0))
        db_save_snapshot(page_id, username, {
            'followers': followers, 'following': following,
            'posts': posts_count, 'profile': profile,
        })
        try:
            upsert_brand_profile(
                page_id,
                {'instagram_scraper_analysis_summary': _summarize_instagram_for_brand(username, profile, {})},
            )
        except Exception:
            pass
    return r


@app.post('/panel/insta/analyze')
async def panel_insta_analyze(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    """Run full AI analysis (slower, ~60-90s). Uses cache if available today."""
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not user:
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    body = await request.json()
    username = (body.get('username', '') or '').strip().lstrip('@')
    page_id = str(body.get('page_id', '') or '')
    as_user = _insta_effective_as_user((body.get('as_user', '') or '').strip())
    force = bool(body.get('force', False))
    if not username:
        return JSONResponse({'ok': False, 'error': 'missing_username'}, status_code=400)
    extra_args = ['--force'] if force else []
    r = _run_insta_script_with_session_fallback('analyze_json.py', username=username, as_user=as_user, extra_args=extra_args, timeout=180)
    if not r.get('ok'):
        fail_diag = {
            'failed': True,
            'error': r.get('error'),
            'detail': r.get('detail'),
            'tried_sessions': r.get('tried_sessions'),
            'script_stderr_tail': (r.get('stderr') or r.get('script_stderr_tail') or '')[-2500:],
            'user_hint': 'Falha ao executar o script: sessão, timeout ou saída inválida. Veja `detail` e o fim de stderr em diagnostics.',
        }
        r = dict(r)
        r['diagnostics'] = fail_diag
        if page_id:
            try:
                upsert_brand_profile(
                    str(page_id),
                    {
                        'last_insta_analyze_diagnostics': {
                            'updated_at': int(time.time()),
                            'username': username,
                            **{k: v for k, v in fail_diag.items() if v is not None},
                        },
                    },
                )
            except Exception:
                pass
        return r
    diag = _build_insta_analyze_diagnostics(r)
    r = dict(r)
    r['diagnostics'] = diag
    if page_id:
        try:
            upsert_brand_profile(
                str(page_id),
                {
                    'last_insta_analyze_diagnostics': {
                        'updated_at': int(time.time()),
                        'username': username,
                        **{k: v for k, v in diag.items() if v is not None},
                    },
                },
            )
        except Exception:
            pass
    if r.get('ok') and page_id:
        profile = r.get('profile', {})
        analysis = r.get('analysis', {})
        followers = _parse_followers(profile.get('followers', 0))
        db_save_snapshot(page_id, username, {
            'followers': followers,
            'following': _parse_followers(profile.get('following', 0)),
            'posts': _parse_followers(profile.get('posts', 0)),
            'profile': profile, 'analysis': analysis,
        })
        route = _ai_route('profile_analysis')
        provider = r.get('provider') or route.get('provider', 'gemini')
        model = r.get('model') or route.get('model') or ('gpt-4o' if provider == 'openai' else 'gemini-2.0-flash')
        usage = r.get('usage') if isinstance(r.get('usage'), dict) and r.get('usage') else {
            'input_tokens': _estimate_text_tokens(json.dumps(profile, ensure_ascii=False)),
            'output_tokens': _estimate_text_tokens(json.dumps(analysis, ensure_ascii=False)),
        }
        usage['total_tokens'] = int(usage.get('total_tokens') or (usage.get('input_tokens', 0) + usage.get('output_tokens', 0)))
        cost_usd = float(r.get('cost_usd') or _calculate_ai_cost(provider, model, usage))
        log_ai_usage(
            'profile_analysis',
            provider,
            model,
            usage,
            cost_usd,
            page_id=page_id,
            post_id=username,
            item_type='instagram_profile',
            extra={'username': username, 'cached': bool(r.get('cached'))},
        )
        try:
            upsert_brand_profile(
                page_id,
                {'instagram_scraper_analysis_summary': _summarize_instagram_for_brand(username, profile, analysis)},
            )
        except Exception:
            pass
    return r


@app.post('/panel/insta/add-competitor')
async def panel_insta_add_competitor(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not user:
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    body = await request.json()
    page_id = str(body.get('page_id', '') or '')
    username = (body.get('username', '') or '').strip().lstrip('@')
    label = (body.get('label', '') or '').strip()
    is_own = int(bool(body.get('is_own', False)))
    if not page_id or not username:
        return JSONResponse({'ok': False, 'error': 'missing_page_id_or_username'}, status_code=400)
    db_add_competitor(page_id, username, label, is_own)
    return {'ok': True}


@app.post('/panel/insta/remove-competitor')
async def panel_insta_remove_competitor(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not user:
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    body = await request.json()
    page_id = str(body.get('page_id', '') or '')
    username = (body.get('username', '') or '').strip()
    db_remove_competitor(page_id, username)
    return {'ok': True}


@app.get('/panel/insta/competitors')
def panel_insta_competitors(request: Request, page_id: str = '', panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    if not page_id:
        return JSONResponse({'ok': False, 'error': 'missing_page_id'}, status_code=400)
    summary = db_get_competitor_summary(page_id)
    bp = get_brand_profile(str(page_id))
    return {
        'ok': True,
        'competitors': summary,
        'last_insta_analyze_diagnostics': bp.get('last_insta_analyze_diagnostics') or None,
    }


def _trunc_json_for_prompt(obj, n: int = 8000) -> str:
    try:
        s = json.dumps(obj, ensure_ascii=False)
    except Exception:
        s = str(obj)
    return s[:n] + ('…' if len(s) > n else '')


def _build_single_post_briefing(page_id: str, theme: str, image_focus: str = '') -> str:
    p = get_brand_profile(str(page_id))
    lines = [
        f"Marca: {p.get('brand_name', '') or '—'}",
        f"Descrição / posicionamento: {p.get('description', '') or '—'}",
        f"Tom de voz: {p.get('tone', 'profissional')}",
        f"Público-alvo: {p.get('target_audience', '') or '—'}",
        f"Produtos/serviços: {p.get('key_products', '') or '—'}",
        f"CTA / oferta: {p.get('best_offer', '') or '—'} | {p.get('cta_style', '') or ''}",
    ]
    if (theme or '').strip():
        lines.append(f"Tema do post (pedido explícito): {theme.strip()}")
    else:
        lines.append('Tema: escolha um tema alinhado à marca para um único post de teste (educar, prova social, oferta, bastidor).')
    if (image_focus or '').strip():
        lines.append(f"Briefing adicional do usuário (usar na legenda E na imagem — prioridade máxima): {image_focus.strip()}")
    return '\n'.join(lines)


def _build_single_post_creative_plan(page_id: str, theme: str, caption: str = '') -> dict:
    p = get_brand_profile(str(page_id))
    brand_name = p.get('brand_name', '') or p.get('page_name', '') or 'Marca'
    description = p.get('description', '') or ''
    audience = p.get('target_audience', '') or ''
    tone = p.get('tone', 'profissional') or 'profissional'
    products = p.get('key_products', '') or ''
    visual_style = p.get('visual_style', '') or ''
    logo_url = p.get('logo_url', '') or ''
    prompt = (
        'Você é um agente de arte para Instagram. '
        'Crie a estratégia textual da peça antes da imagem. '
        'Responda SOMENTE com JSON válido em português do Brasil com as chaves: '
        '{"title":"","subtitle":"","creative_direction":"","caption_summary":""}. '
        'O title deve ser curto, forte e visual. '
        'O subtitle deve complementar o title em 1 linha. '
        'creative_direction deve descrever em 2-4 frases a intenção visual da peça. '
        'caption_summary resume em 1 frase a ideia central da legenda.\n\n'
        f'Marca: {brand_name}\n'
        f'Descrição: {description}\n'
        f'Público: {audience}\n'
        f'Tom: {tone}\n'
        f'Produtos/serviços: {products}\n'
        f'Estilo visual atual: {visual_style}\n'
        f'Tema do conteúdo: {theme or "livre, alinhado à marca"}\n'
        f'Legenda base: {caption or "ainda não gerada"}\n'
    )
    try:
        res = _ai_generate_text('copy_generation', prompt, 60, json_mode=True)
        parsed = _extract_json_block(res.get('text') or '')
        if isinstance(parsed, dict):
            parsed['_provider'] = res.get('provider', '')
            parsed['_model'] = res.get('model', '')
            parsed['_logo_url'] = logo_url
            return parsed
    except Exception:
        pass
    return {
        'title': (theme or brand_name)[:48],
        'subtitle': f'{brand_name} em foco',
        'creative_direction': f'Visual clean, corporativo e moderno para {brand_name}, com foco em {theme or "autoridade da marca"}.',
        'caption_summary': (caption or '')[:160],
        '_provider': 'fallback',
        '_model': 'fallback',
        '_logo_url': logo_url,
    }


def _build_single_post_image_prompt(page_id: str, theme: str, title: str, subtitle: str, caption: str, creative_direction: str = '') -> str:
    p = get_brand_profile(str(page_id))
    brand_name = p.get('brand_name', '') or p.get('page_name', '') or 'Marca'
    logo_url = p.get('logo_url', '') or ''
    visual_style = p.get('visual_style', '') or 'moderno, tecnológico e minimalista'
    colors = p.get('colors', [])
    if isinstance(colors, list):
        color_text = ', '.join(str(c) for c in colors[:6] if str(c).strip())
    else:
        color_text = str(colors or '')
    audience = p.get('target_audience', '') or ''
    base_prompt = (
        'Crie uma arte para Instagram no formato 1:1 (1080x1080), com estilo moderno, tecnológico e minimalista, '
        f'adaptado para a empresa {brand_name} e para o tema "{theme or title}".\n\n'
        'Elementos da arte:\n'
        f'- Fundo e atmosfera alinhados à marca, com visual premium e direção: {visual_style}\n'
        f'- Paleta sugerida da marca: {color_text or "usar cores da marca quando disponíveis, senão neutros sofisticados"}\n'
        f'- Contexto visual coerente com o conteúdo e o público: {audience or "público profissional da marca"}\n'
        '- Tipografia clean e moderna (sans-serif), com alto contraste\n'
        '- Composição preparada para título e subtítulo\n\n'
        'Conteudo:\n'
        f'- Título: "{title}"\n'
        f'- Subtítulo: "{subtitle}"\n'
        f'- Contexto da legenda: "{caption[:400]}"\n'
        f'- Direção criativa adicional: "{creative_direction}"\n\n'
        'Canto inferior reservado:\n'
        '- Deixar área completamente limpa no canto inferior ESQUERDO — sem texto, ícone, decoração ou qualquer elemento. A logo real será colada como overlay depois.\n'
        '- Nao gerar, recriar ou desenhar nenhuma logo, simbolo de marca ou logotipo na imagem\n\n'
        'Direcao de design:\n'
        '- Visual corporativo, premium e contemporâneo\n'
        '- Mistura de realismo com elementos gráficos sutis, sem poluição visual\n'
        '- Layout limpo com boa hierarquia\n'
        '- Subtítulo pequeno acima\n'
        '- Título grande e dominante\n'
        '- Destaque visual na palavra-chave principal\n\n'
        'Restricoes:\n'
        '- Sem poluição visual\n'
        '- Sem excesso de elementos\n'
        '- Sem distorcer texto\n'
        '- Sem logos, marcas ou logotipos desenhados na imagem\n\n'
        '--ar 1:1 --v 6 --style raw'
    )
    return base_prompt


@app.post('/panel/insta/compare')
async def panel_insta_compare(
    request: Request,
    panel_auth: Optional[str] = Cookie(default=None),
    panel_user: Optional[str] = Cookie(default=None),
):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not user:
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    body = await request.json()
    page_id = str(body.get('page_id', '') or '')
    competitor = (body.get('competitor_username', '') or '').strip().lstrip('@').lower()
    if not page_id or not competitor:
        return JSONResponse({'ok': False, 'error': 'missing_page_id_or_username'}, status_code=400)
    if not page_allowed_for_user(user, page_id):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    comps = db_get_competitor_summary(page_id)
    own = next((c for c in comps if c.get('is_own')), None)
    comp = next((c for c in comps if str(c.get('username', '')).lower() == competitor), None)
    if not own:
        return JSONResponse({'ok': False, 'error': 'own_profile_missing'}, status_code=400)
    if not comp:
        return JSONResponse({'ok': False, 'error': 'competitor_not_found'}, status_code=400)
    brand = get_brand_profile(page_id)
    prompt = (
        'Você é estrategista de Instagram. Compare o perfil do cliente (próprio) com o concorrente.\n\n'
        f'PRÓPRIO (@{own.get("username", "")}): {own.get("followers", 0)} seguidores, {own.get("posts", 0)} posts, Δ {own.get("delta", 0)}.\n'
        f'Análise IA (recorte): {_trunc_json_for_prompt(own.get("analysis") or {}, 7000)}\n\n'
        f'CONCORRENTE (@{comp.get("username", "")}): {comp.get("followers", 0)} seguidores, {comp.get("posts", 0)} posts, Δ {comp.get("delta", 0)}.\n'
        f'Análise IA (recorte): {_trunc_json_for_prompt(comp.get("analysis") or {}, 7000)}\n\n'
        f'Contexto marca: {brand.get("brand_name", "")} — {str(brand.get("description", ""))[:600]}\n\n'
        'Responda SOMENTE com JSON válido (português do Brasil) com as chaves:\n'
        '"resumo_numeros": "3–5 frases comparando escala, consistência e posição.",\n'
        '"vantagens_concorrente": ["..."],\n'
        '"vantagens_meu_perfil": ["..."],\n'
        '"desvantagens_meu_perfil": ["..."],\n'
        '"o_que_fazer": ["ação concreta 1", "ação 2", "ação 3"],\n'
        '"sintese_estrategica": "Parágrafo com prioridade única em relação a esse concorrente."'
    )
    try:
        res = _ai_generate_text('profile_analysis', prompt, 120, json_mode=True)
        parsed = _extract_json_block(res.get('text') or '')
        if not isinstance(parsed, dict):
            raise ValueError('invalid_compare_json')
        log_ai_usage(
            'profile_analysis', res.get('provider', ''), res.get('model', ''),
            res.get('usage', {}), res.get('cost_usd', 0.0),
            page_id=page_id, post_id=competitor, item_type='ig_compare',
        )
        return {
            'ok': True, 'compare': parsed,
            'provider': res.get('provider', ''), 'model': res.get('model', ''),
            'cost_usd': res.get('cost_usd', 0.0),
        }
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'compare_failed', 'detail': str(e)}, status_code=400)


@app.post('/panel/single-content/generate')
async def panel_single_content_generate(
    request: Request,
    panel_auth: Optional[str] = Cookie(default=None),
    panel_user: Optional[str] = Cookie(default=None),
):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not user:
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    body = await request.json()
    page_id = str(body.get('page_id', '') or '')
    theme = str(body.get('theme', '') or '')
    image_focus = str(body.get('image_focus', '') or '').strip()
    image_source = str(body.get('image_source', 'ai') or 'ai').strip().lower()
    selected_image_url = str(body.get('selected_image_url', '') or '').strip()
    if not page_id:
        return JSONResponse({'ok': False, 'error': 'missing_page_id'}, status_code=400)
    if not page_allowed_for_user(user, page_id):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    cfg = load_config()
    briefing = _build_single_post_briefing(page_id, theme, image_focus=image_focus)
    p = get_brand_profile(page_id)
    ad = p.get('art_direction') if isinstance(p.get('art_direction'), dict) else {}
    icp = p.get('icp_analysis') if isinstance(p.get('icp_analysis'), dict) else {}
    colors = p.get('colors')
    if isinstance(colors, str):
        colors = [c.strip() for c in colors.split(',') if c.strip()][:8]
    icp_bits = []
    if icp.get('persona') and isinstance(icp.get('persona'), dict):
        persona = icp.get('persona') or {}
        if persona.get('name'):
            icp_bits.append(f"Persona principal: {persona.get('name')}")
        if persona.get('summary'):
            icp_bits.append(str(persona.get('summary')))
    if icp.get('demographics') and isinstance(icp.get('demographics'), dict):
        demo = icp.get('demographics') or {}
        icp_bits.append('Dados demográficos: ' + ', '.join(f'{k}={v}' for k, v in demo.items() if v))
    if icp.get('empathy_map') and isinstance(icp.get('empathy_map'), dict):
        em = icp.get('empathy_map') or {}
        for key in ('thinks_and_feels', 'sees', 'hears', 'pains', 'gains'):
            val = em.get(key)
            if val:
                icp_bits.append(f'{key}: {val}')
    art = {
        'colors': colors if isinstance(colors, list) else ad.get('colors'),
        'visual_style': p.get('visual_style') or ad.get('visual_style'),
        'font_preference': p.get('font_preference') or ad.get('font_preference'),
        'logo_url': p.get('logo_url') or ad.get('logo_url'),
        'reference_image_url': p.get('reference_image_url') or ad.get('reference_image_url'),
        'reference_style_prompt': p.get('reference_style_prompt') or ad.get('style_prompt') or '',
        'use_reference_style': bool(p.get('use_reference_style')),
        'references': [str(r.get('url', '')) for r in (p.get('visual_references') or []) if isinstance(r, dict) and r.get('use_for_style')],
        'niche': p.get('description') or p.get('brand_name') or p.get('target_audience') or '',
        'message_objective': p.get('best_offer') or theme or p.get('cta_style') or '',
        'realistic_scenario': ad.get('realistic_scenario') or p.get('visual_style') or 'cenário coerente com o negócio',
        'character_description': ad.get('character_description') or '',
        'render_type': ad.get('render_type') or 'realismo + elementos 3D sutis',
        'lighting_type': ad.get('lighting_type') or 'soft glow lighting',
        'emotion': ad.get('emotion') or 'confiança, clareza e alto valor percebido',
        'highlight_keyword': theme or p.get('best_offer') or '',
        'highlight_color': (colors[0] if isinstance(colors, list) and colors else '#F06B02'),
        'icp_context': ' | '.join(icp_bits[:8]),
        'image_focus': image_focus,
    }
    try:
        ai = generate_ai_copy_and_prompt(briefing, art_direction=art, page_id=page_id)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'copy_failed', 'detail': str(e)}, status_code=400)
    creative_plan = _build_single_post_creative_plan(page_id, theme, caption=ai.get('copy', ''))
    title = str(ai.get('title', '') or creative_plan.get('title', '') or '').strip()
    subtitle = str(ai.get('subtitle', '') or creative_plan.get('subtitle', '') or '').strip()
    creative_direction = str(creative_plan.get('creative_direction', '') or '').strip()
    image_prompt = str(ai.get('image_prompt', '') or '').strip()
    if not image_prompt:
        image_prompt = _build_single_post_image_prompt(
            page_id,
            theme,
            title=title,
            subtitle=subtitle,
            caption=ai.get('copy', ''),
            creative_direction=creative_direction,
        )
    if image_source in ('gallery', 'upload') and selected_image_url:
        return {
            'ok': True,
            'caption': ai.get('copy', ''),
            'title': title,
            'subtitle': subtitle,
            'creative_direction': creative_direction,
            'image_prompt': image_prompt,
            'public_url': selected_image_url,
            'local_path': '',
            'image': {},
            'image_source': image_source,
            'logo_url': art.get('logo_url', ''),
        }
    try:
        gallery = list(p.get('gallery_references') or [])
        gallery_matches = _select_gallery_refs_for_briefing(gallery, briefing + ' ' + image_prompt)
        style_refs = _get_style_ref_paths(page_id, max_refs=2)
        combined_refs = style_refs + [rp for rp in gallery_matches if rp not in style_refs]
        ref_paths = combined_refs[:4] if combined_refs else None
        gen = generate_image_asset(cfg, image_prompt, post_id='', prefix='singlepost', operation='image_generation', ref_image_paths=ref_paths)
        images = gen.get('images') or []
        first = images[0] if images else {}
        local_path = first.get('path') or gen.get('requested_output', '')
        logo_dark = str(p.get('logo_path', '') or '')
        logo_light = str(p.get('logo_light_path', '') or '')
        if local_path and (logo_dark or logo_light):
            overlaid = _apply_logo_smart(local_path, logo_dark, logo_light)
            if overlaid:
                local_path = overlaid
        # Always rebuild from final local_path so logo overlay is included
        public_url = publish_generated_file(cfg, local_path) if local_path else ''
        if not public_url:
            public_url = build_public_media_url(cfg, local_path, post_id=gen.get('post_id', ''), prefix='singlepost') if local_path else ''
        log_ai_usage(
            'image_generation', gen.get('provider', ''), gen.get('model', ''),
            gen.get('usage', {}), gen.get('cost_usd', 0.0), page_id=page_id, item_type='single_content',
        )
        return {
            'ok': True,
            'caption': ai.get('copy', ''),
            'title': title,
            'subtitle': subtitle,
            'creative_direction': creative_direction,
            'image_prompt': image_prompt,
            'public_url': public_url,
            'local_path': local_path,
            'image': first,
            'image_source': 'ai',
            'logo_url': art.get('logo_url', ''),
        }
    except Exception as e:
        return JSONResponse({
            'ok': False, 'error': 'image_failed', 'detail': str(e),
            'caption': ai.get('copy', ''), 'image_prompt': image_prompt,
            'title': title, 'subtitle': subtitle, 'creative_direction': creative_direction,
        }, status_code=400)


@app.post('/panel/single-content/suggest-focus')
async def panel_single_content_suggest_focus(
    request: Request,
    panel_auth: Optional[str] = Cookie(default=None),
    panel_user: Optional[str] = Cookie(default=None),
):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not user:
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    body = await request.json()
    page_id = str(body.get('page_id', '') or '')
    theme = str(body.get('theme', '') or '').strip()
    if not page_id:
        return JSONResponse({'ok': False, 'error': 'missing_page_id'}, status_code=400)
    if not page_allowed_for_user(user, page_id):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    p = get_brand_profile(page_id)
    icp = p.get('icp_analysis') if isinstance(p.get('icp_analysis'), dict) else {}
    ad = p.get('art_direction') if isinstance(p.get('art_direction'), dict) else {}
    brand_ctx = (
        f"Marca: {p.get('brand_name', '')}\n"
        f"Descrição: {p.get('description', '')}\n"
        f"Público-alvo: {p.get('target_audience', '')}\n"
        f"Produtos/serviços: {p.get('key_products', '')}\n"
        f"Estilo visual: {p.get('visual_style', '') or ad.get('visual_style', '')}\n"
        f"Tom: {p.get('tone', 'profissional')}\n"
        + (f"Tema do post: {theme}\n" if theme else '')
        + (f"ICP resumo: {json.dumps(icp, ensure_ascii=False)[:600]}\n" if icp else '')
    )
    prompt = (
        'Você é um estrategista de conteúdo e diretor de arte especialista em Instagram. '
        'Com base nos dados da marca abaixo, sugira um briefing detalhado para um post que vai guiar tanto a legenda quanto a imagem gerada por IA. '
        'O briefing deve cobrir: produto ou oferta em foco, mensagem principal, o que não pode aparecer, '
        'elementos visuais prioritários, público que a peça deve atrair, emoção ou valor que deve transmitir, '
        'e qualquer detalhe relevante (preço, CTA, prova social, cenário, etc.). '
        'Seja concreto, específico à marca e útil para quem vai revisar antes de gerar. '
        'Responda SOMENTE com JSON: {"image_focus": "..."}\n\n'
        f'{brand_ctx}'
    )
    try:
        result = _ai_generate_text('focus_suggestion', prompt, 60, json_mode=True)
        parsed = _extract_json_block(result.get('text') or '')
        image_focus = _coerce_text(parsed.get('image_focus'))
        if not image_focus:
            return JSONResponse({'ok': False, 'error': 'empty_suggestion'}, status_code=400)
        log_ai_usage('focus_suggestion', result.get('provider', ''), result.get('model', ''), result.get('usage', {}), result.get('cost_usd', 0.0), page_id=page_id, item_type='single_focus')
        return {'ok': True, 'image_focus': image_focus}
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)


@app.get('/panel/icp')
def panel_icp(request: Request, page_id: str = '', panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None), refresh: str = 'false'):
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not user:
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    if not page_id:
        return JSONResponse({'ok': False, 'error': 'missing_page_id'}, status_code=400)
    if not page_allowed_for_user(user, str(page_id)):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    profile = get_brand_profile(page_id)
    try:
        context = build_icp_context(page_id)
    except Exception as e:
        append_system_error_log(
            'icp_load_error',
            'Failed to load ICP screen context',
            detail=str(e),
            page_id=page_id,
        )
        context = {
            'brand_profile': profile,
            'own_profile': {},
            'competitors': [],
            'icp_onboarding_text': profile.get('icp_onboarding_text', ''),
            'icp_compare_notes': profile.get('icp_compare_notes', ''),
            'icp_adjustment_notes': profile.get('icp_adjustment_notes', ''),
            'icp_analysis_history': profile.get('icp_analysis_history', [])[-10:],
            'page_id': page_id,
        }
    return {'ok': True, 'page_id': page_id, 'context': context, 'analysis': profile.get('icp_analysis', {})}


@app.post('/panel/icp/generate')
async def panel_icp_generate(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not user:
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    body = await request.json()
    page_id = str(body.get('page_id', '') or '')
    if not page_id:
        return JSONResponse({'ok': False, 'error': 'missing_page_id'}, status_code=400)
    if not page_allowed_for_user(user, page_id):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    onboarding_text = str(body.get('onboarding_text', '') or '').strip()
    compare_notes = str(body.get('compare_notes', '') or '').strip()
    adjustment_notes = str(body.get('adjustment_notes', '') or '').strip()
    mode = str(body.get('mode', 'generate') or 'generate').strip().lower()
    try:
        analysis = generate_icp_analysis(page_id, onboarding_text=onboarding_text, compare_notes=compare_notes, adjustment_notes=adjustment_notes)
        profile = get_brand_profile(page_id)
        history = list(profile.get('icp_analysis_history') or [])
        history.append({
            'ts': int(time.time()),
            'mode': mode,
            'provider': analysis.get('_ai_provider', ''),
            'model': analysis.get('_ai_model', ''),
            'overview': analysis.get('overview', ''),
            'analysis_text': analysis.get('analysis_text', ''),
            'owner_input': {
                'onboarding_text': onboarding_text,
                'compare_notes': compare_notes,
                'adjustment_notes': adjustment_notes,
            },
        })
        profile = upsert_brand_profile(page_id, {
            'icp_onboarding_text': onboarding_text,
            'icp_compare_notes': compare_notes,
            'icp_adjustment_notes': adjustment_notes,
            'icp_analysis': analysis,
            'icp_analysis_history': history[-20:],
        })
        return {'ok': True, 'page_id': page_id, 'context': build_icp_context(page_id), 'analysis': profile.get('icp_analysis', {})}
    except Exception as e:
        append_system_error_log(
            'icp_generation_error',
            'ICP generation failed',
            detail=str(e),
            page_id=page_id,
            mode=mode,
            provider=_ai_route('icp_analysis').get('provider', ''),
            model=_ai_route('icp_analysis').get('model', ''),
            onboarding_text=onboarding_text[:1000],
            compare_notes=compare_notes[:1000],
            adjustment_notes=adjustment_notes[:1000],
        )
        return JSONResponse({'ok': False, 'error': 'icp_generation_failed', 'detail': str(e)}, status_code=400)


@app.get('/panel/insta/snapshots')
def panel_insta_snapshots(request: Request, username: str = '', days: int = 30, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    snaps = db_get_snapshots(username, days)
    return {'ok': True, 'snapshots': snaps}


# ── Instagram post (create + publish, session-based auth) ─────────────────────

@app.post('/meta/instagram/post')
async def meta_instagram_post(request: Request):
    """
    Create and publish a single Instagram image post.
    Body: { image_url: str, caption?: str, ig_user_id?, page_id?, username?, access_token?, mode? }
    """
    cfg = load_config()
    body = await request.json()
    image_url = body.get('image_url', '')
    caption = normalize_caption_text(body.get('caption', ''))
    post_type = (body.get('post_type', 'image') or 'image').strip().lower()
    publish_now = str(body.get('publish_now', 'true')).lower() in ['1', 'true', 'yes', 'y']
    if not image_url:
        return JSONResponse({'ok': False, 'error': 'missing_image_url'}, status_code=400)
    effective_ig_user_id, effective_token, effective_host = _resolve_ig_context(body)
    if not effective_ig_user_id or not effective_token:
        return JSONResponse({'ok': False, 'error': 'missing_instagram_auth_context'}, status_code=400)
    try:
        image_url = _ensure_ig_accessible_url(image_url, cfg)
        creation = instagram_create_media(cfg, effective_ig_user_id, effective_token, image_url, caption, host=effective_host)
        if 'error' in creation:
            return JSONResponse({'ok': False, 'error': 'media_create_failed', 'detail': creation['error'], 'media': {'post_type': post_type, 'image_url': image_url, 'caption': caption}}, status_code=400)
        result = {
            'ok': True,
            'post_type': post_type,
            'media': {
                'image_url': image_url,
                'caption': caption,
                'create_endpoint': f"https://{effective_host}/{cfg['graph_api_version']}/{effective_ig_user_id}/media",
                'publish_endpoint': f"https://{effective_host}/{cfg['graph_api_version']}/{effective_ig_user_id}/media_publish",
            },
            'creation': creation,
        }
        if publish_now:
            publish_result = instagram_publish_media(cfg, effective_ig_user_id, effective_token, creation.get('id', ''), host=effective_host)
            result['publish_result'] = publish_result
        else:
            result['publish_result'] = None
            result['next_step'] = {
                'action': 'publish_container',
                'creation_id': creation.get('id', ''),
                'endpoint': '/meta/instagram/publish-container',
            }
        return result
    except urllib.error.HTTPError as e:
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': e.read().decode('utf-8', errors='replace')}, status_code=400)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'instagram_post_failed', 'detail': str(e)}, status_code=400)


@app.get('/instagram/webhook')
def instagram_webhook_verify(request: Request):
    cfg = load_config()
    verify_token = get_secret(INSTAGRAM_VERIFY_TOKEN_NAME)
    mode = request.query_params.get('hub.mode', '')
    token = request.query_params.get('hub.verify_token', '')
    challenge = request.query_params.get('hub.challenge', '')
    code = request.query_params.get('code', '')
    error = request.query_params.get('error', '')

    if code:
        try:
            token_data = instagram_direct_exchange_code(cfg, code)
            short_token = token_data.get('access_token', '')
            long_lived = instagram_exchange_long_lived_token(cfg, short_token) if short_token else {}
            merged = dict(token_data)
            if long_lived:
                merged['short_lived_access_token'] = short_token
                merged.update(long_lived)
            save_json(INSTAGRAM_DIRECT_SESSION_PATH, merged)
            return RedirectResponse('/', status_code=302)
        except urllib.error.HTTPError as e:
            return JSONResponse({'ok': False, 'error': 'http_error', 'detail': e.read().decode('utf-8', errors='replace')}, status_code=400)
        except Exception as e:
            return JSONResponse({'ok': False, 'error': 'instagram_direct_exchange_failed', 'detail': str(e)}, status_code=400)

    if error:
        return JSONResponse({'ok': False, 'error': error}, status_code=400)

    if mode == 'subscribe' and token and token == verify_token:
        return PlainTextResponse(challenge)
    return PlainTextResponse('Forbidden', status_code=403)


@app.post('/instagram/webhook')
async def instagram_webhook_receive(request: Request):
    body = await request.json()
    EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with EVENTS_PATH.open('a') as f:
        f.write(json.dumps({'source': 'instagram_webhook', 'body': body}, ensure_ascii=False) + '\n')
    return {'ok': True}


@app.get('/instagram/connect/start')
def instagram_connect_start():
    cfg = load_config()
    direct = get_instagram_direct_config(cfg)
    if not direct['app_id'] or not direct['app_secret']:
        return JSONResponse({'ok': False, 'error': 'instagram_app_not_configured'}, status_code=400)
    scopes = 'instagram_business_basic,instagram_business_content_publish'
    url = (
        'https://www.instagram.com/oauth/authorize'
        f'?enable_fb_login=0&force_authentication=1&client_id={urllib.parse.quote(direct["app_id"])}'
        f'&redirect_uri={urllib.parse.quote(direct["callback_url"], safe="")}'
        f'&response_type=code&scope={urllib.parse.quote(scopes)}'
    )
    return RedirectResponse(url, status_code=302)


@app.get('/instagram/connect/callback')
def instagram_connect_callback(code: str = '', error: str = ''):
    cfg = load_config()
    if error:
        return JSONResponse({'ok': False, 'error': error}, status_code=400)
    if not code:
        return JSONResponse({'ok': False, 'error': 'missing_code'}, status_code=400)
    try:
        token_data = instagram_direct_exchange_code(cfg, code)
        short_token = token_data.get('access_token', '')
        long_lived = instagram_exchange_long_lived_token(cfg, short_token) if short_token else {}
        merged = dict(token_data)
        if long_lived:
            merged['short_lived_access_token'] = short_token
            merged.update(long_lived)
        save_json(INSTAGRAM_DIRECT_SESSION_PATH, merged)
        return RedirectResponse('/', status_code=302)
    except urllib.error.HTTPError as e:
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': e.read().decode('utf-8', errors='replace')}, status_code=400)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'instagram_direct_exchange_failed', 'detail': str(e)}, status_code=400)


@app.get('/internal/restart-panel')
def internal_restart_panel(token: str = ''):
    secret = get_secret(RESTART_TOKEN_NAME)
    if not secret or token != secret:
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    try:
        result = subprocess.run(['systemctl', 'restart', 'meta-connection-panel'], capture_output=True, text=True, check=True)
        return {'ok': True, 'service': 'meta-connection-panel', 'stdout': result.stdout, 'stderr': result.stderr}
    except subprocess.CalledProcessError as e:
        return JSONResponse({'ok': False, 'error': 'restart_failed', 'stdout': e.stdout, 'stderr': e.stderr}, status_code=500)


@app.get('/internal/panel-admin')
def internal_panel_admin(action: str = '', token: str = ''):
    secret = get_secret(PANEL_ADMIN_TOKEN_NAME)
    if not secret or token != secret:
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    action = (action or '').strip().lower()
    try:
        if action == 'status':
            result = subprocess.run(['systemctl', 'status', 'meta-connection-panel', '--no-pager'], capture_output=True, text=True, check=True)
            return {'ok': True, 'action': action, 'stdout': result.stdout, 'stderr': result.stderr}
        if action == 'restart':
            result = subprocess.run(['systemctl', 'restart', 'meta-connection-panel'], capture_output=True, text=True, check=True)
            return {'ok': True, 'action': action, 'stdout': result.stdout, 'stderr': result.stderr}
        if action == 'logs':
            result = subprocess.run(['journalctl', '-u', 'meta-connection-panel', '-n', '80', '--no-pager'], capture_output=True, text=True, check=True)
            return {'ok': True, 'action': action, 'stdout': result.stdout, 'stderr': result.stderr}
        return JSONResponse({'ok': False, 'error': 'unsupported_action'}, status_code=400)
    except subprocess.CalledProcessError as e:
        return JSONResponse({'ok': False, 'error': 'panel_admin_failed', 'action': action, 'stdout': e.stdout, 'stderr': e.stderr}, status_code=500)


@app.get('/meta/connect/start')
def meta_connect_start(panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    email = _normalize_panel_email(panel_user or '')
    cfg = load_config()
    if not cfg['app_id']:
        return JSONResponse({'ok': False, 'error': 'app_id_not_configured'}, status_code=400)
    callback_url = cfg['public_base_url'].rstrip('/') + cfg['oauth_callback_path']
    state_payload = {
        'panel_user': email,
        'ts': int(time.time()),
    }
    oauth_url = (
        f"https://www.facebook.com/{cfg['graph_api_version']}/dialog/oauth"
        f"?client_id={quote(cfg['app_id'])}"
        f"&redirect_uri={quote(callback_url, safe='')}"
        f"&scope={quote(cfg['default_scopes'])}"
        f"&response_type=code"
        f"&state={quote(json.dumps(state_payload, ensure_ascii=False), safe='')}"
    )
    return RedirectResponse(oauth_url, status_code=302)


@app.get('/meta/connect/callback')
def meta_connect_callback(code: str = '', state: str = '', error: str = ''):
    if error:
        return JSONResponse({'ok': False, 'error': error, 'state': state}, status_code=400)
    if not code:
        return JSONResponse({'ok': False, 'error': 'missing_code', 'state': state}, status_code=400)
    try:
        panel_user_email = ''
        try:
            state_obj = json.loads(state) if state else {}
            if isinstance(state_obj, dict):
                panel_user_email = _normalize_panel_email(state_obj.get('panel_user', ''))
        except Exception:
            panel_user_email = ''
        cfg = load_config()
        token_data = exchange_code_for_token(cfg, code)
        access_token = token_data.get('access_token', '')
        me = fetch_me(cfg, access_token) if access_token else {}
        accounts = fetch_me_accounts(cfg, access_token) if access_token else {}
        ad_accounts = fetch_ad_accounts(cfg, access_token) if access_token else {}
        session = {
            'token': token_data,
            'me': me,
            'pages': accounts.get('data', []),
            'ad_accounts': ad_accounts.get('data', []),
            'state': state,
            'panel_user_email': panel_user_email,
            'connected_at': int(time.time()),
        }
        save_meta_session_for_panel_user(panel_user_email, session)
        return RedirectResponse('/', status_code=302)
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': body}, status_code=400)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'callback_failed', 'detail': str(e)}, status_code=400)


@app.get('/meta/accounts')
def meta_accounts(panel_user: Optional[str] = Cookie(default=None)):
    cfg = load_config()
    session = get_meta_session_for_panel_user(panel_user or '')
    access_token = ((session.get('token') or {}).get('access_token')) or ''
    if not access_token:
        return JSONResponse({'ok': False, 'error': 'not_connected'}, status_code=400)
    try:
        me = fetch_me(cfg, access_token)
        accounts = fetch_me_accounts(cfg, access_token)
        ad_accounts = fetch_ad_accounts(cfg, access_token)
        session['me'] = me
        session['pages'] = accounts.get('data', [])
        session['ad_accounts'] = ad_accounts.get('data', [])
        save_meta_session_for_panel_user(panel_user or '', session)
        return {'ok': True, 'me': me, 'pages': accounts.get('data', []), 'ad_accounts': ad_accounts.get('data', [])}
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': body}, status_code=400)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'accounts_failed', 'detail': str(e)}, status_code=400)


@app.get('/meta/instagram-accounts')
def meta_instagram_accounts(request: Request, admin_token: str = '', panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    token_ok = bool(admin_token and admin_token == get_secret(PANEL_ADMIN_TOKEN_NAME))
    session_ok = _panel_session_valid(panel_auth or '', panel_user or '')
    api_key_ok = _panel_auth_ok(request, panel_auth or '', panel_user or '')
    if not token_ok and not session_ok and not api_key_ok:
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    user = current_panel_user(panel_auth or '', panel_user or '', request=request) if (session_ok or api_key_ok) else {'role': 'admin'}
    accounts = list_instagram_accounts()
    if not is_admin_user(user):
        allowed = set(get_allowed_page_ids_for_user(user))
        accounts = [a for a in accounts if str(a.get('page_id', '')) in allowed]
    return {'ok': True, 'instagram_accounts': accounts}


@app.post('/meta/ai-copy')
async def meta_ai_copy(request: Request):
    """Generate AI copy + image_prompt from a briefing, without generating an image."""
    body = await request.json()
    briefing = (body.get('briefing', '') or '').strip()
    art_direction = body.get('art_direction', {}) or {}
    page_id = str(body.get('page_id', '') or '')
    plan_id = str(body.get('plan_id', '') or '')
    post_id = str(body.get('post_id', '') or '')
    item_type = str(body.get('item_type', '') or 'copy')
    if not briefing:
        return JSONResponse({'ok': False, 'error': 'missing_briefing'}, status_code=400)
    try:
        result = generate_ai_copy_and_prompt(briefing, art_direction=art_direction, page_id=page_id)
        log_ai_usage(
            operation='copy_generation',
            provider=result.get('provider', ''),
            model=result.get('model', result.get('provider', '')),
            usage=result.get('copy_usage', result.get('usage', {})),
            cost_usd=float(result.get('copy_cost_usd', result.get('cost_usd', 0.0)) or 0.0),
            page_id=page_id,
            plan_id=plan_id,
            post_id=post_id,
            item_type=item_type,
        )
        if result.get('prompt_provider') or result.get('prompt_model'):
            log_ai_usage(
                operation='prompt_generation',
                provider=result.get('prompt_provider', ''),
                model=result.get('prompt_model', result.get('prompt_provider', '')),
                usage=result.get('prompt_usage', {}),
                cost_usd=float(result.get('prompt_cost_usd', 0.0) or 0.0),
                page_id=page_id,
                plan_id=plan_id,
                post_id=post_id,
                item_type=item_type,
            )
        return {
            'ok': True,
            'copy': result.get('copy', ''),
            'title': result.get('title', ''),
            'subtitle': result.get('subtitle', ''),
            'image_prompt': result.get('image_prompt', ''),
            'provider': result.get('provider', ''),
            'prompt_provider': result.get('prompt_provider', ''),
            'prompt_model': result.get('prompt_model', ''),
            'art_direction': art_direction,
        }
    except Exception as e:
        append_system_error_log(
            'ai_copy_error',
            'AI copy generation failed',
            detail=str(e),
            briefing=briefing[:1000],
            art_direction=art_direction,
            **_request_context(request),
        )
        return JSONResponse({'ok': False, 'error': 'ai_copy_failed', 'detail': str(e)}, status_code=400)


@app.get('/studio/gallery')
def studio_gallery():
    """List already-generated images available for reuse."""
    cfg = load_config()
    base_url = cfg['public_base_url'].rstrip('/')
    exts = {'.jpg', '.jpeg', '.png', '.webp'}
    items = []
    for f in sorted(GENERATED_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.suffix.lower() in exts:
            stat = f.stat()
            items.append({
                'filename': f.name,
                'public_url': f'{base_url}/media/generated/{f.name}',
                'size': stat.st_size,
                'mtime': int(stat.st_mtime),
            })
    return {'ok': True, 'images': items}


@app.get('/panel/gallery')
def panel_gallery(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    return studio_gallery()


@app.get('/schedule/posts')
def schedule_posts_list(status: str = '', page_id: str = '', ig_user_id: str = ''):
    posts = load_scheduled_posts()
    items = list(posts.values())
    if status:
        items = [p for p in items if p.get('status') == status]
    if page_id:
        items = [p for p in items if str(p.get('page_id', '')) == str(page_id)]
    if ig_user_id:
        items = [p for p in items if str(p.get('ig_user_id', '')) == str(ig_user_id)]
    items.sort(key=lambda p: p.get('scheduled_at', 0))
    return {'ok': True, 'posts': items}


@app.post('/schedule/post/add')
async def schedule_post_add(request: Request):
    body = await request.json()
    admin_token = body.get('admin_token', '')
    token_ok = bool(admin_token and admin_token == get_secret(PANEL_ADMIN_TOKEN_NAME))
    if not token_ok and not _panel_auth_ok(request, ''):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    required = ['ig_user_id', 'access_token', 'image_url', 'caption', 'scheduled_at']
    for f in required:
        if not body.get(f):
            return JSONResponse({'ok': False, 'error': f'missing_{f}'}, status_code=400)
    entry = add_scheduled_post(
        ig_user_id=body['ig_user_id'],
        page_name=body.get('page_name', ''),
        access_token=body['access_token'],
        image_url=body['image_url'],
        caption=body['caption'],
        scheduled_at=int(body['scheduled_at']),
        page_id=body.get('page_id', ''),
        ig_username=body.get('ig_username', ''),
        source=body.get('source', 'manual'),
        plan_id=body.get('plan_id', ''),
        plan_post_id=body.get('plan_post_id', ''),
    )
    return {'ok': True, 'post': entry}


@app.get('/panel/content-plans')
def panel_content_plans(request: Request, page_id: str = '', limit: int = 10,
                        panel_auth: Optional[str] = Cookie(default=None),
                        panel_user: Optional[str] = Cookie(default=None)):
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not user:
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    if page_id and not page_allowed_for_user(user, str(page_id)):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    try:
        plans = db_load_plans(page_id, limit=limit) if page_id else []
        if not plans:
            # Fallback to JSON for legacy data
            legacy = load_content_plans()
            items = list(legacy.values())
            if page_id:
                items = [p for p in items if str(p.get('page_id','')) == str(page_id)]
            items.sort(key=lambda p: p.get('updated_at', 0), reverse=True)
            plans = items[:limit]
        return {'ok': True, 'plans': plans}
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=400)


@app.post('/panel/content-plan/save')
async def panel_content_plan_save(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not user:
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    body = await request.json()
    page_id = str(body.get('page_id', '') or '')
    if not page_id:
        return JSONResponse({'ok': False, 'error': 'missing_page_id'}, status_code=400)
    if not page_allowed_for_user(user, page_id):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    import random, string
    plan_id = str(body.get('plan_id', '') or '').strip() or ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))
    try:
        saved = db_save_plan(
            plan_id=plan_id, page_id=page_id,
            page_name=body.get('page_name', ''),
            ig_user_id=body.get('ig_user_id', ''),
            ig_username=body.get('ig_username', ''),
            posts=body.get('posts', []) or [],
            focus=body.get('focus', ''),
            model=body.get('model', ''),
            title=body.get('title', ''),
            plan_type=body.get('plan_type', 'monthly'),
            month_label=body.get('month_label', ''),
            generation_cost_usd=float(body.get('generation_cost_usd', 0.0) or 0.0),
        )
        return {'ok': True, 'plan': saved}
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=400)


@app.post('/panel/content-plan/update-post')
async def panel_content_plan_update_post(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not user:
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    body = await request.json()
    post_id = str(body.get('post_id', '') or '')
    plan_id = str(body.get('plan_id', '') or '')
    page_id = str(body.get('page_id', '') or '')
    if not post_id or not plan_id:
        return JSONResponse({'ok': False, 'error': 'missing_post_id_or_plan_id'}, status_code=400)
    if page_id and not page_allowed_for_user(user, page_id):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    updates = {k: v for k, v in body.items() if k not in ('post_id', 'plan_id')}
    try:
        db_update_post(post_id, plan_id, updates)
        return {'ok': True}
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=400)


@app.post('/panel/content-plan/validate-media')
async def panel_content_plan_validate_media(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not user:
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    body = await request.json()
    page_id = str(body.get('page_id', '') or '')
    if not page_id:
        return JSONResponse({'ok': False, 'error': 'missing_page_id'}, status_code=400)
    if not page_allowed_for_user(user, page_id):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    fmt = str(body.get('format', 'static') or 'static').strip().lower()
    caption = str(body.get('caption', '') or '')
    image_url = str(body.get('image_url', '') or '')
    image_urls = body.get('image_urls', []) if isinstance(body.get('image_urls'), list) else []
    target = get_instagram_account_by_username(page_id=page_id)
    if not target:
        return JSONResponse({'ok': False, 'error': 'instagram_account_not_found'}, status_code=404)
    ig = target.get('instagram_business_account') or {}
    ig_user_id = ig.get('id', '')
    access_token = target.get('page_access_token', '')
    if not ig_user_id or not access_token:
        return JSONResponse({'ok': False, 'error': 'missing_instagram_auth_context'}, status_code=400)
    cfg = load_config()
    try:
        if fmt == 'carousel':
            valid_urls = [u for u in image_urls if u][:10]
            if len(valid_urls) < 2:
                return JSONResponse({'ok': False, 'error': 'carousel_requires_at_least_2_images'}, status_code=400)
            children_ids = []
            child_results = []
            for img in valid_urls:
                probe = _probe_public_image_url(img)
                if not probe.get('ok'):
                    append_system_error_log('meta_validation_error', 'Carousel image URL is not serving an image', page_id=page_id, format=fmt, detail=probe)
                    return JSONResponse({'ok': False, 'error': 'carousel_image_url_invalid', 'detail': probe}, status_code=400)
                item = instagram_create_carousel_item(cfg, ig_user_id, access_token, img)
                child_results.append(item)
                if 'error' in item or not item.get('id'):
                    append_system_error_log('meta_validation_error', 'Carousel validation failed', page_id=page_id, format=fmt, detail=item)
                    return JSONResponse({'ok': False, 'error': 'carousel_item_create_failed', 'detail': item}, status_code=400)
                children_ids.append(item.get('id'))
            container = instagram_create_carousel_container(cfg, ig_user_id, access_token, children_ids, caption)
            if 'error' in container:
                append_system_error_log('meta_validation_error', 'Carousel container validation failed', page_id=page_id, format=fmt, detail=container)
                return JSONResponse({'ok': False, 'error': 'carousel_container_create_failed', 'detail': container}, status_code=400)
            return {'ok': True, 'validation': {'format': fmt, 'container_id': container.get('id', ''), 'children_ids': children_ids, 'validated_at': int(time.time())}}
        if not image_url:
            return JSONResponse({'ok': False, 'error': 'missing_image_url'}, status_code=400)
        probe = _probe_public_image_url(image_url)
        if not probe.get('ok'):
            append_system_error_log('meta_validation_error', 'Instagram image URL is not serving an image', page_id=page_id, format=fmt, detail=probe)
            return JSONResponse({'ok': False, 'error': 'image_url_invalid', 'detail': probe}, status_code=400)
        result = instagram_create_media(cfg, ig_user_id, access_token, image_url, caption)
        if 'error' in result:
            append_system_error_log('meta_validation_error', 'Instagram media validation failed', page_id=page_id, format=fmt, detail=result)
            return JSONResponse({'ok': False, 'error': 'media_create_failed', 'detail': result['error']}, status_code=400)
        return {'ok': True, 'validation': {'format': fmt, 'container_id': result.get('id', ''), 'validated_at': int(time.time())}}
    except urllib.error.HTTPError as e:
        detail = e.read().decode('utf-8', errors='replace')
        append_system_error_log('meta_validation_error', 'Instagram media validation HTTP error', page_id=page_id, format=fmt, detail=detail)
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': detail}, status_code=400)
    except Exception as e:
        append_system_error_log('meta_validation_error', 'Instagram media validation crashed', page_id=page_id, format=fmt, detail=str(e))
        return JSONResponse({'ok': False, 'error': 'media_validation_failed', 'detail': str(e)}, status_code=400)


@app.post('/panel/content-plan/schedule-batch')
async def panel_content_plan_schedule_batch(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    auth = require_panel_auth(panel_auth, panel_user, request=request)
    if auth:
        return auth
    body = await request.json()
    admin_token = get_secret(PANEL_ADMIN_TOKEN_NAME)
    ig_user_id = body.get('ig_user_id', '')
    access_token = body.get('access_token', '')
    page_id = body.get('page_id', '')
    page_name = body.get('page_name', '')
    ig_username = body.get('ig_username', '')
    posts = body.get('posts', []) or []
    if not ig_user_id or not access_token or not posts:
        return JSONResponse({'ok': False, 'error': 'missing_context_or_posts'}, status_code=400)
    created = []
    for item in posts:
        if not item.get('image_url') or not item.get('caption') or not item.get('scheduled_at'):
            continue
        channels = item.get('channels') or ['instagram']
        if 'instagram' in channels:
            entry = add_scheduled_post(
                ig_user_id=ig_user_id,
                page_name=page_name,
                access_token=access_token,
                image_url=item.get('image_url', ''),
                caption=item.get('caption', ''),
                scheduled_at=int(item.get('scheduled_at')),
                page_id=page_id,
                ig_username=ig_username,
                source='content_planner',
                plan_id=body.get('plan_id', ''),
                plan_post_id=item.get('id', ''),
            )
            entry['channel'] = 'instagram'
            created.append(entry)
        if 'facebook' in channels:
            cfg = load_config()
            fb_result = create_page_photo_post(
                cfg,
                page_id,
                item.get('image_url', ''),
                item.get('caption', ''),
                'false',
                str(int(item.get('scheduled_at'))),
            )
            created.append({
                'id': f"fb_{item.get('id', '')}",
                'channel': 'facebook',
                'page_id': page_id,
                'page_name': page_name,
                'caption': item.get('caption', ''),
                'image_url': item.get('image_url', ''),
                'scheduled_at': int(item.get('scheduled_at')),
                'source': 'facebook_graph',
                'status': 'scheduled',
                'result': fb_result,
            })
    return {'ok': True, 'scheduled': created, 'count': len(created), 'admin_token_present': bool(admin_token)}


@app.post('/schedule/post/delete')
async def schedule_post_delete(request: Request):
    body = await request.json()
    admin_token = body.get('admin_token', '')
    if not admin_token or admin_token != get_secret(PANEL_ADMIN_TOKEN_NAME):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    pid = body.get('id', '')
    posts = load_scheduled_posts()
    if pid not in posts:
        return JSONResponse({'ok': False, 'error': 'not_found'}, status_code=404)
    del posts[pid]
    save_scheduled_posts(posts)
    return {'ok': True}


@app.post('/schedule/post/publish-now')
async def schedule_post_publish_now(request: Request):
    body = await request.json()
    admin_token = body.get('admin_token', '')
    if not admin_token or admin_token != get_secret(PANEL_ADMIN_TOKEN_NAME):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    pid = body.get('id', '')
    posts = load_scheduled_posts()
    post = posts.get(pid)
    if not post:
        return JSONResponse({'ok': False, 'error': 'not_found'}, status_code=404)
    cfg = load_config()
    try:
        result = instagram_create_media(cfg, post['ig_user_id'], post['access_token'], post['image_url'], post['caption'])
        if 'error' in result:
            raise Exception(str(result['error']))
        pub = instagram_publish_media(cfg, post['ig_user_id'], post['access_token'], result['id'])
        if 'error' in pub:
            raise Exception(str(pub['error']))
        posts[pid]['status'] = 'published'
        posts[pid]['published_at'] = int(time.time())
        save_scheduled_posts(posts)
        return {'ok': True, 'result': pub}
    except Exception as e:
        posts[pid]['status'] = 'failed'
        posts[pid]['error'] = str(e)
        save_scheduled_posts(posts)
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=400)


@app.post('/studio/upload-image')
async def studio_upload_image(file: UploadFile = File(...)):
    """Upload an image file; convert to JPEG and store in static/generated/ (served by Nginx directly)."""
    cfg = load_config()
    import random, string
    suffix = ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(12))
    dest = GENERATED_DIR / f'upload{suffix}.jpg'
    try:
        GENERATED_DIR.mkdir(parents=True, exist_ok=True)
        raw = await file.read()
        import io
        with Image.open(io.BytesIO(raw)) as im:
            if im.mode in ('RGBA', 'LA', 'P'):
                im = im.convert('RGB')
            elif im.mode != 'RGB':
                im = im.convert('RGB')
            im.save(dest, format='JPEG', quality=95)
        public_url = cfg['public_base_url'].rstrip('/') + f'/media/generated/{dest.name}'
        return {'ok': True, 'public_url': public_url, 'filename': dest.name}
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'upload_failed', 'detail': str(e)}, status_code=400)


@app.post('/panel/gallery/upload-image')
async def panel_gallery_upload_image(request: Request, file: UploadFile = File(...), panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    return await studio_upload_image(file)


@app.get('/meta/ad-accounts')
def meta_ad_accounts(force_refresh: str = '0', panel_user: Optional[str] = Cookie(default=None)):
    cfg = load_config()
    session = get_meta_session_for_panel_user(panel_user or '')
    cached = session.get('ad_accounts', []) if isinstance(session, dict) else []
    if str(force_refresh).lower() not in ['1', 'true', 'yes'] and cached:
        return {'ok': True, 'ad_accounts': cached, 'cached': True}
    access_token = ((session.get('token') or {}).get('access_token')) or ''
    if not access_token:
        return JSONResponse({'ok': False, 'error': 'not_connected'}, status_code=400)
    try:
        ad_accounts = fetch_ad_accounts(cfg, access_token)
        session['ad_accounts'] = ad_accounts.get('data', [])
        save_meta_session_for_panel_user(panel_user or '', session)
        return {'ok': True, 'ad_accounts': ad_accounts.get('data', [])}
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        return JSONResponse({'ok': bool(cached), 'error': 'http_error', 'detail': body, 'ad_accounts': cached, 'cached': bool(cached)}, status_code=200 if cached else 400)
    except Exception as e:
        return JSONResponse({'ok': bool(cached), 'error': 'ad_accounts_failed', 'detail': str(e), 'ad_accounts': cached, 'cached': bool(cached)}, status_code=200 if cached else 400)


@app.get('/panel/campaigns/context')
def panel_campaigns_context(request: Request, page_id: str = '', panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not user:
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    if not page_id or not page_allowed_for_user(user, str(page_id)):
        return JSONResponse({'ok': False, 'error': 'forbidden_or_missing_page'}, status_code=403)
    session = get_meta_session_for_panel_user(panel_user or '')
    pages = (session.get('pages') or []) if isinstance(session, dict) else []
    own_ad_accounts = (session.get('ad_accounts') or []) if isinstance(session, dict) else []
    shared_ad_accounts = get_shareable_ad_accounts_from_admin() if not is_admin_user(user) else []
    ad_accounts = merge_ad_accounts_unique(own_ad_accounts, shared_ad_accounts)
    page = next((p for p in pages if str((p or {}).get('id', '')) == str(page_id)), {}) or {}
    company = load_companies().get(str(page_id), {}) or {}
    profile = get_brand_profile(str(page_id)) or {}
    bound_ad_account_id = normalize_ad_account_id(
        str(((company.get('bindings') or {}).get('meta') or {}).get('ad_account_id') or '')
    )
    enriched = []
    for acct in ad_accounts:
        acct_id = normalize_ad_account_id(str((acct or {}).get('id') or (acct or {}).get('account_id') or ''))
        if not ad_account_allowed_for_user(user, acct_id):
            continue
        score, reasons = _score_ad_account_for_page(acct, page=page, company=company, profile=profile, bound_ad_account_id=bound_ad_account_id)
        enriched.append({
            **acct,
            'id': acct_id,
            '_match_score': score,
            '_match_reasons': reasons,
            '_suggested': score > 0,
            '_bound': bool(bound_ad_account_id and acct_id == bound_ad_account_id),
        })
    enriched.sort(key=lambda x: (int(x.get('_match_score') or 0), str(x.get('name') or '').lower()), reverse=True)
    preferred = normalize_ad_account_id(profile.get('preferred_ad_account_id', ''))
    return {
        'ok': True,
        'page_id': str(page_id),
        'page': page,
        'preferred_ad_account_id': preferred,
        'bound_ad_account_id': bound_ad_account_id,
        'ad_accounts': enriched,
    }


@app.post('/panel/campaigns/context/save')
async def panel_campaigns_context_save(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not user:
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    body = await request.json()
    page_id = str(body.get('page_id', '') or '')
    preferred_ad_account_id = normalize_ad_account_id(body.get('preferred_ad_account_id', ''))
    if not page_id or not page_allowed_for_user(user, page_id):
        return JSONResponse({'ok': False, 'error': 'forbidden_or_missing_page'}, status_code=403)
    profile = upsert_brand_profile(page_id, {'preferred_ad_account_id': preferred_ad_account_id})
    return {'ok': True, 'profile': profile, 'preferred_ad_account_id': preferred_ad_account_id}


@app.get('/meta/ad-campaigns')
def meta_ad_campaigns(ad_account_id: str = '', effective_status: str = ''):
    cfg = load_config()
    if not ad_account_id:
        return JSONResponse({'ok': False, 'error': 'missing_ad_account_id'}, status_code=400)
    ad_account_id = normalize_ad_account_id(ad_account_id)
    statuses = [s.strip() for s in effective_status.split(',') if s.strip()]
    try:
        result = fetch_ad_account_campaigns(cfg, ad_account_id, statuses or None)
        return {'ok': True, 'ad_account_id': ad_account_id, 'campaigns': result.get('data', [])}
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': body}, status_code=400)


@app.get('/meta/ad-audiences')
def meta_ad_audiences(ad_account_id: str = ''):
    cfg = load_config()
    if not ad_account_id:
        return JSONResponse({'ok': False, 'error': 'missing_ad_account_id'}, status_code=400)
    try:
        result = fetch_ad_account_saved_audiences(cfg, ad_account_id)
        return {'ok': True, 'ad_account_id': ad_account_id, 'audiences': result.get('data', [])}
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': body}, status_code=400)


@app.get('/meta/ad-targeting-search')
def meta_ad_targeting_search(ad_account_id: str = '', q: str = '', limit: str = '20'):
    cfg = load_config()
    if not q:
        return JSONResponse({'ok': False, 'error': 'missing_query'}, status_code=400)
    try:
        result = fetch_targeting_search(cfg, q, ad_account_id, limit)
        return {'ok': True, 'ad_account_id': ad_account_id, 'query': q, 'results': result.get('data', [])}
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': body}, status_code=400)


@app.get('/meta/page-leadgen-forms')
def meta_page_leadgen_forms(page_id: str = ''):
    cfg = load_config()
    if not page_id:
        return JSONResponse({'ok': False, 'error': 'missing_page_id'}, status_code=400)
    try:
        result = fetch_page_leadgen_forms(cfg, page_id)
        return {'ok': True, 'page_id': page_id, 'forms': result.get('data', [])}
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': body}, status_code=400)


@app.get('/meta/ad-pixels')
def meta_ad_pixels(ad_account_id: str = ''):
    cfg = load_config()
    if not ad_account_id:
        return JSONResponse({'ok': False, 'error': 'missing_ad_account_id'}, status_code=400)
    try:
        result = fetch_ad_account_pixels(cfg, ad_account_id)
        return {'ok': True, 'ad_account_id': ad_account_id, 'pixels': result.get('data', [])}
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': body}, status_code=400)


@app.get('/meta/ad-performance-tree')
def meta_ad_performance_tree(request: Request, ad_account_id: str = '', date_preset: str = 'last_7d', since: str = '', until: str = '', limit: str = '250', panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not user:
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    cfg = load_config()
    if not ad_account_id:
        return JSONResponse({'ok': False, 'error': 'missing_ad_account_id'}, status_code=400)
    ad_account_id = normalize_ad_account_id(ad_account_id)
    if not ad_account_allowed_for_user(user, ad_account_id):
        return JSONResponse({'ok': False, 'error': 'forbidden_ad_account'}, status_code=403)
    try:
        payload = build_spend_active_ads_tree(cfg, ad_account_id, date_preset=date_preset, since=since, until=until, limit=limit)
        return {'ok': True, 'ad_account_id': ad_account_id, **payload}
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': body}, status_code=400)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'ad_performance_tree_failed', 'detail': str(e)}, status_code=400)


@app.post('/meta/ad-drafts/create-campaign')
async def meta_ad_draft_create_campaign(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not user:
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    cfg = load_config()
    body = await request.json()
    try:
        ad_account_id = normalize_ad_account_id(body.get('ad_account_id', ''))
        campaign_name = body.get('campaign_name', '')
        objective = body.get('objective', 'OUTCOME_SALES')
        special_ad_categories = body.get('special_ad_categories', [])
        adset_name = body.get('adset_name', '')
        daily_budget = str(body.get('daily_budget', '') or '')
        targeting = body.get('targeting', {}) or {}
        optimization_goal = body.get('optimization_goal', 'LINK_CLICKS')
        billing_event = body.get('billing_event', 'IMPRESSIONS')
        bid_strategy = body.get('bid_strategy', 'LOWEST_COST_WITHOUT_CAP')
        promoted_object = body.get('promoted_object')
        creative_name = body.get('creative_name', '')
        ad_name = body.get('ad_name', '')
        page_id = body.get('page_id', '')
        instagram_actor_id = body.get('instagram_actor_id', '')
        image_url = body.get('image_url', '')
        image_hash = body.get('image_hash', '')
        message = body.get('message', '')
        link = body.get('link', '')
        call_to_action_type = body.get('call_to_action_type', 'LEARN_MORE')
        if not ad_account_id or not campaign_name:
            return JSONResponse({'ok': False, 'error': 'missing_ad_account_id_or_campaign_name'}, status_code=400)
        if not ad_account_allowed_for_user(user, ad_account_id):
            return JSONResponse({'ok': False, 'error': 'forbidden_ad_account'}, status_code=403)
        campaign = create_campaign_draft(cfg, ad_account_id, campaign_name, objective, special_ad_categories, 'PAUSED')
        result = {'campaign': campaign, 'state': 'PAUSED'}
        adset = None
        if adset_name and daily_budget and targeting:
            adset = create_adset_draft(cfg, ad_account_id, campaign.get('id', ''), adset_name, optimization_goal, billing_event, daily_budget, targeting, 'PAUSED', promoted_object, bid_strategy)
            result['adset'] = adset
        creative = None
        if creative_name and page_id and (image_url or image_hash) and link:
            creative = create_adcreative_draft(cfg, ad_account_id, creative_name, page_id, instagram_actor_id, image_url, image_hash, message, link, call_to_action_type)
            result['creative'] = creative
        if ad_name and adset and creative:
            ad = create_ad_draft(cfg, ad_account_id, ad_name, adset.get('id', ''), creative.get('id', ''), 'PAUSED')
            result['ad'] = ad
        with META_AD_DRAFT_RUNS_PATH.open('a') as f:
            f.write(json.dumps({'request': body, 'result': result}, ensure_ascii=False) + '\n')
        return {'ok': True, **result}
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': body}, status_code=400)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'ad_draft_create_failed', 'detail': str(e)}, status_code=400)



@app.get('/panel/ad-account-memory')
def panel_ad_account_memory(request: Request, ad_account_id: str = '', panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not user:
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    ad_account_id = normalize_ad_account_id(ad_account_id)
    if not ad_account_allowed_for_user(user, ad_account_id):
        return JSONResponse({'ok': False, 'error': 'forbidden_ad_account'}, status_code=403)
    mem = load_ad_account_memory()
    return {'ok': True, 'ad_account_id': ad_account_id, 'memory': (mem or {}).get(ad_account_id, {})}


@app.get('/meta/interest-search')
def meta_interest_search(request: Request, q: str = '', ad_account_id: str = '', limit: str = '20', panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not user:
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    cfg = load_config()
    if not q:
        return {'ok': True, 'interests': []}
    try:
        ad_account_id = normalize_ad_account_id(ad_account_id)
        if ad_account_id and not ad_account_allowed_for_user(user, ad_account_id):
            return JSONResponse({'ok': False, 'error': 'forbidden_ad_account'}, status_code=403)
        r = fetch_targeting_search(cfg, query=q[:80], ad_account_id=ad_account_id, limit=limit)
        return {'ok': True, 'interests': r.get('data', [])[:20]}
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=400)


@app.get('/meta/account-links')
def meta_account_links(ad_account_id: str = '', page_id: str = ''):
    """Return all links and forms in use across recent ads + any lead forms for the page."""
    cfg = load_config()
    links = []
    forms = []
    try:
        if page_id:
            fr = fetch_page_leadgen_forms(cfg, page_id)
            for f in (fr.get('data') or [])[:20]:
                forms.append({'id': f.get('id'), 'name': f.get('name'), 'type': 'lead_form', 'status': f.get('status', '')})
    except Exception:
        pass
    try:
        if ad_account_id:
            acct = normalize_ad_account_id(ad_account_id)
            access_token = get_meta_access_token()
            params = {
                'fields': 'name,creative{object_story_spec,asset_feed_spec,link_url}',
                'limit': '50',
                'access_token': access_token,
            }
            url = f"https://graph.facebook.com/{cfg['graph_api_version']}/{acct}/ads?{urllib.parse.urlencode(params)}"
            ads_r = graph_get(url)
            seen = set()
            for ad in (ads_r.get('data') or []):
                cr = ad.get('creative') or {}
                spec = cr.get('object_story_spec') or {}
                link = (spec.get('link_data') or {}).get('link') or cr.get('link_url') or ''
                if link and link not in seen:
                    seen.add(link)
                    links.append({'url': link, 'ad_name': ad.get('name', '')})
    except Exception:
        pass
    return {'ok': True, 'forms': forms, 'links': links[:20]}


@app.post('/panel/campaigns/wizard/analyze')
async def panel_campaigns_wizard_analyze(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    """AI traffic manager: analyze account, find interests, forms, links, and generate campaign recommendation."""
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    body = await request.json()
    ad_account_id = normalize_ad_account_id(body.get('ad_account_id', ''))
    page_id = str(body.get('page_id', '') or '')
    product = str(body.get('product', '') or '').strip()
    objective = str(body.get('objective', '') or 'OUTCOME_LEADS')
    budget = str(body.get('budget', '') or '50')
    if not ad_account_id:
        return JSONResponse({'ok': False, 'error': 'missing_ad_account_id'}, status_code=400)
    cfg = load_config()
    profile = get_brand_profile(page_id) if page_id else {}
    mem = (load_ad_account_memory() or {}).get(ad_account_id, {})

    # 1. Lead forms
    forms = []
    try:
        if page_id:
            fr = fetch_page_leadgen_forms(cfg, page_id)
            forms = [{'id': f.get('id'), 'name': f.get('name', ''), 'status': f.get('status', '')}
                     for f in (fr.get('data') or [])[:15]]
    except Exception:
        pass

    # 2. Pixels
    pixels = []
    try:
        pr = fetch_ad_account_pixels(cfg, ad_account_id)
        pixels = (pr.get('data') or [])[:5]
    except Exception:
        pass

    # 3. Pull historical adsets targeting: locations, interests, demographics already used
    historical_interests: list[dict] = []
    historical_locations: list[dict] = []
    historical_ages: list[dict] = []
    seen_int_ids: set = set()
    seen_loc_keys: set = set()
    try:
        adsets_r = fetch_adsets(cfg, ad_account_id, limit='50')
        for adset in (adsets_r.get('data') or []):
            tgt = adset.get('targeting') or {}
            # Locations — Meta uses different key fields per type
            geo = tgt.get('geo_locations') or {}
            for loc_type in ['cities', 'regions', 'countries', 'zips', 'places', 'location_cluster_ids']:
                for loc in (geo.get(loc_type) or []):
                    # cities/regions use 'key', countries use 'country_code', others use 'key' or 'name'
                    if loc_type == 'countries':
                        key = str(loc.get('country_code') or loc.get('key') or loc.get('name') or '')
                        name = loc.get('name') or key
                    else:
                        key = str(loc.get('key') or loc.get('id') or loc.get('name') or '')
                        name = loc.get('name') or key
                    if key and key not in seen_loc_keys:
                        seen_loc_keys.add(key)
                        historical_locations.append({
                            'key': key,
                            'name': name,
                            'type': loc_type,
                            'country_code': loc.get('country_code', ''),
                            'region': loc.get('region', ''),
                        })
            # Interests from flexible_spec AND targeting_optimization (targeting_relaxation)
            for spec in (tgt.get('flexible_spec') or []) + (tgt.get('exclusions') and [] or []):
                for it in (spec.get('interests') or []):
                    iid = str(it.get('id') or it.get('name') or '')
                    if iid and iid not in seen_int_ids:
                        seen_int_ids.add(iid)
                        historical_interests.append({
                            'id': it.get('id', ''),
                            'name': it.get('name', ''),
                            'from_history': True,
                        })
            # Ages
            if tgt.get('age_min') or tgt.get('age_max'):
                historical_ages.append({'age_min': tgt.get('age_min', 18), 'age_max': tgt.get('age_max', 65), 'genders': tgt.get('genders', [])})
    except Exception:
        pass

    # 4. Historical ad links and copy — fetch ad creatives with full fields
    links = []
    historical_copies: list[str] = []
    try:
        access_token = get_meta_access_token()
        params = {
            'fields': 'name,creative{object_story_spec,link_url,body,title,call_to_action_type}',
            'limit': '40',
            'access_token': access_token,
        }
        url = f"https://graph.facebook.com/{cfg['graph_api_version']}/{ad_account_id}/ads?{urllib.parse.urlencode(params)}"
        ads_r = graph_get(url)
        seen_links: set = set()
        for ad in (ads_r.get('data') or []):
            cr = ad.get('creative') or {}
            spec = cr.get('object_story_spec') or {}
            link_data = spec.get('link_data') or {}
            link = link_data.get('link') or spec.get('page_welcome_message', {}).get('landing_page_url') or cr.get('link_url') or ''
            body = link_data.get('message') or link_data.get('description') or cr.get('body') or ''
            title = link_data.get('name') or cr.get('title') or ''
            if link and link not in seen_links:
                seen_links.add(link)
                links.append({'url': link, 'ad_name': ad.get('name', ''), 'title': title, 'cta': cr.get('call_to_action_type', '')})
            if body and len(historical_copies) < 5:
                historical_copies.append(f'[{ad.get("name","")}]: {body[:200]}')
    except Exception:
        pass

    # 5. Interest search — first use relevant keywords, skip if already have from history
    new_interests: list[dict] = []
    new_seen: set = set(i.get('id', i.get('name', '')) for i in historical_interests)
    kw_sources = [product, profile.get('key_products', ''), profile.get('target_audience', '')]
    for kw in kw_sources:
        for word in (kw or '').replace(',', ' ').split():
            if len(word) < 4:
                continue
            try:
                ir = fetch_targeting_search(cfg, query=word[:60], ad_account_id=ad_account_id, limit='8')
                for item in (ir.get('data') or []):
                    iid = str(item.get('id') or '')
                    if iid and iid not in new_seen:
                        new_seen.add(iid)
                        new_interests.append({
                            'id': iid, 'name': item.get('name', ''),
                            'audience_size_upper_bound': item.get('audience_size_upper_bound', 0),
                            'from_history': False,
                        })
            except Exception:
                pass
            if len(new_interests) >= 15:
                break
        if len(new_interests) >= 15:
            break

    # Combine: history first, then new Meta suggestions
    all_interests = historical_interests[:10] + new_interests[:15]

    # 6. Best demographic from history
    best_age = historical_ages[0] if historical_ages else {'age_min': 25, 'age_max': 55, 'genders': []}

    # 7. AI recommendation — rich context
    top_demos = mem.get('top_demographics', [])[:3]
    best_results = mem.get('best_known_results', {})
    top_camps = mem.get('top_campaign_names', [])[:4]
    icp = profile.get('icp_onboarding_text', '') or ''
    brand_desc = profile.get('description', '') or ''
    tone = profile.get('tone', 'profissional')
    best_offer = profile.get('best_offer', '')
    ref_style = profile.get('reference_style_prompt', '')

    prompt = (
        'Você é um gestor de tráfego e copywriter especialista em Meta Ads. '
        'Gere uma recomendação completa de campanha com copy de alta conversão. '
        'A copy DEVE usar o tom da marca, falar diretamente com o público-alvo, ter um gancho forte, '
        'destacar a proposta de valor e terminar com CTA claro. NÃO use texto genérico. '
        'Retorne SOMENTE JSON válido com estas chaves exatas:\n'
        '{\n'
        '  "campaign_name": "nome descritivo da campanha",\n'
        '  "headline": "título curto e impactante (máx 40 chars)",\n'
        '  "primary_text": "texto principal do anúncio (3-5 parágrafos, gancho + contexto + prova + CTA, tom da marca)",\n'
        '  "description": "descrição curta (máx 25 chars)",\n'
        '  "cta": "SIGN_UP ou LEARN_MORE ou SHOP_NOW ou GET_QUOTE ou SUBSCRIBE ou DOWNLOAD",\n'
        '  "age_min": 18,\n'
        '  "age_max": 65,\n'
        '  "genders": [] ou [1] masculino ou [2] feminino,\n'
        '  "interests_selected": ["nome1","nome2",...] (máx 5, da lista disponível — prefira os já usados),\n'
        '  "location_suggested": "cidade ou estado ou país sugerido",\n'
        '  "budget_daily": 50,\n'
        '  "targeting_summary": "resumo do público em 1 linha",\n'
        '  "why": "justificativa das escolhas baseada em dados históricos (3-4 frases)"\n'
        '}\n\n'
        f'=== PRODUTO/SERVIÇO ===\n{product}\n\n'
        f'=== MARCA ===\n{brand_desc}\nTom de voz: {tone}\nOferta principal: {best_offer}\n\n'
        f'=== PÚBLICO IDEAL (ICP) ===\n{icp[:600]}\n\n'
        f'=== OBJETIVO DA CAMPANHA ===\n{objective_label_pt(objective)}\n\n'
        f'=== HISTÓRICO DA CONTA ===\n'
        f'Melhores campanhas: {top_camps}\n'
        f'Melhores resultados: {best_results}\n'
        f'Melhor demografia: {top_demos}\n'
        f'Faixa etária já usada: {best_age}\n\n'
        f'=== COPIES JÁ USADAS (referência de estilo) ===\n'
        + ('\n'.join(historical_copies[:3]) if historical_copies else 'Nenhuma no histórico') + '\n\n'
        f'=== INTERESSES DISPONÍVEIS ===\n'
        f'Já usados na conta: {[i["name"] for i in historical_interests[:10]]}\n'
        f'Sugestões Meta: {[i["name"] for i in new_interests[:10]]}\n\n'
        f'=== LOCALIZAÇÕES JÁ USADAS ===\n{[l["name"] for l in historical_locations[:10]]}\n\n'
        f'=== FORMULÁRIOS DISPONÍVEIS ===\n{[f.get("name","") for f in forms[:5]]}\n'
        f'=== PIXELS ===\n{[p.get("name","") for p in pixels[:3]]}\n'
        + (f'\n=== SÍNTESE VISUAL ===\n{ref_style[:300]}\n' if ref_style else '')
    )
    try:
        res = _ai_generate_text('campaign_analysis', prompt, 90, json_mode=True)
        suggestion = _extract_json_block(res.get('text') or '')
    except Exception:
        suggestion = {}

    return {
        'ok': True,
        'suggestion': suggestion if isinstance(suggestion, dict) else {},
        'interests': all_interests,
        'historical_interests': historical_interests,
        'new_interests': new_interests,
        'historical_locations': historical_locations[:20],
        'forms': forms,
        'links': links[:20],
        'pixels': pixels,
        'best_age': best_age,
        'account_memory': {
            'top_campaigns': top_camps,
            'top_demographics': top_demos,
            'best_results': best_results,
        },
    }


@app.post('/panel/ad-builder-ai')
async def panel_ad_builder_ai(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not user:
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    body = await request.json()
    ad_account_id = normalize_ad_account_id(body.get('ad_account_id', ''))
    ad_builder_page_id = str(body.get('page_id', '') or '')
    objective = body.get('objective', 'OUTCOME_SALES')
    destination = (body.get('destination') or 'website').strip().lower()
    briefing_text = (body.get('briefing') or '').strip()
    product = (body.get('product_name') or '').strip()
    offer = (body.get('offer') or '').strip()
    page_name = (body.get('page_name') or '').strip()
    location = (body.get('location') or '').strip()
    audience_hint = (body.get('audience_hint') or '').strip()
    link = (body.get('link') or '').strip()
    whatsapp = (body.get('whatsapp') or '').strip()
    gender = (body.get('gender') or '').strip().lower()
    age_min = int(body.get('age_min', 21) or 21)
    age_max = int(body.get('age_max', 65) or 65)
    mem = (load_ad_account_memory() or {}).get(ad_account_id, {}) if ad_account_id else {}
    top_campaigns = '; '.join(mem.get('top_campaign_names', [])[:6])
    objective_labels = ', '.join(mem.get('objective_labels', [])[:6])
    objective_mix = ', '.join([f"{k}: {v}" for k, v in (mem.get('objective_mix') or {}).items()][:8])
    best_results = ', '.join([f"{k}: {v}" for k, v in (mem.get('best_known_results') or {}).items() if str(v) not in ('0', '0.0', '')][:8])
    top_demo = '; '.join([f"{(d or {}).get('age','?')}/{(d or {}).get('gender','?')} spend={(d or {}).get('spend','0')} ctr={(d or {}).get('ctr','0')}" for d in (mem.get('top_demographics') or [])[:5]])

    objective_config = {
        'OUTCOME_LEADS': {'optimization_goal': 'LEAD_GENERATION', 'billing_event': 'IMPRESSIONS', 'cta': 'SIGN_UP'},
        'OUTCOME_TRAFFIC': {'optimization_goal': 'LINK_CLICKS', 'billing_event': 'IMPRESSIONS', 'cta': 'LEARN_MORE'},
        'OUTCOME_SALES': {'optimization_goal': 'OFFSITE_CONVERSIONS', 'billing_event': 'IMPRESSIONS', 'cta': 'SHOP_NOW'},
        'OUTCOME_ENGAGEMENT': {'optimization_goal': 'POST_ENGAGEMENT', 'billing_event': 'IMPRESSIONS', 'cta': 'LEARN_MORE'},
        'OUTCOME_AWARENESS': {'optimization_goal': 'REACH', 'billing_event': 'IMPRESSIONS', 'cta': 'LEARN_MORE'},
    }.get(objective, {'optimization_goal': 'LINK_CLICKS', 'billing_event': 'IMPRESSIONS', 'cta': 'LEARN_MORE'})

    if objective == 'OUTCOME_LEADS' and destination in ['whatsapp', 'instagram', 'messenger']:
        objective_config = {'optimization_goal': 'CONVERSATIONS', 'billing_event': 'IMPRESSIONS', 'cta': 'SEND_MESSAGE' if destination != 'whatsapp' else 'WHATSAPP_MESSAGE'}

    briefing = (
        f"Conta: {ad_account_id}. Página/base: {page_name}. Objetivo: {objective_label_pt(objective)}. Destino: {destination}. Briefing principal: {briefing_text}. Produto/oferta: {product}. Oferta: {offer}. "
        f"Localização: {location}. Público: {audience_hint}. Link/destino: {link}. WhatsApp: {whatsapp}. Faixa etária: {age_min}-{age_max}. Gênero: {gender or 'todos'}. "
        f"Histórico da conta: campanhas com melhor memória = {top_campaigns}. Objetivos históricos = {objective_labels}. Mix histórico = {objective_mix}. "
        f"Melhores sinais de resultado conhecidos = {best_results}. Demografia forte observada = {top_demo}. "
        f"Use o briefing principal como base prioritária para gerar copy e prompt visual, tentando se aproximar do que mais performou nessa conta, sem repetir texto antigo literalmente. "
        f"Também devolva sugestões de interesses/tópicos compatíveis com segmentação Meta para esse objetivo e destino."
    )
    ai = generate_ai_copy_and_prompt(briefing, page_id=ad_builder_page_id)

    raw_interest_terms = []
    for source in [audience_hint, product, offer, location]:
        if source:
            raw_interest_terms.extend([x.strip() for x in source.replace(';', ',').split(',') if x.strip()])
    suggested_interests = []
    seen = set()
    for item in raw_interest_terms:
        norm = item.lower()
        if norm in seen:
            continue
        seen.add(norm)
        suggested_interests.append(item)
    suggested_interests = suggested_interests[:12]

    targeting = _ad_builder_default_targeting(location, suggested_interests, gender, age_min, age_max)
    return {
        'ok': True,
        'ad_account_id': ad_account_id,
        'objective': objective,
        'objective_label': objective_label_pt(objective),
        'destination': destination,
        'memory': mem,
        'suggested_copy': ai.get('copy', ''),
        'suggested_image_prompt': ai.get('image_prompt', ''),
        'provider': ai.get('provider', ''),
        'suggested_interests': suggested_interests,
        'suggested_targeting': targeting,
        'objective_config': objective_config,
        'suggested_destination': destination,
        'link_required': destination in ['website'],
        'whatsapp_required': destination == 'whatsapp',
    }




@app.get('/panel/profile-growth')
def panel_profile_growth(request: Request, profile_key: str = '', panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    db = load_profile_followers_daily()
    items = db.get(profile_key, []) if isinstance(db.get(profile_key, []), list) else []
    current = items[-1]['followers_count'] if items else 0
    return {'ok': True, 'profile_key': profile_key, 'growth': followers_growth_summary(profile_key, current)}


@app.get('/panel/ads-report-history')
def panel_ads_report_history(request: Request, ad_account_id: str = '', panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not user:
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    ad_account_id = normalize_ad_account_id(ad_account_id)
    if not ad_account_allowed_for_user(user, ad_account_id):
        return JSONResponse({'ok': False, 'error': 'forbidden_ad_account'}, status_code=403)
    db = load_ads_reports_history()
    return {'ok': True, 'ad_account_id': ad_account_id, 'reports': (db or {}).get(ad_account_id, [])[-20:]}


@app.post('/panel/ad-builder-upload-image')
async def panel_ad_builder_upload_image(request: Request, file: UploadFile = File(...), panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not user:
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    return await studio_upload_image(file)


@app.post('/panel/ad-builder-generate-image')
async def panel_ad_builder_generate_image(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not user:
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    body = await request.json()
    prompt = (body.get('image_prompt') or '').strip()
    page_id = str(body.get('page_id', '') or '')
    plan_id = str(body.get('plan_id', '') or '')
    post_id = str(body.get('post_id', '') or '')
    item_type = str(body.get('item_type', '') or 'adbuilder')
    if not prompt:
        return JSONResponse({'ok': False, 'error': 'missing_image_prompt'}, status_code=400)
    cfg = load_config()
    try:
        ref_paths = None
        if page_id:
            p_prof = get_brand_profile(page_id)
            gallery = list(p_prof.get('gallery_references') or [])
            gallery_matches = _select_gallery_refs_for_briefing(gallery, prompt)
            style_refs = _get_style_ref_paths(page_id, max_refs=2)
            combined = style_refs + [p for p in gallery_matches if p not in style_refs]
            ref_paths = combined[:4] if combined else None
        image = generate_image_asset(cfg, prompt, prefix='adbuilder', ref_image_paths=ref_paths)
        original_local = image.get('requested_output') or image.get('path') or ''
        local_path = original_local
        if local_path and page_id:
            profile = get_brand_profile(page_id)
            logo_dark = str(profile.get('logo_path', '') or '')
            logo_light = str(profile.get('logo_light_path', '') or '')
            if logo_dark or logo_light:
                overlaid = _apply_logo_smart(local_path, logo_dark, logo_light)
                if overlaid:
                    local_path = overlaid
        # Always rebuild public_url from final local_path (logo overlay may change the file)
        public_url = publish_generated_file(cfg, local_path) if local_path else ''
        if not public_url:
            public_url = image.get('public_url', '')
        log_ai_usage('image_generation', image.get('provider', ''), image.get('model', ''), image.get('usage', {}), image.get('cost_usd', 0.0), page_id=page_id, plan_id=plan_id, post_id=post_id or image.get('post_id', ''), item_type=item_type)
        return {'ok': True, 'image': image, 'local_path': local_path, 'public_url': public_url, 'provider': image.get('provider', ''), 'model': image.get('model', ''), 'cost_usd': image.get('cost_usd', 0.0)}
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'image_generation_failed', 'detail': str(e)}, status_code=400)


@app.get('/panel/ad-builder-assets')
def panel_ad_builder_assets(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not user:
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    pages_payload = panel_pages(panel_auth=panel_auth, panel_user=panel_user)
    pages = pages_payload.get('pages', []) if isinstance(pages_payload, dict) else []
    channels = []
    for p in pages:
        ig = (p.get('instagram_business_account') or {}) if isinstance(p, dict) else {}
        page_id = str((p or {}).get('id', '') or '')
        if page_id:
            channels.append({'type': 'messenger', 'page_id': page_id, 'page_name': p.get('name', ''), 'label': f"Messenger · {p.get('name','Página')}"})
        if ig.get('id'):
            channels.append({'type': 'instagram', 'page_id': page_id, 'ig_user_id': ig.get('id'), 'username': ig.get('username', ''), 'label': f"Instagram Direct · @{ig.get('username','') or ig.get('id','')}"})
    return {'ok': True, 'pages': pages, 'channels': channels}


@app.post('/meta/ad-drafts/activate')
async def meta_ad_draft_activate(request: Request):
    cfg = load_config()
    body = await request.json()
    try:
        result = {}
        if body.get('campaign_id'):
            result['campaign'] = update_meta_object(cfg, body.get('campaign_id', ''), {'status': 'ACTIVE'})
        if body.get('adset_id'):
            result['adset'] = update_meta_object(cfg, body.get('adset_id', ''), {'status': 'ACTIVE'})
        if body.get('ad_id'):
            result['ad'] = update_meta_object(cfg, body.get('ad_id', ''), {'status': 'ACTIVE'})
        return {'ok': True, 'result': result}
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': body}, status_code=400)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'ad_activate_failed', 'detail': str(e)}, status_code=400)


@app.post('/meta/ad-drafts/update-budget')
async def meta_ad_draft_update_budget(request: Request):
    cfg = load_config()
    body = await request.json()
    try:
        adset_id = body.get('adset_id', '')
        daily_budget = str(body.get('daily_budget', '') or '')
        if not adset_id or not daily_budget:
            return JSONResponse({'ok': False, 'error': 'missing_adset_id_or_daily_budget'}, status_code=400)
        result = update_meta_object(cfg, adset_id, {'daily_budget': daily_budget})
        return {'ok': True, 'result': result}
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': body}, status_code=400)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'ad_budget_update_failed', 'detail': str(e)}, status_code=400)


@app.post('/meta/ad-drafts/pause')
async def meta_ad_draft_pause(request: Request):
    cfg = load_config()
    body = await request.json()
    try:
        result = {}
        if body.get('campaign_id'):
            result['campaign'] = update_meta_object(cfg, body.get('campaign_id', ''), {'status': 'PAUSED'})
        if body.get('adset_id'):
            result['adset'] = update_meta_object(cfg, body.get('adset_id', ''), {'status': 'PAUSED'})
        if body.get('ad_id'):
            result['ad'] = update_meta_object(cfg, body.get('ad_id', ''), {'status': 'PAUSED'})
        return {'ok': True, 'result': result}
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': body}, status_code=400)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'ad_pause_failed', 'detail': str(e)}, status_code=400)


@app.get('/meta/page-posts')
def meta_page_posts(page_id: str = ''):
    cfg = load_config()
    if not page_id:
        return JSONResponse({'ok': False, 'error': 'missing_page_id'}, status_code=400)
    try:
        posts = fetch_page_posts(cfg, page_id)
        return {'ok': True, 'page_id': page_id, 'posts': posts.get('data', [])}
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': body}, status_code=400)


@app.post('/meta/page-posts/create')
async def meta_page_posts_create(request: Request):
    cfg = load_config()
    body = await request.json()
    try:
        page_id = body.get('page_id', '')
        message = body.get('message', '')
        link = body.get('link', '')
        published = str(body.get('published', 'true')).lower()
        scheduled_publish_time = str(body.get('scheduled_publish_time', '') or '')
        result = create_page_post(cfg, page_id, message, link, published, scheduled_publish_time)
        return {'ok': True, 'result': result}
    except urllib.error.HTTPError as e:
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': e.read().decode('utf-8', errors='replace')}, status_code=400)


@app.post('/meta/page-posts/create-photo')
async def meta_page_posts_create_photo(request: Request):
    cfg = load_config()
    body = await request.json()
    try:
        result = create_page_photo_post(
            cfg,
            body.get('page_id', ''),
            body.get('image_url', ''),
            body.get('caption', ''),
            str(body.get('published', 'true')).lower(),
            str(body.get('scheduled_publish_time', '') or ''),
        )
        return {'ok': True, 'result': result}
    except urllib.error.HTTPError as e:
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': e.read().decode('utf-8', errors='replace')}, status_code=400)


@app.post('/meta/page-posts/update')
async def meta_page_posts_update(request: Request):
    cfg = load_config()
    body = await request.json()
    try:
        result = update_page_post(cfg, body.get('post_id', ''), body.get('message', ''))
        return {'ok': True, 'result': result}
    except urllib.error.HTTPError as e:
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': e.read().decode('utf-8', errors='replace')}, status_code=400)


@app.post('/meta/page-posts/delete')
async def meta_page_posts_delete(request: Request):
    cfg = load_config()
    body = await request.json()
    try:
        result = delete_page_post(cfg, body.get('post_id', ''))
        return {'ok': True, 'result': result}
    except urllib.error.HTTPError as e:
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': e.read().decode('utf-8', errors='replace')}, status_code=400)


@app.post('/meta/ai-post')
async def meta_ai_post(request: Request):
    cfg = load_config()
    body = await request.json()
    description = body.get('description', '')
    page_id = body.get('page_id', '')
    scheduled_publish_time = str(body.get('scheduled_publish_time', '') or '')
    publish_now = bool(body.get('publish_now', True))
    publish = 'true' if publish_now and not scheduled_publish_time else 'false'
    try:
        generated = generate_ai_copy_and_prompt(description, page_id=str(page_id or ''))
        image = generate_image_local(generated['image_prompt'])
        image_path = image.get('path', '')
        image_url = body.get('image_url', '')
        if not image_url and image_path:
            image_url = publish_generated_file(cfg, image_path)
        result = {
            'generated': generated,
            'image': image,
        }
        if page_id:
            if image_url:
                post_result = create_page_photo_post(cfg, page_id, image_url, generated['copy'], publish, scheduled_publish_time)
            else:
                post_result = create_page_post(cfg, page_id, generated['copy'], '', publish, scheduled_publish_time)
            result['post_result'] = post_result
        with AI_POST_RUNS_PATH.open('a') as f:
            f.write(json.dumps({'description': description, 'page_id': page_id, 'scheduled_publish_time': scheduled_publish_time, 'publish_now': publish_now, 'result': result}, ensure_ascii=False) + '\n')
        return {'ok': True, **result}
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'ai_post_failed', 'detail': str(e)}, status_code=400)


@app.post('/meta/instagram-media/create')
async def meta_instagram_media_create(request: Request):
    cfg = load_config()
    body = await request.json()
    admin_token = body.get('admin_token', '')
    if not admin_token or admin_token != get_secret(PANEL_ADMIN_TOKEN_NAME):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    try:
        ig_user_id = body.get('ig_user_id', '')
        image_url = body.get('image_url', '')
        caption = body.get('caption', '')
        access_token = body.get('access_token', '')
        if not ig_user_id or not image_url or not access_token:
            return JSONResponse({'ok': False, 'error': 'missing_params'}, status_code=400)
        result = instagram_create_media(cfg, ig_user_id, access_token, image_url, caption)
        print(f"DEBUG create media result: {result}")
        if 'error' in result:
             # Just return what Graph API returns and let the client handle it
             return JSONResponse({'ok': False, 'error': 'media_create_failed', 'detail': result['error']}, status_code=400)
        return {'ok': True, 'result': result}
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': body}, status_code=400)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'media_create_failed', 'detail': str(e)}, status_code=400)


@app.post('/meta/instagram-media/publish')
async def meta_instagram_media_publish(request: Request):
    cfg = load_config()
    body = await request.json()
    admin_token = body.get('admin_token', '')
    if not admin_token or admin_token != get_secret(PANEL_ADMIN_TOKEN_NAME):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    try:
        ig_user_id = body.get('ig_user_id', '')
        creation_id = body.get('creation_id', '')
        access_token = body.get('access_token', '')
        if not ig_user_id or not creation_id or not access_token:
            return JSONResponse({'ok': False, 'error': 'missing_params'}, status_code=400)
        result = instagram_publish_media(cfg, ig_user_id, access_token, creation_id)
        return {'ok': True, 'result': result}
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': body}, status_code=400)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'media_publish_failed', 'detail': str(e)}, status_code=400)



@app.get('/instagram/session')
def instagram_session_info():
    session = get_instagram_direct_session()
    token = session.get('access_token', '')
    return {
        'ok': True,
        'connected': bool(token),
        'user_id': session.get('user_id'),
        'permissions': session.get('permissions', []),
        'token_masked': (('*' * max(len(token) - 6, 0)) + token[-6:]) if token else '',
    }


@app.get('/instagram-web/accounts')
def instagram_web_accounts():
    return {'ok': True, **load_instagram_web_accounts()}


@app.get('/instagram-browser/accounts')
def instagram_browser_accounts():
    return {'ok': True, **load_instagram_browser_accounts()}


@app.get('/instagram-browser/register')
def instagram_browser_register(account_key: str = '', username: str = '', note: str = ''):
    if not account_key:
        return JSONResponse({'ok': False, 'error': 'missing_account_key'}, status_code=400)
    account = upsert_instagram_browser_account(account_key, username, note)
    try:
        init_result = run_instagram_browser_runner(['init', account_key])
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'instagram_browser_init_failed', 'detail': str(e)}, status_code=400)
    return {'ok': True, 'account': account, 'init_result': init_result}


@app.post('/instagram-browser/login-ui')
def instagram_browser_login_ui(account_key: str = Form(...), username: str = Form(...), password: str = Form(...), note: str = Form('')):
    try:
        account = upsert_instagram_browser_account(account_key.strip(), username.strip(), note.strip())
        job = create_instagram_browser_job('login', account_key.strip(), ['login', account_key.strip(), username.strip(), password])
        return HTMLResponse(f"<html><body style='font-family:Arial,sans-serif;margin:40px'><h1>Instagram Browser Login Started</h1><pre>{json.dumps({'account': account, 'job': job}, ensure_ascii=False, indent=2)}</pre><p><a href='/instagram-browser/job-status?job_id={job['job_id']}'>Ver status do job</a></p><p><a href='/'>Voltar</a></p></body></html>")
    except Exception as e:
        return HTMLResponse(f"<html><body style='font-family:Arial,sans-serif;margin:40px'><h1>Instagram Browser Login Error</h1><pre>{str(e)}</pre><p><a href='/'>Voltar</a></p></body></html>", status_code=400)


@app.post('/instagram-browser/login-2fa-ui')
def instagram_browser_login_2fa_ui(account_key: str = Form(...), username: str = Form(...), password: str = Form(...), code: str = Form(...)):
    try:
        job = create_instagram_browser_job('login-2fa', account_key.strip(), ['login-2fa', account_key.strip(), username.strip(), password, code.strip()])
        return HTMLResponse(f"<html><body style='font-family:Arial,sans-serif;margin:40px'><h1>Instagram Browser 2FA Started</h1><pre>{json.dumps({'job': job}, ensure_ascii=False, indent=2)}</pre><p><a href='/instagram-browser/job-status?job_id={job['job_id']}'>Ver status do job</a></p><p><a href='/'>Voltar</a></p></body></html>")
    except Exception as e:
        return HTMLResponse(f"<html><body style='font-family:Arial,sans-serif;margin:40px'><h1>Instagram Browser 2FA Error</h1><pre>{str(e)}</pre><p><a href='/'>Voltar</a></p></body></html>", status_code=400)


@app.get('/instagram-browser/cookie-status')
def instagram_browser_cookie_status(account_key: str = ''):
    if not account_key:
        return JSONResponse({'ok': False, 'error': 'missing_account_key'}, status_code=400)
    try:
        result = run_instagram_browser_runner(['cookie-status', account_key])
        return {'ok': True, 'result': result}
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'instagram_browser_cookie_status_failed', 'detail': str(e)}, status_code=400)


@app.get('/instagram-browser/job-status')
def instagram_browser_job_status(job_id: str = ''):
    if not job_id:
        return JSONResponse({'ok': False, 'error': 'missing_job_id'}, status_code=400)
    job = get_instagram_browser_job(job_id)
    if not job:
        return JSONResponse({'ok': False, 'error': 'job_not_found'}, status_code=404)
    log_text = ''
    try:
        if Path(job.get('log_path', '')).exists():
            log_text = Path(job['log_path']).read_text()[-8000:]
    except Exception:
        pass
    return {'ok': True, 'job': job, 'log_tail': log_text}


@app.get('/instagram-browser/post-image')
def instagram_browser_post_image(account_key: str = '', image_path: str = '', caption: str = ''):
    if not account_key or not image_path:
        return JSONResponse({'ok': False, 'error': 'missing_account_key_or_image_path'}, status_code=400)
    try:
        normalized_path = ensure_local_jpeg(urllib.parse.unquote(image_path))
        job = create_instagram_browser_job('post', account_key, ['post', account_key, normalized_path, caption])
        return {'ok': True, 'image_path_used': normalized_path, 'job': job}
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'instagram_browser_post_failed', 'detail': str(e)}, status_code=400)


@app.get('/instagram-web/cookie-status')
def instagram_web_cookie_status(account_key: str = ''):
    if not account_key:
        return JSONResponse({'ok': False, 'error': 'missing_account_key'}, status_code=400)
    try:
        result = run_instagram_web_runner(['cookie-status', account_key])
        return {'ok': True, 'result': result}
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'cookie_status_failed', 'detail': str(e)}, status_code=400)


@app.get('/instagram-web/profile')
def instagram_web_profile(account_key: str = ''):
    if not account_key:
        return JSONResponse({'ok': False, 'error': 'missing_account_key'}, status_code=400)
    try:
        result = run_instagram_web_runner(['profile', account_key])
        return {'ok': True, 'result': result}
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'instagram_web_profile_failed', 'detail': str(e)}, status_code=400)


@app.get('/instagram-web/register')
def instagram_web_register(account_key: str = '', username: str = '', note: str = ''):
    if not account_key:
        return JSONResponse({'ok': False, 'error': 'missing_account_key'}, status_code=400)
    account = upsert_instagram_web_account(account_key, username, note)
    return {'ok': True, 'account': account}


@app.post('/instagram-web/login-ui')
def instagram_web_login_ui(account_key: str = Form(...), username: str = Form(...), password: str = Form(...), note: str = Form('')):
    try:
        account = upsert_instagram_web_account(account_key.strip(), username.strip(), note.strip())
        result = run_instagram_web_runner(['login', account_key.strip(), username.strip(), password])
        return HTMLResponse(f"<html><body style='font-family:Arial,sans-serif;margin:40px'><h1>Instagram Web Login</h1><pre>{json.dumps({'account': account, 'result': result}, ensure_ascii=False, indent=2)}</pre><p><a href='/'>Voltar</a></p></body></html>")
    except Exception as e:
        return HTMLResponse(f"<html><body style='font-family:Arial,sans-serif;margin:40px'><h1>Instagram Web Login Error</h1><pre>{str(e)}</pre><p><a href='/'>Voltar</a></p></body></html>", status_code=400)


@app.get('/instagram-web/post-image')
def instagram_web_post_image(account_key: str = '', image_path: str = '', caption: str = ''):
    if not account_key or not image_path:
        return JSONResponse({'ok': False, 'error': 'missing_account_key_or_image_path'}, status_code=400)
    try:
        normalized_path = ensure_local_jpeg(urllib.parse.unquote(image_path))
        result = run_instagram_web_runner(['post', account_key, normalized_path, caption])
        return {'ok': True, 'image_path_used': normalized_path, 'result': result}
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'instagram_web_post_failed', 'detail': str(e)}, status_code=400)


@app.get('/x/connect/start')
def x_connect_start():
    cfg = load_config()
    client_id = get_secret(X_CLIENT_ID_NAME) or cfg.get('x_client_id', '')
    if not client_id:
        return JSONResponse({'ok': False, 'error': 'missing_x_client_id'}, status_code=400)
    redirect_uri = cfg['public_base_url'].rstrip('/') + X_REDIRECT_PATH
    scopes = (cfg.get('x_scopes') or 'tweet.read tweet.write users.read offline.access').strip()
    params = urllib.parse.urlencode({
        'response_type': 'code',
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'scope': scopes,
        'state': 'x',
        'code_challenge': 'challenge',
        'code_challenge_method': 'plain'
    })
    return RedirectResponse(f"https://twitter.com/i/oauth2/authorize?{params}")


@app.get('/x/connect/callback')
def x_connect_callback(code: str = '', state: str = '', error: str = '', error_description: str = ''):
    cfg = load_config()
    if error:
        return JSONResponse({'ok': False, 'error': error, 'detail': error_description}, status_code=400)
    if not code:
        return JSONResponse({'ok': False, 'error': 'missing_code'}, status_code=400)
    client_id = get_secret(X_CLIENT_ID_NAME) or cfg.get('x_client_id', '')
    client_secret = get_secret(X_CLIENT_SECRET_NAME) or cfg.get('x_client_secret', '')
    if not client_id or not client_secret:
        return JSONResponse({'ok': False, 'error': 'missing_x_client_credentials'}, status_code=400)
    redirect_uri = cfg['public_base_url'].rstrip('/') + X_REDIRECT_PATH
    token_payload = urllib.parse.urlencode({
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri,
        'client_id': client_id,
        'code_verifier': 'challenge',
    }).encode('utf-8')
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode('utf-8')).decode('ascii')
    req = urllib.request.Request('https://api.twitter.com/2/oauth2/token', data=token_payload, headers={
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': f'Basic {basic}',
        'User-Agent': 'meta-connection-panel/1.0',
    })
    with urllib.request.urlopen(req, timeout=60) as resp:
        token_data = json.loads(resp.read().decode('utf-8'))
    token_data['state'] = state
    save_json(X_SESSION_PATH, token_data)
    return {'ok': True, 'saved': True, 'token': {k: token_data.get(k) for k in ['token_type', 'expires_in', 'scope']}}


@app.get('/x/session')
def x_session_status():
    session = get_x_session()
    return {'ok': True, 'connected': bool(session.get('access_token')), 'session': session}


@app.get('/x/me')
def x_me():
    token = get_x_access_token()
    if not token:
        return JSONResponse({'ok': False, 'error': 'missing_x_access_token'}, status_code=400)
    req = urllib.request.Request('https://api.twitter.com/2/users/me', headers={
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json',
        'User-Agent': 'meta-connection-panel/1.0',
    })
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    session = get_x_session()
    session['me'] = data
    save_json(X_SESSION_PATH, session)
    return {'ok': True, 'me': data}


@app.post('/x/post')
async def x_post(request: Request):
    body = await request.json()
    text = (body.get('text', '') or '').strip()
    if not text:
        return JSONResponse({'ok': False, 'error': 'missing_text'}, status_code=400)
    token = get_x_access_token()
    if not token:
        return JSONResponse({'ok': False, 'error': 'missing_x_access_token'}, status_code=400)
    payload = {'text': text}
    req = urllib.request.Request('https://api.twitter.com/2/tweets', data=json.dumps(payload).encode('utf-8'), headers={
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'User-Agent': 'meta-connection-panel/1.0',
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode('utf-8'))
        return {'ok': True, 'request': payload, 'result': result}
    except urllib.error.HTTPError as e:
        detail = e.read().decode('utf-8', errors='replace')
        return JSONResponse({'ok': False, 'error': 'x_post_failed', 'status_code': e.code, 'detail': detail, 'request': payload}, status_code=400 if e.code < 500 else 502)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'x_post_failed', 'detail': str(e), 'request': payload}, status_code=400)


@app.get('/linkedin/connect/start')
def linkedin_connect_start():
    cfg = load_config()
    client_id = get_secret(LINKEDIN_CLIENT_ID_NAME) or cfg.get('linkedin_client_id', '')
    if not client_id:
        return JSONResponse({'ok': False, 'error': 'missing_linkedin_client_id'}, status_code=400)
    redirect_uri = cfg['public_base_url'].rstrip('/') + LINKEDIN_REDIRECT_PATH
    scopes = 'openid profile email w_member_social'
    params = urllib.parse.urlencode({
        'response_type': 'code',
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'scope': scopes,
        'state': 'linkedin'
    })
    return RedirectResponse(f"https://www.linkedin.com/oauth/v2/authorization?{params}")


@app.get('/linkedin/connect/callback')
def linkedin_connect_callback(code: str = '', error: str = '', error_description: str = ''):
    cfg = load_config()
    if error:
        return JSONResponse({'ok': False, 'error': error, 'detail': error_description}, status_code=400)
    if not code:
        return JSONResponse({'ok': False, 'error': 'missing_code'}, status_code=400)
    client_id = get_secret(LINKEDIN_CLIENT_ID_NAME) or cfg.get('linkedin_client_id', '')
    client_secret = get_secret(LINKEDIN_CLIENT_SECRET_NAME) or cfg.get('linkedin_client_secret', '')
    if not client_id or not client_secret:
        return JSONResponse({'ok': False, 'error': 'missing_linkedin_client_credentials'}, status_code=400)
    redirect_uri = cfg['public_base_url'].rstrip('/') + LINKEDIN_REDIRECT_PATH
    data = urllib.parse.urlencode({
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri,
        'client_id': client_id,
        'client_secret': client_secret,
    }).encode('utf-8')
    req = urllib.request.Request('https://www.linkedin.com/oauth/v2/accessToken', data=data, headers={'Content-Type': 'application/x-www-form-urlencoded'})
    with urllib.request.urlopen(req, timeout=60) as resp:
        token_data = json.loads(resp.read().decode('utf-8'))
    try:
        me_req = urllib.request.Request('https://api.linkedin.com/v2/userinfo', headers={
            'Authorization': f"Bearer {token_data.get('access_token', '')}",
            'Accept': 'application/json',
            'User-Agent': 'meta-connection-panel/1.0',
        })
        with urllib.request.urlopen(me_req, timeout=60) as resp:
            me_data = json.loads(resp.read().decode('utf-8'))
        token_data['me'] = me_data
        if me_data.get('sub'):
            token_data['author_urn'] = f"urn:li:person:{me_data['sub']}"
    except Exception:
        pass
    save_json(LINKEDIN_SESSION_PATH, token_data)
    return {'ok': True, 'token': {k: token_data.get(k) for k in ['access_token', 'expires_in']}, 'saved': True}


@app.get('/linkedin/session')
def linkedin_session_status():
    session = get_linkedin_session()
    return {'ok': True, 'connected': bool(session.get('access_token')), 'session': session}


@app.get('/linkedin/debug')
def linkedin_debug():
    session = get_linkedin_session()
    token = session.get('access_token', '')
    me = session.get('me', {}) or {}
    author_urn = get_linkedin_author_urn()
    return {
        'ok': True,
        'connected': bool(token),
        'has_access_token': bool(token),
        'scopes': session.get('scope', ''),
        'expires_in': session.get('expires_in', ''),
        'token_type': session.get('token_type', ''),
        'author_urn': author_urn,
        'me_cached': me,
        'saved_keys': list(session.keys()),
        'note': 'Use /linkedin/me and /linkedin/post with Authorization: Bearer access_token.',
    }


@app.get('/linkedin/me')
def linkedin_me():
    token = get_linkedin_access_token()
    if not token:
        return JSONResponse({'ok': False, 'error': 'missing_linkedin_access_token'}, status_code=400)
    url = 'https://api.linkedin.com/v2/userinfo'
    req = urllib.request.Request(url, headers={
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json',
        'User-Agent': 'meta-connection-panel/1.0',
    })
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    session = get_linkedin_session()
    session['me'] = data
    if data.get('sub'):
        session['author_urn'] = f"urn:li:person:{data['sub']}"
    save_json(LINKEDIN_SESSION_PATH, session)
    return {'ok': True, 'me': data, 'author_urn': get_linkedin_author_urn()}


@app.get('/linkedin/author')
def linkedin_author():
    session = get_linkedin_session()
    return {'ok': True, 'author_urn': get_linkedin_author_urn(), 'session_author_urn': session.get('author_urn', ''), 'cached_me': session.get('me', {})}


@app.get('/linkedin/organizations')
def linkedin_organizations():
    token = get_linkedin_access_token()
    if not token:
        return JSONResponse({'ok': False, 'error': 'missing_linkedin_access_token'}, status_code=400)
    # LinkedIn company discovery varies by app permissions. Try the most common endpoint first.
    urls = [
        'https://api.linkedin.com/v2/organizationalEntityAcls?q=roleAssignee&role=ADMINISTRATOR',
        'https://api.linkedin.com/v2/organizationAcls?q=roleAssignee&role=ADMINISTRATOR',
    ]
    last_error = None
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={
                'Authorization': f'Bearer {token}',
                'Accept': 'application/json',
                'User-Agent': 'meta-connection-panel/1.0',
            })
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            session = get_linkedin_session()
            session['organizations'] = data
            save_json(LINKEDIN_SESSION_PATH, session)
            return {'ok': True, 'source': url, 'organizations': data}
        except Exception as e:
            last_error = str(e)
    return JSONResponse({'ok': False, 'error': 'organization_lookup_failed', 'detail': last_error}, status_code=400)


@app.post('/linkedin/post')
async def linkedin_post(request: Request):
    body = await request.json()
    text = (body.get('text', '') or '').strip()
    author_urn = (body.get('author_urn', '') or '').strip() or get_linkedin_author_urn()
    visibility = (body.get('visibility', 'PUBLIC') or 'PUBLIC').strip().upper()
    if not text:
        return JSONResponse({'ok': False, 'error': 'missing_text'}, status_code=400)
    token = get_linkedin_access_token()
    if not token:
        return JSONResponse({'ok': False, 'error': 'missing_linkedin_access_token'}, status_code=400)
    if not author_urn:
        return JSONResponse({'ok': False, 'error': 'missing_author_urn'}, status_code=400)
    payload = {
        'author': author_urn,
        'lifecycleState': 'PUBLISHED',
        'specificContent': {
            'com.linkedin.ugc.ShareContent': {
                'shareCommentary': {'text': text},
                'shareMediaCategory': 'NONE',
            }
        },
        'visibility': {'com.linkedin.ugc.MemberNetworkVisibility': visibility},
    }
    req = urllib.request.Request('https://api.linkedin.com/v2/ugcPosts', data=json.dumps(payload).encode('utf-8'), headers={
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'X-Restli-Protocol-Version': '2.0.0',
        'User-Agent': 'meta-connection-panel/1.0',
    })
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = resp.read().decode('utf-8')
    return {'ok': True, 'author_urn': author_urn, 'request': payload, 'result': json.loads(result) if result else {}}


@app.post('/linkedin/post-image')
async def linkedin_post_image(request: Request):
    body = await request.json()
    text = (body.get('text', '') or '').strip()
    author_urn = (body.get('author_urn', '') or '').strip() or get_linkedin_author_urn()
    image_url = (body.get('image_url', '') or '').strip()
    if not text or not author_urn or not image_url:
        return JSONResponse({'ok': False, 'error': 'missing_text_author_urn_or_image_url'}, status_code=400)
    token = get_linkedin_access_token()
    if not token:
        return JSONResponse({'ok': False, 'error': 'missing_linkedin_access_token'}, status_code=400)
    upload_req = urllib.request.Request('https://api.linkedin.com/v2/assets?action=registerUpload', data=json.dumps({
        'registerUploadRequest': {
            'owner': author_urn,
            'recipes': ['urn:li:digitalmediaRecipe:feedshare-image'],
            'serviceRelationships': [{
                'relationshipType': 'OWNER',
                'identifier': 'urn:li:userGeneratedContent'
            }]
        }
    }).encode('utf-8'), headers={
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'X-Restli-Protocol-Version': '2.0.0',
        'User-Agent': 'meta-connection-panel/1.0',
    })
    with urllib.request.urlopen(upload_req, timeout=60) as resp:
        reg = json.loads(resp.read().decode('utf-8'))
    return {'ok': True, 'author_urn': author_urn, 'upload': reg, 'note': 'LinkedIn image post flow still needs completion against upload URL + asset URN; this route is the MVP scaffold.'}


@app.post('/meta/image/generate')
async def meta_image_generate(request: Request):
    """
    Generate an image locally with Nano Banana and publish it under a simple public filename.
    Body: { prompt?: str, briefing?: str, post_id?: str, prefix?: str }
    If briefing is provided, AI generates copy + image_prompt from it (returns copy in response).
    If prompt is provided directly, uses it as the image prompt.
    """
    cfg = load_config()
    body = await request.json()
    briefing = (body.get('briefing', '') or '').strip()
    prompt = (body.get('prompt', '') or '').strip()
    post_id = body.get('post_id', '')
    prefix = sanitize_public_media_name(body.get('prefix', 'igpost'), fallback='igpost')
    art_direction = body.get('art_direction', {}) or {}

    ai_copy = None
    if briefing:
        ai_copy = generate_ai_copy_and_prompt(briefing, art_direction=art_direction)
        prompt = ai_copy.get('image_prompt', '') or briefing

    if not prompt:
        return JSONResponse({'ok': False, 'error': 'missing_prompt_or_briefing'}, status_code=400)
    try:
        generated = generate_image_asset(cfg, prompt, post_id=post_id, prefix=prefix)
        images = generated.get('images', [])
        first = images[0] if images else {}
        local_path = first.get('path') or generated.get('requested_output', '')
        public_url = generated.get('public_url') or (build_public_media_url(cfg, local_path, post_id=generated.get('post_id', post_id), prefix=prefix) if local_path else '')
        copy_text = (ai_copy.get('copy', '') if ai_copy else '')
        log_ai_usage('image_generation', generated.get('provider', ''), generated.get('model', ''), generated.get('usage', {}), generated.get('cost_usd', 0.0), post_id=generated.get('post_id', post_id), item_type='post')
        return {
            'ok': True,
            'prompt': prompt,
            'briefing': briefing,
            'copy': copy_text,
            'post_id': generated.get('post_id', post_id),
            'image': first,
            'local_path': local_path,
            'public_url': public_url,
            'generated': ai_copy,
            'provider': generated.get('provider', ''),
            'model': generated.get('model', ''),
            'cost_usd': generated.get('cost_usd', 0.0),
            'recommended_media_payload': {
                'image_url': public_url,
                'caption': copy_text or 'Legenda aqui',
                'post_type': 'image'
            }
        }
    except subprocess.CalledProcessError as e:
        detail = e.stderr or e.stdout or str(e)
        return JSONResponse({'ok': False, 'error': 'image_generation_failed', 'detail': detail}, status_code=400)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'image_generation_failed', 'detail': str(e)}, status_code=400)

@app.get('/meta/instagram-access-token')
def meta_instagram_access_token(page_id: str = '', ig_user_id: str = '', username: str = '', refresh: str = 'false'):
    cfg = load_config()
    try:
        if str(refresh).lower() in ['1', 'true', 'yes', 'y']:
            refresh_pages_from_general_token(cfg)
        page = get_page_record(page_id=page_id, ig_user_id=ig_user_id, username=username)
        if not page:
            return JSONResponse({'ok': False, 'error': 'instagram_account_not_found'}, status_code=404)
        ig = page.get('instagram_business_account') or {}
        page_token = page.get('access_token', '') or page.get('page_access_token', '')
        if not page_token:
            return JSONResponse({'ok': False, 'error': 'page_access_token_not_found'}, status_code=404)
        return {
            'ok': True,
            'page_id': page.get('id', ''),
            'page_name': page.get('name', ''),
            'instagram_business_account': ig,
            'access_token': page_token,
            'source': 'me/accounts',
            'hint': 'This token is the page-level token associated with the selected Instagram business account and can be used for Graph Instagram publishing flows.'
        }
    except urllib.error.HTTPError as e:
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': e.read().decode('utf-8', errors='replace')}, status_code=400)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'instagram_access_token_lookup_failed', 'detail': str(e)}, status_code=400)

@app.get('/meta/instagram-insights')
def meta_instagram_insights(username: str = '', ig_user_id: str = '', page_id: str = '', metrics: str = '', period: str = '', since: str = '', until: str = ''):
    cfg = load_config()
    target = get_instagram_account_by_username(username=username, ig_user_id=ig_user_id, page_id=page_id)
    if not target and page_id:
        session = get_meta_session_for_panel_user(panel_user or '')
        for p in (session.get('pages') or []):
            if str((p or {}).get('id', '')) == str(page_id):
                ig = (p or {}).get('instagram_business_account') or {}
                if ig and (not ig_user_id or str(ig.get('id', '')) == str(ig_user_id)):
                    target = {
                        'page_id': str((p or {}).get('id', '')),
                        'page_name': (p or {}).get('name', ''),
                        'page_access_token': (p or {}).get('access_token', ''),
                        'instagram_business_account': ig,
                    }
                    break
    if not target or not metrics:
        return JSONResponse({'ok': False, 'error': 'missing_target_or_metrics'}, status_code=400)
    try:
        ig = target['instagram_business_account']
        result = instagram_account_insights(cfg, ig.get('id', ''), target.get('page_access_token', ''), metrics, period, since, until)
        return {'ok': True, 'target': target, 'metrics': metrics, 'result': result}
    except urllib.error.HTTPError as e:
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': e.read().decode('utf-8', errors='replace')}, status_code=400)


@app.get('/meta/instagram-media-insights')
def meta_instagram_media_insights(media_id: str = '', username: str = '', ig_user_id: str = '', page_id: str = '', metrics: str = ''):
    cfg = load_config()
    target = get_instagram_account_by_username(username=username, ig_user_id=ig_user_id, page_id=page_id)
    if not target and page_id:
        session = get_meta_session_for_panel_user(panel_user or '')
        for p in (session.get('pages') or []):
            if str((p or {}).get('id', '')) == str(page_id):
                ig = (p or {}).get('instagram_business_account') or {}
                if ig and (not ig_user_id or str(ig.get('id', '')) == str(ig_user_id)):
                    target = {
                        'page_id': str((p or {}).get('id', '')),
                        'page_name': (p or {}).get('name', ''),
                        'page_access_token': (p or {}).get('access_token', ''),
                        'instagram_business_account': ig,
                    }
                    break
    if not target or not media_id or not metrics:
        return JSONResponse({'ok': False, 'error': 'missing_target_media_or_metrics'}, status_code=400)
    try:
        result = instagram_media_insights(cfg, media_id, target.get('page_access_token', ''), metrics)
        return {'ok': True, 'target': target, 'media_id': media_id, 'metrics': metrics, 'result': result}
    except urllib.error.HTTPError as e:
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': e.read().decode('utf-8', errors='replace')}, status_code=400)


@app.get('/meta/publish-existing-image')
def meta_publish_existing_image(path: str = ''):
    cfg = load_config()
    if not path:
        return JSONResponse({'ok': False, 'error': 'missing_path'}, status_code=400)
    try:
        public_url = publish_generated_file(cfg, urllib.parse.unquote(path))
        filename = public_url.rsplit('/', 1)[-1] if public_url else ''
        exists = bool(filename and (GENERATED_DIR / filename).exists())
        return {'ok': True, 'path': urllib.parse.unquote(path), 'public_url': public_url, 'exists': exists}
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'publish_existing_image_failed', 'detail': str(e)}, status_code=400)


@app.get('/meta/run-instagram-ai-post')
def meta_run_instagram_ai_post(username: str = '', ig_user_id: str = '', page_id: str = '', description: str = '', image_url: str = '', preview_only: str = 'false', mode: str = ''):
    cfg = load_config()
    direct_token = get_instagram_direct_token()
    direct_user_id = get_instagram_direct_user_id()
    target = get_instagram_account_by_username(username=username, ig_user_id=ig_user_id, page_id=page_id)
    if not target and page_id:
        session = get_meta_session_for_panel_user(panel_user or '')
        for p in (session.get('pages') or []):
            if str((p or {}).get('id', '')) == str(page_id):
                ig = (p or {}).get('instagram_business_account') or {}
                if ig and (not ig_user_id or str(ig.get('id', '')) == str(ig_user_id)):
                    target = {
                        'page_id': str((p or {}).get('id', '')),
                        'page_name': (p or {}).get('name', ''),
                        'page_access_token': (p or {}).get('access_token', ''),
                        'instagram_business_account': ig,
                    }
                    break

    if not description:
        return JSONResponse({'ok': False, 'error': 'missing_description'}, status_code=400)

    requested_mode = (mode or '').strip().lower()
    if requested_mode == 'facebook_page':
        use_direct = False
    elif requested_mode == 'instagram_direct':
        use_direct = True
    else:
        use_direct = bool(direct_user_id and direct_token)

    if use_direct:
        effective_ig_user_id = direct_user_id
        effective_token = direct_token
        effective_host = 'graph.instagram.com'
    else:
        effective_ig_user_id = (target.get('instagram_business_account', {}).get('id', '') if target else '')
        effective_token = (target.get('page_access_token', '') if target else '')
        effective_host = 'graph.facebook.com'

    if not effective_ig_user_id or not effective_token:
        return JSONResponse({'ok': False, 'error': 'missing_instagram_auth_context'}, status_code=400)

    try:
        preview_only_bool = str(preview_only).lower() in ['1', 'true', 'yes', 'y']
        generated = generate_ai_copy_and_prompt(description)
        image = {}
        image_path = ''
        final_image_url = urllib.parse.unquote(image_url).strip() if image_url else ''
        if not final_image_url:
            image = generate_image_local(generated['image_prompt'])
            image_path = image.get('path', '')
            final_image_url = publish_generated_file(cfg, image_path) if image_path else ''
        result = {
            'target': target,
            'instagram_direct_user_id': direct_user_id,
            'mode': 'instagram_direct' if use_direct else 'facebook_page',
            'generated': generated,
            'image': image,
            'image_url': final_image_url,
            'preview_only': preview_only_bool,
        }
        if not preview_only_bool and final_image_url:
            creation = instagram_create_media(cfg, effective_ig_user_id, effective_token, final_image_url, generated['copy'], host=effective_host)
            creation_id = creation.get('id', '')
            publish_result = instagram_publish_media(cfg, effective_ig_user_id, effective_token, creation_id, host=effective_host)
            result['creation'] = creation
            result['publish_result'] = publish_result
        return {'ok': True, **result}
    except urllib.error.HTTPError as e:
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': e.read().decode('utf-8', errors='replace')}, status_code=400)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'instagram_ai_post_failed', 'detail': str(e)}, status_code=400)


@app.get('/meta/page-insights')
def meta_page_insights(page_id: str = '', metrics: str = '', period: str = '', since: str = '', until: str = ''):
    cfg = load_config()
    if not page_id or not metrics:
        return JSONResponse({'ok': False, 'error': 'missing_page_id_or_metrics'}, status_code=400)
    try:
        result = fetch_page_insights(cfg, page_id, metrics, period, since, until)
        return {'ok': True, 'page_id': page_id, 'metrics': metrics, 'result': result}
    except urllib.error.HTTPError as e:
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': e.read().decode('utf-8', errors='replace')}, status_code=400)


@app.get('/meta/metrics/page-insights')
def meta_metrics_page_insights():
    return {
        'ok': True,
        'description': 'Supported metric names for the page insights endpoints. Combine the "name" values with commas when calling /meta/page-insights or /meta/post-insights.',
        'metrics': PAGE_INSIGHTS_METRICS,
        'hint': 'Example: /meta/page-insights?page_id=123&metrics=page_engagement,page_impressions',
    }


@app.get('/meta/metrics/ads')
def meta_metrics_ads():
    return {
        'ok': True,
        'description': 'Advertising metrics that the Graph API accepts when requesting /<ad>/insights, /<adset>/insights, or /<campaign>/insights.',
        'metrics': AD_INSIGHTS_METRICS,
        'hint': 'Use these names as the metric parameter on Facebook Graph insights requests (e.g. metric=impressions,clicks).',
    }

@app.get('/meta/post-insights')
def meta_post_insights(post_id: str = '', metrics: str = '', period: str = '', since: str = '', until: str = '', page_id: str = ''):
    cfg = load_config()
    if not post_id or not metrics:
        return JSONResponse({'ok': False, 'error': 'missing_post_id_or_metrics'}, status_code=400)
    try:
        result = fetch_post_insights(cfg, post_id, metrics, period, since, until, page_id)
        return {'ok': True, 'post_id': post_id, 'metrics': metrics, 'result': result}
    except urllib.error.HTTPError as e:
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': e.read().decode('utf-8', errors='replace')}, status_code=400)


@app.get('/meta/run-ai-post')
def meta_run_ai_post(page_id: str = '', description: str = '', scheduled_publish_time: str = '', publish_now: str = 'true', image_url: str = '', preview_only: str = 'false'):
    cfg = load_config()
    if not page_id or not description:
        return JSONResponse({'ok': False, 'error': 'missing_page_id_or_description'}, status_code=400)
    try:
        publish_now_bool = str(publish_now).lower() in ['1', 'true', 'yes', 'y']
        preview_only_bool = str(preview_only).lower() in ['1', 'true', 'yes', 'y']
        publish = 'true' if publish_now_bool and not scheduled_publish_time else 'false'
        generated = generate_ai_copy_and_prompt(description, page_id=str(page_id or ''))
        image = generate_image_local(generated['image_prompt'])
        image_path = image.get('path', '')
        final_image_url = image_url or (publish_generated_file(cfg, image_path) if image_path else '')
        result = {
            'generated': generated,
            'image': image,
            'image_url': final_image_url,
            'preview_only': preview_only_bool,
        }
        if not preview_only_bool:
            if final_image_url:
                post_result = create_page_photo_post(cfg, page_id, final_image_url, generated['copy'], publish, scheduled_publish_time)
            else:
                post_result = create_page_post(cfg, page_id, generated['copy'], '', publish, scheduled_publish_time)
            result['post_result'] = post_result
        with AI_POST_RUNS_PATH.open('a') as f:
            f.write(json.dumps({'mode': 'get', 'description': description, 'page_id': page_id, 'scheduled_publish_time': scheduled_publish_time, 'publish_now': publish_now_bool, 'preview_only': preview_only_bool, 'result': result}, ensure_ascii=False) + '\n')
        return {'ok': True, **result}
    except urllib.error.HTTPError as e:
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': e.read().decode('utf-8', errors='replace')}, status_code=400)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'run_ai_post_failed', 'detail': str(e)}, status_code=400)


@app.get('/meta/run-page-posts')
def meta_run_page_posts(page_id: str = ''):
    cfg = load_config()
    if not page_id:
        return JSONResponse({'ok': False, 'error': 'missing_page_id'}, status_code=400)
    try:
        posts = fetch_page_posts(cfg, page_id)
        return {'ok': True, 'page_id': page_id, 'posts': posts.get('data', [])}
    except urllib.error.HTTPError as e:
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': e.read().decode('utf-8', errors='replace')}, status_code=400)


@app.get('/meta/webhook')
def meta_webhook_verify(request: Request):
    cfg = load_config()
    verify_token = get_secret(cfg['verify_token_name'])
    mode = request.query_params.get('hub.mode', '')
    token = request.query_params.get('hub.verify_token', '')
    challenge = request.query_params.get('hub.challenge', '')
    if mode == 'subscribe' and token and token == verify_token:
        return PlainTextResponse(challenge)
    return PlainTextResponse('Forbidden', status_code=403)


@app.post('/meta/webhook')
async def meta_webhook_receive(request: Request):
    body = await request.json()
    EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with EVENTS_PATH.open('a') as f:
        f.write(json.dumps(body, ensure_ascii=False) + '\n')
    return {'ok': True}


@app.get('/meta/debug/config')
def meta_debug_config():
    cfg = load_config()
    session = load_json(META_SESSION_PATH, {})
    return {
        'ok': True,
        'public_base_url': cfg.get('public_base_url', ''),
        'app_id': cfg.get('app_id', ''),
        'graph_api_version': cfg.get('graph_api_version', ''),
        'default_scopes': cfg.get('default_scopes', ''),
        'ai_settings': cfg.get('ai_settings', {}),
        'app_secret_saved': bool(get_secret(cfg['app_secret_name'])),
        'verify_token_saved': bool(get_secret(cfg['verify_token_name'])),
        'gemini_api_key_saved': bool(get_secret(GEMINI_API_KEY_NAME) or get_secret('GOOGLE_API_KEY')),
        'openai_api_key_saved': bool(get_secret(OPENAI_API_KEY_NAME)),
        'openai_base_url': _openai_base_url(),
        'freeimage_api_key_saved': bool(get_secret(FREEIMAGE_API_KEY_NAME)),
        'cloudinary_cloud_name': get_secret(CLOUDINARY_CLOUD_NAME),
        'cloudinary_api_key_saved': bool(get_secret(CLOUDINARY_API_KEY_NAME)),
        'cloudinary_api_secret_saved': bool(get_secret(CLOUDINARY_API_SECRET_NAME)),
        'connected': bool((session.get('token') or {}).get('access_token')),
        'pages_count': len(session.get('pages', [])),
        'ad_accounts_count': len(session.get('ad_accounts', [])),
    }


@app.get('/privacy', response_class=HTMLResponse)
def privacy_page():
    cfg = load_config()
    base = cfg['public_base_url'].rstrip('/')
    html = f"""
    <html>
      <head>
        <title>Privacy Policy - Marketing Automation API</title>
        <meta charset=\"UTF-8\"/>
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"/>
      </head>
      <body style=\"font-family:Arial,sans-serif;max-width:900px;margin:40px auto;line-height:1.7;color:#0f172a;padding:0 16px\">
        <h1>Privacy Policy</h1>
        <p>This application and API are operated for marketing automation, social publishing, analytics, business account connectivity, and workflow orchestration across supported platforms such as Meta, Instagram, LinkedIn, and X.</p>
        <p>We may process account identifiers, profile metadata, authentication tokens, page and organization connection metadata, webhook events, publishing requests, media URLs, campaign-related information, and operational logs strictly to provide the requested integrations and service functionality.</p>
        <p>We do not intentionally sell personal data. Information is processed only for service operation, integration management, analytics, security monitoring, abuse prevention, and support.</p>
        <p>Access to connected accounts and stored integration data is limited to authorized operational use. Reasonable technical and administrative measures are used to reduce unauthorized access risk, but no internet-connected service can guarantee absolute security.</p>
        <p>Users may request data deletion by following the instructions available at <a href=\"{base}/data-deletion\">{base}/data-deletion</a>.</p>
        <p>Terms of service are available at <a href=\"{base}/terms\">{base}/terms</a>.</p>
        <p>Service endpoint: <a href=\"{base}\">{base}</a>.</p>
      </body>
    </html>
    """
    return HTMLResponse(html)


@app.get('/terms', response_class=HTMLResponse)
def terms_page():
    cfg = load_config()
    base = cfg['public_base_url'].rstrip('/')
    html = f"""
    <html>
      <head>
        <title>Terms of Service - Marketing Automation API</title>
        <meta charset=\"UTF-8\"/>
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"/>
      </head>
      <body style=\"font-family:Arial,sans-serif;max-width:900px;margin:40px auto;line-height:1.7;color:#0f172a;padding:0 16px\">
        <h1>Terms of Service</h1>
        <p>This application provides marketing automation tooling, social account connectivity, webhook endpoints, content publishing workflows, analytics, and operational interfaces for connected business assets.</p>
        <p>Use of this service must comply with applicable law and the platform policies, developer terms, automation rules, and business permissions of each connected platform, including but not limited to Meta, LinkedIn, and X.</p>
        <p>You are responsible for ensuring you have authorization to connect, manage, publish to, analyze, or otherwise operate any connected account, page, profile, organization, or advertising asset.</p>
        <p>The service may be modified, rate-limited, restricted, or suspended for maintenance, platform compliance, abuse prevention, security protection, or technical reasons.</p>
        <p>Privacy details are available at <a href=\"{base}/privacy\">{base}/privacy</a>.</p>
      </body>
    </html>
    """
    return HTMLResponse(html)


@app.get('/data-deletion', response_class=HTMLResponse)
def data_deletion_page():
    cfg = load_config()
    base = cfg['public_base_url'].rstrip('/')
    html = f"""
    <html>
      <head>
        <title>Data Deletion Instructions - Marketing Automation API</title>
        <meta charset=\"UTF-8\"/>
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"/>
      </head>
      <body style=\"font-family:Arial,sans-serif;max-width:900px;margin:40px auto;line-height:1.7;color:#0f172a;padding:0 16px\">
        <h1>Data Deletion Instructions</h1>
        <p>If you want your integration-related data removed from this application, send a deletion request including the connected account, organization, profile, or app identification details used during the integration.</p>
        <p>After receiving a valid request, integration data stored for the identified account can be reviewed and removed, except where retention is required for security, compliance, legal, or fraud-prevention reasons.</p>
        <p>You may also disconnect this application directly from your connected platform account settings when supported by the platform provider.</p>
        <p>Related links:</p>
        <ul>
          <li><a href=\"{base}/privacy\">Privacy Policy</a></li>
          <li><a href=\"{base}/terms\">Terms of Service</a></li>
        </ul>
      </body>
    </html>
    """
    return HTMLResponse(html)

# ── Instagram Carousel ────────────────────────────────────────────────────────

@app.post('/meta/instagram/carousel')
async def meta_instagram_carousel(request: Request):
    """
    Publish an Instagram carousel post (2–10 images).
    Body: { image_urls: [str, ...], caption?: str, username?, ig_user_id?, page_id?, access_token?, mode? }
    """
    cfg = load_config()
    body = await request.json()
    image_urls = body.get('image_urls', [])
    caption = body.get('caption', '')
    if not image_urls or len(image_urls) < 2:
        return JSONResponse({'ok': False, 'error': 'carousel_requires_at_least_2_images'}, status_code=400)
    effective_ig_user_id, effective_token, effective_host = _resolve_ig_context(body)
    if not effective_ig_user_id or not effective_token:
        return JSONResponse({'ok': False, 'error': 'missing_instagram_auth_context'}, status_code=400)
    try:
        children_ids = []
        items_result = []
        for img_url in image_urls:
            item = instagram_create_carousel_item(cfg, effective_ig_user_id, effective_token, img_url, host=effective_host)
            if 'error' in item:
                return JSONResponse({'ok': False, 'error': 'carousel_item_create_failed', 'detail': item['error'], 'image_url': img_url}, status_code=400)
            children_ids.append(item['id'])
            items_result.append(item)
        container = instagram_create_carousel_container(cfg, effective_ig_user_id, effective_token, children_ids, caption, host=effective_host)
        if 'error' in container:
            return JSONResponse({'ok': False, 'error': 'carousel_container_create_failed', 'detail': container['error']}, status_code=400)
        publish_result = instagram_publish_media(cfg, effective_ig_user_id, effective_token, container['id'], host=effective_host)
        return {'ok': True, 'items': items_result, 'container': container, 'publish_result': publish_result}
    except urllib.error.HTTPError as e:
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': e.read().decode('utf-8', errors='replace')}, status_code=400)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'carousel_post_failed', 'detail': str(e)}, status_code=400)


# ── Instagram Story ───────────────────────────────────────────────────────────

@app.post('/meta/instagram/story')
async def meta_instagram_story(request: Request):
    """
    Publish an Instagram Story (image).
    Body: { image_url: str, username?, ig_user_id?, page_id?, access_token?, mode? }
    """
    cfg = load_config()
    body = await request.json()
    image_url = body.get('image_url', '')
    if not image_url:
        return JSONResponse({'ok': False, 'error': 'missing_image_url'}, status_code=400)
    effective_ig_user_id, effective_token, effective_host = _resolve_ig_context(body)
    if not effective_ig_user_id or not effective_token:
        return JSONResponse({'ok': False, 'error': 'missing_instagram_auth_context'}, status_code=400)
    try:
        container = instagram_create_story_container(cfg, effective_ig_user_id, effective_token, image_url, host=effective_host)
        if 'error' in container:
            return JSONResponse({'ok': False, 'error': 'story_create_failed', 'detail': container['error']}, status_code=400)
        publish_result = instagram_publish_media(cfg, effective_ig_user_id, effective_token, container['id'], host=effective_host)
        return {'ok': True, 'container': container, 'publish_result': publish_result}
    except urllib.error.HTTPError as e:
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': e.read().decode('utf-8', errors='replace')}, status_code=400)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'story_post_failed', 'detail': str(e)}, status_code=400)


# ── Instagram Reel ────────────────────────────────────────────────────────────

@app.post('/meta/instagram/reel')
async def meta_instagram_reel(request: Request):
    """
    Create an Instagram Reel container (video processing is async).
    Body: { video_url: str, caption?: str, share_to_feed?: bool, username?, ig_user_id?, page_id?, access_token?, mode? }
    After creation, poll GET /meta/instagram/container-status until status_code=FINISHED,
    then publish with POST /meta/instagram/publish-container.
    """
    cfg = load_config()
    body = await request.json()
    video_url = body.get('video_url', '')
    if not video_url:
        return JSONResponse({'ok': False, 'error': 'missing_video_url'}, status_code=400)
    effective_ig_user_id, effective_token, effective_host = _resolve_ig_context(body)
    if not effective_ig_user_id or not effective_token:
        return JSONResponse({'ok': False, 'error': 'missing_instagram_auth_context'}, status_code=400)
    try:
        container = instagram_create_reel_container(
            cfg, effective_ig_user_id, effective_token,
            video_url, body.get('caption', ''),
            bool(body.get('share_to_feed', True)),
            host=effective_host,
        )
        if 'error' in container:
            return JSONResponse({'ok': False, 'error': 'reel_create_failed', 'detail': container['error']}, status_code=400)
        return {
            'ok': True,
            'container': container,
            'ig_user_id': effective_ig_user_id,
            'note': 'Video is processing. Poll GET /meta/instagram/container-status?container_id=ID&ig_user_id=ID until status_code=FINISHED, then POST /meta/instagram/publish-container.',
        }
    except urllib.error.HTTPError as e:
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': e.read().decode('utf-8', errors='replace')}, status_code=400)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'reel_create_failed', 'detail': str(e)}, status_code=400)


@app.get('/meta/instagram/container-status')
def meta_instagram_container_status(container_id: str = '', ig_user_id: str = '', access_token: str = '', username: str = '', page_id: str = '', mode: str = ''):
    cfg = load_config()
    if not container_id:
        return JSONResponse({'ok': False, 'error': 'missing_container_id'}, status_code=400)
    _, effective_token, effective_host = _resolve_ig_context({
        'ig_user_id': ig_user_id, 'access_token': access_token,
        'username': username, 'page_id': page_id, 'mode': mode,
    })
    if not effective_token:
        return JSONResponse({'ok': False, 'error': 'missing_auth_context'}, status_code=400)
    try:
        result = instagram_check_container_status(cfg, container_id, effective_token, host=effective_host)
        return {'ok': True, 'container_id': container_id, 'result': result}
    except urllib.error.HTTPError as e:
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': e.read().decode('utf-8', errors='replace')}, status_code=400)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'container_status_failed', 'detail': str(e)}, status_code=400)


@app.post('/meta/instagram/publish-container')
async def meta_instagram_publish_container(request: Request):
    """
    Publish a ready container (after status_code=FINISHED).
    Body: { container_id: str, ig_user_id?: str, access_token?: str, username?, page_id?, mode? }
    """
    cfg = load_config()
    body = await request.json()
    container_id = body.get('container_id', '')
    if not container_id:
        return JSONResponse({'ok': False, 'error': 'missing_container_id'}, status_code=400)
    effective_ig_user_id, effective_token, effective_host = _resolve_ig_context(body)
    if not effective_ig_user_id or not effective_token:
        return JSONResponse({'ok': False, 'error': 'missing_instagram_auth_context'}, status_code=400)
    try:
        publish_result = instagram_publish_media(cfg, effective_ig_user_id, effective_token, container_id, host=effective_host)
        return {'ok': True, 'publish_result': publish_result}
    except urllib.error.HTTPError as e:
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': e.read().decode('utf-8', errors='replace')}, status_code=400)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'publish_container_failed', 'detail': str(e)}, status_code=400)


# ── Facebook Posts (full-featured) ────────────────────────────────────────────

@app.post('/meta/facebook/post')
async def meta_facebook_post(request: Request):
    """
    Create a Facebook Page text/link post.
    Body: { page_id: str, message: str, link?: str, published?: bool, scheduled_publish_time?: str }
    """
    cfg = load_config()
    body = await request.json()
    page_id = body.get('page_id', '')
    message = body.get('message', '')
    if not page_id or not message:
        return JSONResponse({'ok': False, 'error': 'missing_page_id_or_message'}, status_code=400)
    try:
        result = create_page_post(
            cfg, page_id, message,
            body.get('link', ''),
            str(body.get('published', 'true')).lower(),
            str(body.get('scheduled_publish_time', '') or ''),
        )
        return {'ok': True, 'result': result}
    except urllib.error.HTTPError as e:
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': e.read().decode('utf-8', errors='replace')}, status_code=400)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'facebook_post_failed', 'detail': str(e)}, status_code=400)


@app.post('/meta/facebook/photo')
async def meta_facebook_photo(request: Request):
    """
    Post a photo to a Facebook Page.
    Body: { page_id: str, image_url: str, caption?: str, published?: bool, scheduled_publish_time?: str }
    """
    cfg = load_config()
    body = await request.json()
    page_id = body.get('page_id', '')
    image_url = body.get('image_url', '')
    if not page_id or not image_url:
        return JSONResponse({'ok': False, 'error': 'missing_page_id_or_image_url'}, status_code=400)
    try:
        result = create_page_photo_post(
            cfg, page_id, image_url,
            body.get('caption', ''),
            str(body.get('published', 'true')).lower(),
            str(body.get('scheduled_publish_time', '') or ''),
        )
        return {'ok': True, 'result': result}
    except urllib.error.HTTPError as e:
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': e.read().decode('utf-8', errors='replace')}, status_code=400)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'facebook_photo_failed', 'detail': str(e)}, status_code=400)


@app.post('/meta/facebook/album')
async def meta_facebook_album(request: Request):
    """
    Post a multi-photo album to a Facebook Page.
    Body: { page_id: str, image_urls: [str, ...], caption?: str, published?: bool }
    """
    cfg = load_config()
    body = await request.json()
    page_id = body.get('page_id', '')
    image_urls = body.get('image_urls', [])
    caption = body.get('caption', '')
    published = str(body.get('published', 'true')).lower()
    if not page_id or not image_urls:
        return JSONResponse({'ok': False, 'error': 'missing_page_id_or_image_urls'}, status_code=400)
    token = get_page_access_token(page_id)
    if not token:
        return JSONResponse({'ok': False, 'error': 'no_token_for_page'}, status_code=400)
    cfg_v = cfg['graph_api_version']
    try:
        photo_ids = []
        for img_url in image_urls:
            url = f"https://graph.facebook.com/{cfg_v}/{page_id}/photos"
            res = graph_post(url, {'url': img_url, 'published': 'false', 'access_token': token})
            if 'id' not in res:
                return JSONResponse({'ok': False, 'error': 'photo_upload_failed', 'detail': res, 'image_url': img_url}, status_code=400)
            photo_ids.append({'media_fbid': res['id']})
        url = f"https://graph.facebook.com/{cfg_v}/{page_id}/feed"
        result = graph_post(url, {
            'message': caption,
            'published': published,
            'attached_media': json.dumps(photo_ids),
            'access_token': token,
        })
        return {'ok': True, 'photo_ids': photo_ids, 'result': result}
    except urllib.error.HTTPError as e:
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': e.read().decode('utf-8', errors='replace')}, status_code=400)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'facebook_album_failed', 'detail': str(e)}, status_code=400)


# ── Ads – list adsets & ads ───────────────────────────────────────────────────

@app.get('/meta/ad-adsets')
def meta_ad_adsets(ad_account_id: str = '', campaign_id: str = '', limit: str = '100'):
    cfg = load_config()
    if not ad_account_id and not campaign_id:
        return JSONResponse({'ok': False, 'error': 'missing_ad_account_id_or_campaign_id'}, status_code=400)
    if ad_account_id:
        ad_account_id = normalize_ad_account_id(ad_account_id)
    try:
        result = fetch_adsets(cfg, ad_account_id, campaign_id, limit)
        return {'ok': True, 'ad_account_id': ad_account_id, 'campaign_id': campaign_id, 'adsets': result.get('data', [])}
    except urllib.error.HTTPError as e:
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': e.read().decode('utf-8', errors='replace')}, status_code=400)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'fetch_adsets_failed', 'detail': str(e)}, status_code=400)


@app.get('/meta/ad-ads')
def meta_ad_ads(ad_account_id: str = '', adset_id: str = '', limit: str = '100'):
    cfg = load_config()
    if not ad_account_id and not adset_id:
        return JSONResponse({'ok': False, 'error': 'missing_ad_account_id_or_adset_id'}, status_code=400)
    if ad_account_id:
        ad_account_id = normalize_ad_account_id(ad_account_id)
    try:
        result = fetch_ads(cfg, ad_account_id, adset_id, limit)
        return {'ok': True, 'ad_account_id': ad_account_id, 'adset_id': adset_id, 'ads': result.get('data', [])}
    except urllib.error.HTTPError as e:
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': e.read().decode('utf-8', errors='replace')}, status_code=400)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'fetch_ads_failed', 'detail': str(e)}, status_code=400)


@app.get('/panel/ads/report')
def panel_ads_report(request: Request, ad_account_id: str = '', date_preset: str = 'last_30d', panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not user:
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    if not ad_account_id:
        return JSONResponse({'ok': False, 'error': 'missing_ad_account_id'}, status_code=400)
    cfg = load_config()
    ad_account_id = normalize_ad_account_id(ad_account_id)
    if not ad_account_allowed_for_user(user, ad_account_id):
        return JSONResponse({'ok': False, 'error': 'forbidden_ad_account'}, status_code=403)
    warnings = []

    try:
        perf_tree = build_spend_active_ads_tree(cfg, ad_account_id, date_preset=date_preset, limit='250')
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'performance_tree_failed', 'detail': str(e)}, status_code=400)

    campaigns_tree = perf_tree.get('campaigns', []) or []
    summary = perf_tree.get('summary', {}) or {}

    total_actions = {}
    campaign_rows = []
    adsets_flat = []
    ads_flat = []
    objective_mix = {}
    active_campaigns = 0
    paused_campaigns = 0

    for campaign_node in campaigns_tree:
        campaign = campaign_node.get('campaign', {}) or {}
        metrics = campaign_node.get('metrics', {}) or {}
        objective_label = objective_label_pt(campaign.get('objective', ''))
        objective_mix[objective_label] = objective_mix.get(objective_label, 0) + 1
        status = (campaign.get('effective_status') or campaign.get('status') or '').upper()
        if status == 'ACTIVE':
            active_campaigns += 1
        if status == 'PAUSED':
            paused_campaigns += 1

        campaign_rows.append({
            **campaign,
            'objective_label': objective_label,
            'performance': metrics,
            'leads': metrics.get('leads', 0),
            'messages': metrics.get('messages', 0),
            'purchases': metrics.get('purchases', 0),
            'spend_30d': metrics.get('spend', 0),
            'ctr_30d': 0,
            'cpc_30d': 0,
        })

        for adset_node in campaign_node.get('adsets', []) or []:
            adset = adset_node.get('adset', {}) or {}
            adset_metrics = adset_node.get('metrics', {}) or {}
            adsets_flat.append({**adset, 'performance': adset_metrics})
            for ad_node in adset_node.get('ads', []) or []:
                ad = ad_node.get('ad', {}) or {}
                ad_metrics = ad_node.get('metrics', {}) or {}
                ads_flat.append({**ad, 'performance': ad_metrics})
                for action in ad_metrics.get('actions', []) or []:
                    action_type = action.get('action_type')
                    if not action_type:
                        continue
                    total_actions[action_type] = total_actions.get(action_type, 0.0) + _coerce_float(action.get('value'))

    totals = {
        'spend': summary.get('spend', 0),
        'impressions': summary.get('impressions', 0),
        'reach': summary.get('reach', 0),
        'clicks': summary.get('clicks', 0),
        'ctr': round((float(summary.get('clicks', 0)) / float(summary.get('impressions', 0)) * 100.0), 2) if float(summary.get('impressions', 0) or 0) > 0 else 0,
        'cpc': round((float(summary.get('spend', 0)) / float(summary.get('clicks', 0))), 2) if float(summary.get('clicks', 0) or 0) > 0 else 0,
        'cpm': round((float(summary.get('spend', 0)) / float(summary.get('impressions', 0)) * 1000.0), 2) if float(summary.get('impressions', 0) or 0) > 0 else 0,
        'actions': total_actions,
        'action_values': {},
        'cost_per_action_type': [],
        'purchase_roas': [],
        'website_purchase_roas': [],
    }

    report = {
        'ad_account_id': ad_account_id,
        'date_preset': date_preset,
        'totals': totals,
        'counts': {
            'campaigns': len(campaigns_tree),
            'adsets': summary.get('adsets', len(adsets_flat)),
            'ads': summary.get('ads', len(ads_flat)),
        },
        'campaigns': campaign_rows,
        'campaign_insights': {},
        'adsets': adsets_flat,
        'ads': ads_flat,
        'demographics': [],
        'active_campaigns': active_campaigns,
        'paused_campaigns': paused_campaigns,
        'objective_mix': objective_mix,
        'performance_tree': perf_tree,
    }
    update_ad_account_memory_snapshot(ad_account_id, report)

    ai_summary = ''
    ai_model_used = ''
    ai_provider_used = ''
    ai_cost_usd = 0.0
    if (_ai_route('campaign_analysis').get('provider') == 'openai' and _openai_api_key()) or (get_secret(GEMINI_API_KEY_NAME) or get_secret('GOOGLE_API_KEY')):
        compact = _compact_report_for_ai(report)
        prompt = (
            'Você é um analista de mídia paga sênior e especialista em dashboards executivos. '
            'Responda em português do Brasil, SEM markdown, SEM #, SEM *, SEM listas com bullets markdown. '
            'Escreva em texto limpo, consistente e escaneável, com blocos curtos e linguagem de relatório executivo. '
            'Use somente os dados reais presentes na entrada. Não invente campanhas, não invente quantidades ativas, não invente resultados. '
            'Os números do topo e da análise DEVEM bater exatamente com os dados consolidados recebidos. '
            'Se existir divergência aparente entre campanhas e totais, confie somente no summary consolidado e nas campanhas fornecidas. '
            'Priorize: 1) resultado final por tipo de campanha, 2) custo por resultado, 3) ROAS quando existir, 4) leitura de eficiência, 5) riscos, 6) oportunidades, 7) próximos passos. '
            'Considere especialmente campanhas de mensagens, cadastros/leads e vendas/compras. '
            'Quando houver dados, separe a análise por objetivo/resultados em blocos independentes: mensagens, cadastros e vendas. '
            'Explique quantas campanhas estão ativas e pausadas com base no summary recebido, qual o peso de cada objetivo, e quais resultados realmente importam. '
            'Evite floreio e evite repetir métricas sem interpretação. '
            'Estruture a resposta em seções nomeadas em texto simples: RESUMO EXECUTIVO, KPIS PRINCIPAIS, CAMPANHAS ATIVAS NO PERÍODO, RESULTADOS POR OBJETIVO, DEMOGRAFIA, RISCOS, OPORTUNIDADES, PRÓXIMOS PASSOS. '
            'Dados (resumo compacto): ' + json.dumps(compact, ensure_ascii=False)
        )
        try:
            ai_result = _ai_generate_text('campaign_analysis', prompt, 60, json_mode=False)
            ai_summary = ai_result.get('text', '')
            ai_model_used = ai_result.get('model', '')
            ai_provider_used = ai_result.get('provider', '')
            ai_cost_usd = ai_result.get('cost_usd', 0.0)
            log_ai_usage('campaign_analysis', ai_provider_used, ai_model_used, ai_result.get('usage', {}), ai_cost_usd, item_type='campaign_report')
        except Exception as e:
            ai_summary = f'Falha ao gerar resumo por IA após tentar vários modelos: {e}'
    else:
        ai_summary = 'Configure Gemini ou OpenAI nas configurações para o resumo por IA.'

    history_entry = {
        'ts': int(time.time()),
        'date_preset': date_preset,
        'report_summary': {
            'active_campaigns': active_campaigns,
            'paused_campaigns': paused_campaigns,
            'objective_mix': objective_mix,
        },
        'totals': report.get('totals', {}),
        'counts': report.get('counts', {}),
        'ai_summary': ai_summary,
        'ai_model': ai_model_used,
        'ai_provider': ai_provider_used,
        'ai_cost_usd': ai_cost_usd,
    }
    append_ads_report_history(ad_account_id, history_entry)
    return {
        'ok': True,
        'report': report,
        'report_summary': {
            'active_campaigns': active_campaigns,
            'paused_campaigns': paused_campaigns,
            'objective_mix': objective_mix,
        },
        'ai_summary': ai_summary,
        'ai_model': ai_model_used,
        'warnings': warnings,
    }


# ── Ads – standalone create ───────────────────────────────────────────────────

@app.post('/meta/ad-drafts/create-adset')
async def meta_ad_draft_create_adset(request: Request):
    cfg = load_config()
    body = await request.json()
    try:
        ad_account_id = body.get('ad_account_id', '')
        campaign_id = body.get('campaign_id', '')
        adset_name = body.get('adset_name', '') or body.get('name', '')
        daily_budget = str(body.get('daily_budget', '') or '')
        targeting = body.get('targeting', {}) or {}
        if not ad_account_id or not campaign_id or not adset_name or not daily_budget:
            return JSONResponse({'ok': False, 'error': 'missing_required_fields: ad_account_id, campaign_id, adset_name, daily_budget'}, status_code=400)
        result = create_adset_draft(
            cfg, ad_account_id, campaign_id, adset_name,
            body.get('optimization_goal', 'LINK_CLICKS'),
            body.get('billing_event', 'IMPRESSIONS'),
            daily_budget, targeting,
            body.get('status', 'PAUSED'),
            body.get('promoted_object'),
            body.get('bid_strategy', 'LOWEST_COST_WITHOUT_CAP'),
        )
        return {'ok': True, 'adset': result}
    except urllib.error.HTTPError as e:
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': e.read().decode('utf-8', errors='replace')}, status_code=400)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'create_adset_failed', 'detail': str(e)}, status_code=400)


@app.post('/meta/ad-drafts/create-creative')
async def meta_ad_draft_create_creative(request: Request):
    cfg = load_config()
    body = await request.json()
    try:
        ad_account_id = body.get('ad_account_id', '')
        creative_name = body.get('creative_name', '') or body.get('name', '')
        page_id = body.get('page_id', '')
        if not ad_account_id or not creative_name or not page_id:
            return JSONResponse({'ok': False, 'error': 'missing_required_fields: ad_account_id, creative_name, page_id'}, status_code=400)
        result = create_adcreative_draft(
            cfg, ad_account_id, creative_name, page_id,
            body.get('instagram_actor_id', ''),
            body.get('image_url', ''),
            body.get('image_hash', ''),
            body.get('message', ''),
            body.get('link', ''),
            body.get('call_to_action_type', 'LEARN_MORE'),
        )
        return {'ok': True, 'creative': result}
    except urllib.error.HTTPError as e:
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': e.read().decode('utf-8', errors='replace')}, status_code=400)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'create_creative_failed', 'detail': str(e)}, status_code=400)


@app.post('/meta/ad-drafts/create-ad')
async def meta_ad_draft_create_ad(request: Request):
    cfg = load_config()
    body = await request.json()
    try:
        ad_account_id = body.get('ad_account_id', '')
        ad_name = body.get('ad_name', '') or body.get('name', '')
        adset_id = body.get('adset_id', '')
        creative_id = body.get('creative_id', '')
        if not ad_account_id or not ad_name or not adset_id or not creative_id:
            return JSONResponse({'ok': False, 'error': 'missing_required_fields: ad_account_id, ad_name, adset_id, creative_id'}, status_code=400)
        result = create_ad_draft(cfg, ad_account_id, ad_name, adset_id, creative_id, body.get('status', 'PAUSED'))
        return {'ok': True, 'ad': result}
    except urllib.error.HTTPError as e:
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': e.read().decode('utf-8', errors='replace')}, status_code=400)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'create_ad_failed', 'detail': str(e)}, status_code=400)


@app.post('/meta/ad-drafts/delete')
async def meta_ad_draft_delete(request: Request):
    """
    Delete ad objects (campaign, adset, ad, creative).
    Body: { campaign_id?, adset_id?, ad_id?, creative_id? } – provide one or more.
    """
    cfg = load_config()
    body = await request.json()
    try:
        result = {}
        for key, field in [('campaign_id', 'campaign'), ('adset_id', 'adset'), ('ad_id', 'ad'), ('creative_id', 'creative')]:
            if body.get(key):
                result[field] = delete_meta_object(cfg, body[key])
        if not result:
            return JSONResponse({'ok': False, 'error': 'no_object_id_provided'}, status_code=400)
        return {'ok': True, 'result': result}
    except urllib.error.HTTPError as e:
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': e.read().decode('utf-8', errors='replace')}, status_code=400)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'delete_failed', 'detail': str(e)}, status_code=400)


# ── AGENTS CONFIG ──────────────────────────────────────────────────────────────

AGENT_DEFINITIONS = [
    {'key': 'copy_generation', 'name': 'Redator', 'description': 'Gera legendas do Instagram com gancho, desenvolvimento e CTA.', 'icon': '✍️'},
    {'key': 'prompt_generation', 'name': 'Diretor de Arte', 'description': 'Gera as variáveis que preenchem o template de arte.', 'icon': '🎨'},
    {'key': 'plan_generation', 'name': 'Planejador', 'description': 'Cria planos de conteúdo mensais com temas e datas.', 'icon': '📅'},
    {'key': 'focus_suggestion', 'name': 'Analista de Foco', 'description': 'Sugere o foco estratégico para cada post ou plano.', 'icon': '🎯'},
    {'key': 'brand_analysis', 'name': 'Analista de Marca', 'description': 'Analisa o perfil e posicionamento da marca.', 'icon': '🏷️'},
    {'key': 'campaign_analysis', 'name': 'Analista de Campanhas', 'description': 'Analisa resultados de campanhas de tráfego e leads.', 'icon': '📊'},
    {'key': 'profile_analysis', 'name': 'Analista de Perfil', 'description': 'Analisa o perfil do Instagram e desempenho orgânico.', 'icon': '📈'},
    {'key': 'icp_analysis', 'name': 'Analista de ICP', 'description': 'Define e refina o cliente ideal da marca.', 'icon': '👤'},
]

DEFAULT_IMAGE_TEMPLATE = """# PROMPT — INSTAGRAM PREMIUM MODERNO (ANTI-SURREAL / LAYOUT FIXO)

Crie uma arte profissional para Instagram no formato 1:1 (1080x1080) inspirada em criativos modernos premium de marcas high-end.

A composição deve parecer uma peça real de marketing feita por designer profissional para redes sociais, com aparência elegante, limpa e comercial.

Evite visual surreal, exageradamente futurista ou conceitos abstratos sem contexto.

---

# CONTEXTO

Nicho: "{NICHO}"

Objetivo: "{OBJETIVO_DA_MENSAGEM}"

Transmitir claramente a mensagem com percepção de valor elevada, aparência premium e foco em conversão.

---

# DIREÇÃO VISUAL

Estilo visual:

"{ESTILO_VISUAL}"

Combinação:

"{TIPO_DE_RENDER}"

Emoção:

"{EMOCAO}"

Iluminação:

"{TIPO_ILUMINACAO}"

A estética deve seguir:

- visual contemporâneo de Instagram
- high-end marketing design
- clean
- sofisticado
- minimalista
- editorial
- UI inspired
- glass morphism discreto
- tecnologia sutil
- aparência real

Evitar:

- elementos flutuando aleatoriamente
- sci-fi exagerado
- objetos sem função
- excesso de hologramas
- excesso de glow
- composições fantasiosas

Tudo deve parecer plausível, comercial e feito para campanhas reais.

---

# FUNDO

Criar fundo premium usando:

"{CORES_PRINCIPAIS}"

Aplicar:

- gradiente escuro suave
- profundidade realista
- iluminação difusa
- contraste leve
- sombras suaves

Adicionar um overlay degradê escuro translúcido semelhante a campanhas premium imobiliárias.

Características:

- iniciar transparente
- aumentar gradualmente
- mais forte no rodapé
- aparência cinematográfica
- transição suave

Objetivo:

dar legibilidade ao conteúdo e destacar a futura logo.

O degradê deve ocupar aproximadamente:

30–40% inferiores da composição

aumentando progressivamente a opacidade.

---

# ÁREA RESERVADA PARA LOGO (REGRA CRÍTICA)

Reservar totalmente o canto:

INFERIOR ESQUERDO

Criar área de segurança:

- 25–30% largura
- 20–25% altura

Nesta região é PROIBIDO:

- textos
- ícones
- botões
- objetos
- personagens
- elementos 3D
- linhas fortes
- partículas
- brilhos
- efeitos chamativos
- formas grandes
- destaques

Permitir somente:

gradiente escuro suave.

Objetivo:

criar espaço limpo para aplicação posterior da logo.

NUNCA gerar:

- logotipo
- marca
- símbolo
- assinatura
- watermark

---

# CENÁRIO

Caso faça sentido:

"{CENARIO_REALISTA}"

Utilizar cenários plausíveis:

Exemplos:

- escritório moderno
- ambiente corporativo
- casa sofisticada
- setup tecnológico
- ambiente médico
- lifestyle premium
- ambiente digital minimalista

Evitar:

- ambientes irreais
- cidades futuristas
- cenários abstratos
- excesso de elementos

---

# PERSONAGEM (OPCIONAL)

"{DESCRICAO_PERSONAGEM}"

Caso exista personagem:

- postura natural
- aparência premium
- visual editorial
- proporções reais
- expressão discreta

Evitar:

- poses artificiais
- exageros
- aparência claramente gerada por IA

---

# ELEMENTOS 3D

Adicionar poucos elementos relacionados ao nicho:

"{NICHO}"

Exemplos:

Fintech:

- gráficos sutis
- linhas financeiras

IA:

- estruturas neurais
- UI tecnológica discreta

Imobiliário:

- arquitetura
- estruturas modernas

Travel:

- localização
- mapas minimalistas

Educação:

- UI elegante
- símbolos discretos

Estilo:

- vidro translúcido
- acrílico premium
- soft glow
- baixa opacidade
- integração natural

Limite:

máximo 2–4 elementos

Nunca competir com o conteúdo principal.

---

# ESTRUTURA GRÁFICA

Inspirado no layout da referência:

Adicionar:

- bordas finas arredondadas
- linhas translúcidas suaves
- molduras minimalistas
- containers modernos
- elementos UI discretos

As linhas devem:

- apoiar a composição
- criar organização visual
- parecer premium

Evitar:

- linhas pesadas
- excesso de molduras
- excesso de elementos gráficos

---

# HIERARQUIA

Subtítulo pequeno acima:

"{SUBTITULO}"

Título principal dominante:

"{TITULO}"

Tipografia:

- sans-serif moderna
- elegante
- forte contraste
- extremamente legível

Destacar:

"{PALAVRA_CHAVE_DESTACADA}"

Cor:

"{COR_DESTAQUE}"

O destaque deve ser sofisticado.

Evitar cores excessivamente saturadas.

---

# ESTILO FINAL

- ultra realistic quando aplicável
- premium marketing design
- editorial
- clean layout
- soft glow
- realismo comercial
- glass morphism discreto
- UI/UX inspired
- composição premium Instagram

---

# RESTRIÇÕES

Sem poluição visual

Sem excesso de elementos

Sem surrealismo

Sem sci-fi exagerado

Sem objetos aleatórios

Sem hologramas excessivos

Sem logos

Sem marcas

Sem watermark

Sem tipografia quebrada

Sem invadir área reservada da logo

Sem elementos chamativos no canto inferior esquerdo

Sempre parecer uma campanha real de Instagram feita por designer profissional.

---

# PARÂMETROS

--ar 1:1 --v 6 --style raw

Negativo:

--no logo, brand mark, watermark, distorted text, clutter, futuristic city, floating objects, excessive holograms, sci-fi, chaos, visual noise"""


@app.get('/panel/agents/config')
async def get_agents_config(request: Request, page_id: str = '', panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    cfg = load_agents_config()
    profile = get_brand_profile(str(page_id)) if page_id else {}
    per_notes = profile.get('agent_system_notes') or {} if isinstance(profile.get('agent_system_notes'), dict) else {}
    agents_out = []
    for defn in AGENT_DEFINITIONS:
        key = defn['key']
        agent_cfg = cfg.get(key) or {}
        note = (per_notes.get(key) or '').strip() or agent_cfg.get('system_note', '')
        agents_out.append({
            **defn,
            'system_note': note,
        })
    per_tpl = (profile.get('image_template') or '').strip() if page_id else ''
    # When page_id given: per-company template or clean DEFAULT (never leak global/other-company template)
    # When no page_id: use global config (admin view)
    image_template = per_tpl or (DEFAULT_IMAGE_TEMPLATE if page_id else (cfg.get('image_template') or DEFAULT_IMAGE_TEMPLATE))
    per_refs = profile.get('designer_references')
    designer_references = per_refs if isinstance(per_refs, list) and per_refs and page_id else (cfg.get('designer_references') or [])
    gallery_references = list(profile.get('gallery_references') or []) if page_id else []
    brand_colors = [str(c) for c in (profile.get('colors') or []) if str(c).strip()] if page_id else []
    icp_summary = ((profile.get('icp_onboarding_text') or '')[:500]).strip() if page_id else ''
    visual_references = [r for r in (profile.get('visual_references') or []) if isinstance(r, dict)] if page_id else []
    return {
        'ok': True,
        'agents': agents_out,
        'image_template': image_template,
        'designer_references': designer_references,
        'gallery_references': gallery_references,
        'brand_colors': brand_colors,
        'icp_summary': icp_summary,
        'visual_references': visual_references,
    }


@app.post('/panel/agents/config')
async def save_agents_config_route(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    body = await request.json()
    page_id = str(body.get('page_id', '') or '').strip()
    key = body.get('key', '')
    valid_keys = [d['key'] for d in AGENT_DEFINITIONS]
    if page_id:
        if key == 'image_template':
            upsert_brand_profile(page_id, {'image_template': (body.get('value') or '').strip()})
            return {'ok': True}
        if key in valid_keys:
            profile = get_brand_profile(page_id)
            notes = profile.get('agent_system_notes') or {}
            if not isinstance(notes, dict):
                notes = {}
            notes[key] = (body.get('system_note') or '').strip()
            upsert_brand_profile(page_id, {'agent_system_notes': notes})
            return {'ok': True}
        return JSONResponse({'ok': False, 'error': 'invalid_key'}, status_code=400)
    cfg = load_agents_config()
    if key == 'image_template':
        cfg['image_template'] = (body.get('value') or '').strip()
        save_agents_config(cfg)
        return {'ok': True}
    if key in valid_keys:
        if key not in cfg or not isinstance(cfg.get(key), dict):
            cfg[key] = {}
        cfg[key]['system_note'] = (body.get('system_note') or '').strip()
        save_agents_config(cfg)
        return {'ok': True}
    return JSONResponse({'ok': False, 'error': 'invalid_key'}, status_code=400)


@app.post('/panel/agents/adjust-with-ai')
async def panel_agents_adjust_with_ai(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    """Customize company-specific prompts for all agents using brand context."""
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    body = await request.json()
    page_id = str(body.get('page_id', '') or '').strip()
    if not page_id:
        return JSONResponse({'ok': False, 'error': 'missing_page_id'}, status_code=400)
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if user and not page_allowed_for_user(user, str(page_id)):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    try:
        result = _build_company_agent_adjustments(page_id)
        return {'ok': True, **result}
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=400)


@app.post('/panel/agents/adjust-art-with-ai')
async def panel_agents_adjust_art_with_ai(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    """Generate only image template + art director note using brand context."""
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    body = await request.json()
    page_id = str(body.get('page_id', '') or '').strip()
    if not page_id:
        return JSONResponse({'ok': False, 'error': 'missing_page_id'}, status_code=400)
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if user and not page_allowed_for_user(user, str(page_id)):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    try:
        result = _build_art_agent_adjustments(page_id)
        return {'ok': True, **result}
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=400)


@app.post('/panel/agents/designer/upload-reference')
async def upload_designer_reference(request: Request, file: UploadFile = File(...), page_id: str = Form(default=''), panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    import uuid as _uuid
    ref_id = _uuid.uuid4().hex[:16]
    ext = Path(file.filename or 'ref.jpg').suffix.lower() or '.jpg'
    if ext not in ('.jpg', '.jpeg', '.png', '.webp'):
        ext = '.jpg'
    filename = f'agent_ref_{ref_id}{ext}'
    dest = UPLOADS_DIR / filename
    dest.write_bytes(await file.read())
    url = f'/static/uploads/{filename}'
    entry = {'id': ref_id, 'url': url, 'filename': filename, 'original_name': file.filename or filename}
    page_id = str(page_id or '').strip()
    if page_id:
        profile = get_brand_profile(page_id)
        refs = list(profile.get('designer_references') or [])
        refs.append(entry)
        upsert_brand_profile(page_id, {'designer_references': refs})
    else:
        cfg = load_agents_config()
        refs = list(cfg.get('designer_references') or [])
        refs.append(entry)
        cfg['designer_references'] = refs
        save_agents_config(cfg)
    return {'ok': True, 'id': ref_id, 'url': url}


@app.delete('/panel/agents/designer/reference/{ref_id}')
async def delete_designer_reference(ref_id: str, request: Request, page_id: str = '', panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    page_id = str(page_id or '').strip()
    if page_id:
        profile = get_brand_profile(page_id)
        refs = list(profile.get('designer_references') or [])
        ref = next((r for r in refs if r.get('id') == ref_id), None)
        if ref:
            try:
                (UPLOADS_DIR / ref['filename']).unlink(missing_ok=True)
            except Exception:
                pass
            upsert_brand_profile(page_id, {'designer_references': [r for r in refs if r.get('id') != ref_id]})
    else:
        cfg = load_agents_config()
        refs = list(cfg.get('designer_references') or [])
        ref = next((r for r in refs if r.get('id') == ref_id), None)
        if ref:
            try:
                (UPLOADS_DIR / ref['filename']).unlink(missing_ok=True)
            except Exception:
                pass
            cfg['designer_references'] = [r for r in refs if r.get('id') != ref_id]
            save_agents_config(cfg)
    return {'ok': True}


@app.post('/panel/agents/designer/import-instagram')
async def import_designer_references_from_instagram(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    body = await request.json()
    page_id = str(body.get('page_id', '') or '').strip()
    username = str(body.get('username', '') or '').strip().lstrip('@')
    if not page_id or not username:
        return JSONResponse({'ok': False, 'error': 'missing_page_id_or_username'}, status_code=400)
    if user and not page_allowed_for_user(user, str(page_id)):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    as_user = _insta_effective_as_user('')
    result = _run_insta_script_with_session_fallback('get_recent_posts_json.py', username=username, as_user=as_user, timeout=180)
    if not result.get('ok'):
        return JSONResponse({'ok': False, 'error': result.get('error') or 'instagram_import_failed', 'detail': result.get('detail', '')}, status_code=400)
    selected_posts = result.get('selected_posts') or []
    recent_posts = result.get('recent_posts') or []
    scraped_images = result.get('images') or []
    posts = []
    if isinstance(selected_posts, list) and selected_posts:
        for item in selected_posts:
            if not isinstance(item, dict):
                continue
            posts.append({
                'shortcode': item.get('shortcode'),
                'permalink': item.get('permalink'),
                'image_url': '',
                'caption': item.get('caption') or '',
                'filename': item.get('filename') or '',
            })
    if (not posts) and isinstance(recent_posts, list):
        posts = [p for p in recent_posts if isinstance(p, dict)]
    if not posts:
        return JSONResponse({'ok': False, 'error': 'no_recent_posts_found'}, status_code=400)
    profile_data = result.get('profile') or {}
    selected_by_shortcode = {
        str(item.get('shortcode') or ''): item
        for item in (selected_posts if isinstance(selected_posts, list) else [])
        if isinstance(item, dict) and str(item.get('shortcode') or '')
    }
    image_payloads = {
        str(item.get('filename') or '').strip(): item
        for item in (scraped_images if isinstance(scraped_images, list) else [])
        if isinstance(item, dict) and str(item.get('filename') or '').strip()
    }
    profile = get_brand_profile(page_id)
    refs = list(profile.get('designer_references') or [])
    existing_keys = {
        str((ref or {}).get('source_key', '') or '').strip()
        for ref in refs if isinstance(ref, dict)
    }
    cfg = load_config()
    imported = []
    cfg = load_config()
    for idx, post in enumerate(posts[:3], 1):
        if not isinstance(post, dict):
            continue
        image_url = str(post.get('image_url') or '').strip()
        permalink = str(post.get('permalink') or '').strip()
        shortcode = str(post.get('shortcode') or '').strip()
        selected = selected_by_shortcode.get(shortcode) if shortcode else None
        filename_hint = str((selected or {}).get('filename') or post.get('filename') or '').strip()
        source_key = permalink or shortcode or image_url
        if not source_key or source_key in existing_keys:
            continue
        image_bytes = b''
        ext = '.jpg'
        payload = image_payloads.get(filename_hint) if filename_hint else None
        if payload and payload.get('content_base64'):
            try:
                image_bytes = base64.b64decode(payload.get('content_base64') or '')
            except Exception:
                image_bytes = b''
            ext = Path(filename_hint).suffix.lower() or '.jpg'
        elif image_url:
            try:
                resp = requests.get(
                    image_url,
                    headers={
                        'User-Agent': 'Mozilla/5.0',
                        'Referer': 'https://www.instagram.com/',
                    },
                    timeout=20,
                )
                resp.raise_for_status()
                image_bytes = resp.content
                ctype = str(resp.headers.get('Content-Type', '') or '').lower()
                if 'png' in ctype:
                    ext = '.png'
                elif 'webp' in ctype:
                    ext = '.webp'
            except Exception:
                image_bytes = b''
        if not image_bytes:
            continue
        ref_id = hashlib.sha256(f'{page_id}-{username}-{source_key}-{idx}'.encode('utf-8')).hexdigest()[:16]
        filename = f'agent_ref_ig_{page_id}_{ref_id}{ext}'
        dest = UPLOADS_DIR / filename
        dest.write_bytes(image_bytes)
        url = cfg['public_base_url'].rstrip('/') + f'/uploads/{filename}'
        entry = {
            'id': ref_id,
            'url': url,
            'filename': filename,
            'original_name': f'@{username}_{shortcode or idx}{ext}',
            'source': 'instagram_post',
            'source_username': username,
            'source_key': source_key,
            'permalink': permalink,
            'caption': str(post.get('caption') or '').strip()[:500],
        }
        refs.append(entry)
        imported.append(entry)
        existing_keys.add(source_key)
    upsert_brand_profile(page_id, {'designer_references': refs})
    return {'ok': True, 'imported_count': len(imported), 'imported': imported, 'designer_references': refs, 'profile_username': username}


@app.post('/panel/agents/designer/preview-prompt')
async def designer_preview_prompt(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    body = await request.json()
    description = (body.get('description') or '').strip()
    if not description:
        return JSONResponse({'ok': False, 'error': 'missing_description'}, status_code=400)
    art_direction = body.get('art_direction') or {}
    preview_page_id = str(body.get('page_id', '') or '')
    if preview_page_id:
        p = get_brand_profile(preview_page_id)
        colors = p.get('colors') or []
        base_art = {
            'colors': colors,
            'visual_style': p.get('visual_style', ''),
            'font_preference': p.get('font_preference', ''),
            'logo_url': p.get('logo_url', ''),
            'reference_image_url': p.get('reference_image_url', ''),
            'reference_style_prompt': p.get('reference_style_prompt', ''),
            'use_reference_style': bool(p.get('use_reference_style')),
            'references': [str(r.get('url', '')) for r in (p.get('visual_references') or []) if isinstance(r, dict) and r.get('use_for_style')],
            'niche': p.get('description') or p.get('brand_name') or p.get('target_audience') or '',
            'icp_context': p.get('icp_onboarding_text', ''),
        }
        base_art.update(art_direction)
        art_direction = base_art
    try:
        result = generate_ai_copy_and_prompt(description, art_direction, page_id=preview_page_id)
        return {'ok': True, 'image_prompt': result.get('image_prompt', ''), 'copy': result.get('copy', ''), 'title': result.get('title', ''), 'subtitle': result.get('subtitle', '')}
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=400)


@app.post('/panel/agents/designer/test-image')
async def designer_test_image(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    body = await request.json()
    image_prompt = (body.get('image_prompt') or '').strip()
    test_page_id = str(body.get('page_id', '') or '')
    if not image_prompt:
        return JSONResponse({'ok': False, 'error': 'missing_image_prompt'}, status_code=400)
    cfg = load_config()
    try:
        gallery_paths = None
        if test_page_id:
            p = get_brand_profile(test_page_id)
            gallery = list(p.get('gallery_references') or [])
            gallery_paths = _select_gallery_refs_for_briefing(gallery, image_prompt) or None
        result = generate_image_asset(cfg, image_prompt, post_id='agent_test', prefix='agenttest', ref_image_paths=gallery_paths)
        local_path = (result.get('images') or [{}])[0].get('path') or result.get('requested_output', '')
        if local_path and test_page_id:
            p = get_brand_profile(test_page_id)
            logo_dark = str(p.get('logo_path', '') or '')
            logo_light = str(p.get('logo_light_path', '') or '')
            if logo_dark or logo_light:
                overlaid = _apply_logo_smart(local_path, logo_dark, logo_light)
                if overlaid:
                    local_path = overlaid
                    result['public_url'] = build_public_media_url(cfg, local_path, post_id='agent_test', prefix='agenttest')
        return {'ok': True, **result}
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=400)


@app.post('/panel/agents/designer/upload-gallery')
async def upload_designer_gallery(request: Request, file: UploadFile = File(...), page_id: str = Form(default=''), panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    page_id = str(page_id or '').strip()
    if not page_id:
        return JSONResponse({'ok': False, 'error': 'missing_page_id'}, status_code=400)
    import uuid as _uuid
    ref_id = _uuid.uuid4().hex[:16]
    ext = Path(file.filename or 'photo.jpg').suffix.lower() or '.jpg'
    if ext not in ('.jpg', '.jpeg', '.png', '.webp'):
        ext = '.jpg'
    filename = f'gallery_{page_id}_{ref_id}{ext}'
    dest = UPLOADS_DIR / filename
    dest.write_bytes(await file.read())
    url = f'/static/uploads/{filename}'
    entry = {'id': ref_id, 'url': url, 'path': str(dest), 'filename': filename, 'original_name': file.filename or filename}
    profile = get_brand_profile(page_id)
    gallery = list(profile.get('gallery_references') or [])
    gallery.append(entry)
    upsert_brand_profile(page_id, {'gallery_references': gallery})
    # Auto-describe with vision if OpenAI is available
    description = ''
    api_key = _openai_api_key()
    if api_key:
        try:
            description = _describe_image_with_vision(str(dest), api_key)
        except Exception:
            pass
    if description:
        updated_gallery = list(get_brand_profile(page_id).get('gallery_references') or [])
        for r in updated_gallery:
            if r.get('id') == ref_id:
                r['description'] = description
                break
        upsert_brand_profile(page_id, {'gallery_references': updated_gallery})
    return {'ok': True, 'id': ref_id, 'url': url, 'description': description}


@app.patch('/panel/agents/designer/gallery/{ref_id}')
async def update_gallery_description(ref_id: str, request: Request, page_id: str = '', panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    page_id = str(page_id or '').strip()
    if not page_id:
        return JSONResponse({'ok': False, 'error': 'missing_page_id'}, status_code=400)
    body = await request.json()
    new_desc = str(body.get('description', '') or '').strip()
    auto = bool(body.get('auto', False))
    profile = get_brand_profile(page_id)
    gallery = list(profile.get('gallery_references') or [])
    ref = next((r for r in gallery if r.get('id') == ref_id), None)
    if not ref:
        return JSONResponse({'ok': False, 'error': 'not_found'}, status_code=404)
    if auto:
        api_key = _openai_api_key()
        if api_key and ref.get('path') and Path(str(ref['path'])).exists():
            try:
                new_desc = _describe_image_with_vision(str(ref['path']), api_key)
            except Exception:
                pass
    ref['description'] = new_desc
    upsert_brand_profile(page_id, {'gallery_references': gallery})
    return {'ok': True, 'description': new_desc}


@app.delete('/panel/agents/designer/gallery/{ref_id}')
async def delete_designer_gallery(ref_id: str, request: Request, page_id: str = '', panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    page_id = str(page_id or '').strip()
    if not page_id:
        return JSONResponse({'ok': False, 'error': 'missing_page_id'}, status_code=400)
    profile = get_brand_profile(page_id)
    gallery = list(profile.get('gallery_references') or [])
    ref = next((r for r in gallery if r.get('id') == ref_id), None)
    if ref:
        try:
            Path(ref.get('path', '')).unlink(missing_ok=True)
        except Exception:
            pass
        upsert_brand_profile(page_id, {'gallery_references': [r for r in gallery if r.get('id') != ref_id]})
    return {'ok': True}


def _scrape_website(url: str, timeout: int = 12) -> str:
    """Fetch a website and return a cleaned text excerpt for AI analysis."""
    import re
    try:
        req = urllib.request.Request(
            url.strip(),
            headers={'User-Agent': 'Mozilla/5.0 (compatible; MetaPanelBot/1.0)'},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(200_000).decode('utf-8', errors='replace')
    except Exception:
        return ''
    raw = re.sub(r'<script[^>]*>.*?</script>', ' ', raw, flags=re.DOTALL | re.IGNORECASE)
    raw = re.sub(r'<style[^>]*>.*?</style>', ' ', raw, flags=re.DOTALL | re.IGNORECASE)
    title_m = re.search(r'<title[^>]*>([^<]+)</title>', raw, re.IGNORECASE)
    desc_m = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']{10,})["\']', raw, re.IGNORECASE)
    og_desc = re.search(r'<meta[^>]*property=["\']og:description["\'][^>]*content=["\']([^"\']{10,})["\']', raw, re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', raw)
    text = re.sub(r'\s+', ' ', text).strip()[:5000]
    parts = []
    if title_m:
        parts.append(f'Título: {title_m.group(1).strip()}')
    if desc_m:
        parts.append(f'Meta descrição: {desc_m.group(1).strip()}')
    if og_desc and (not desc_m or og_desc.group(1) != desc_m.group(1)):
        parts.append(f'OG descrição: {og_desc.group(1).strip()}')
    parts.append(f'Conteúdo: {text}')
    return '\n'.join(parts)


@app.post('/panel/onboarding/analyze')
async def panel_onboarding_analyze(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    body = await request.json()
    page_id = str(body.get('page_id', '') or '').strip()
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if page_id and user and not page_allowed_for_user(user, str(page_id)):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    website_url = str(body.get('website_url', '') or '').strip()
    instagram_handle = str(body.get('instagram_handle', '') or '').lstrip('@').strip()
    brief_description = str(body.get('description', '') or '').strip()
    reference_websites = [str(v or '').strip() for v in (body.get('reference_websites') or []) if str(v or '').strip()]
    reference_instagrams = [str(v or '').lstrip('@').strip() for v in (body.get('reference_instagrams') or []) if str(v or '').strip()]

    site_content = ''
    if website_url:
        if not website_url.startswith('http'):
            website_url = 'https://' + website_url
        site_content = _scrape_website(website_url)

    reference_site_chunks: list[str] = []
    for ref_url in reference_websites[:3]:
        url = ref_url if ref_url.startswith('http') else f'https://{ref_url}'
        try:
            reference_site_chunks.append(f'Referência de site {url}: {_scrape_website(url)[:1500]}')
        except Exception:
            reference_site_chunks.append(f'Referência de site: {url}')

    ig_context = ''
    if instagram_handle:
        # Try to get IG bio from connected accounts if available
        session = load_json(META_SESSION_PATH, {})
        for pg in session.get('pages', []):
            ig = (pg.get('instagram_business_account') or {})
            if str(ig.get('username', '')).lower() == instagram_handle.lower():
                ig_context = f"Instagram @{instagram_handle}: {ig.get('biography','')}, {ig.get('followers_count',0)} seguidores."
                break
        if not ig_context:
            ig_context = f"Instagram: @{instagram_handle}"

    reference_ig_lines: list[str] = []
    if reference_instagrams:
        session = load_json(META_SESSION_PATH, {})
        for handle in reference_instagrams[:5]:
            line = f'Referência Instagram: @{handle}'
            for pg in session.get('pages', []):
                ig = (pg.get('instagram_business_account') or {})
                if str(ig.get('username', '')).lower() == handle.lower():
                    line = f'Referência Instagram @{handle}: {ig.get("biography","")}, {ig.get("followers_count",0)} seguidores.'
                    break
            reference_ig_lines.append(line)

    profile = get_brand_profile(page_id) if page_id else {}
    visual_refs = profile.get('visual_references') if isinstance(profile.get('visual_references'), list) else []
    ref_labels = [str((ref or {}).get('label', '') or (ref or {}).get('filename', '') or '').strip() for ref in visual_refs if isinstance(ref, dict)]
    colors = [str(c).strip() for c in (profile.get('colors') or []) if str(c).strip()]
    reference_style_prompt = str(profile.get('reference_style_prompt') or '').strip()
    font_preference = str(profile.get('font_preference') or '').strip()
    reference_sites_text = '\n'.join(reference_site_chunks)
    reference_instagrams_text = '\n'.join(reference_ig_lines)

    prompt = (
        'Você é um especialista em branding e marketing digital. Analise as informações abaixo e '
        'extraia dados para preencher o perfil da marca. '
        'Retorne SOMENTE JSON válido em português do Brasil com estas chaves exatas:\n'
        '{\n'
        '  "brand_name": "nome da marca (curto)",\n'
        '  "tagline": "slogan ou tagline da marca",\n'
        '  "description": "descrição concisa do negócio (2-4 frases)",\n'
        '  "key_products": "principais produtos/serviços separados por vírgula",\n'
        '  "target_audience": "descrição do público-alvo ideal",\n'
        '  "tone": "tom de voz (ex: profissional, descontraído, técnico, empático)",\n'
        '  "best_offer": "principal proposta de valor ou oferta",\n'
        '  "visual_style": "estilo visual sugerido (ex: moderno, minimalista, colorido)",\n'
        '  "colors": ["#112233", "#445566"],\n'
        '  "font_preference": "descrição de tipografia adequada para a marca",\n'
        '  "reference_style_prompt": "resumo prático da direção visual da marca",\n'
        '  "competitors": ["@handle1", "@handle2"],\n'
        '  "icp_summary": "síntese objetiva do cliente ideal",\n'
        '  "icp_pain_points": "3 principais dores do cliente ideal",\n'
        '  "icp_desires": "3 principais desejos do cliente ideal",\n'
        '  "icp_objections": "principais objeções de compra"\n'
        '}\n\n'
        f'{"Site: " + site_content[:4000] if site_content else ""}\n'
        f'{ig_context}\n'
        f'{reference_sites_text}\n' if reference_sites_text else ''
        f'{reference_instagrams_text}\n' if reference_instagrams_text else ''
        f'{"Referências visuais enviadas: " + ", ".join(v for v in ref_labels if v) if ref_labels else ""}\n'
        f'{"Paleta atual detectada: " + ", ".join(colors) if colors else ""}\n'
        f'{"Direção visual detectada: " + reference_style_prompt if reference_style_prompt else ""}\n'
        f'{"Preferência tipográfica atual: " + font_preference if font_preference else ""}\n'
        f'{"Descrição fornecida: " + brief_description if brief_description else ""}\n'
        'Sem markdown, sem explicações, apenas o JSON.'
    )
    try:
        result = _ai_generate_text('brand_analysis', prompt, 60, json_mode=True)
        parsed = _extract_json_block(result.get('text') or '')
        if not isinstance(parsed, dict):
            return JSONResponse({'ok': False, 'error': 'ai_parse_failed'}, status_code=400)
        return {
            'ok': True,
            'profile': parsed,
            'site_scraped': bool(site_content),
            'usage': result.get('usage', {}),
        }
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=400)


@app.post('/panel/onboarding/save')
async def panel_onboarding_save(request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    if not _panel_auth_ok(request, panel_auth or '', panel_user or ''):
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    body = await request.json()
    page_id = str(body.get('page_id', '') or '').strip()
    if not page_id:
        return JSONResponse({'ok': False, 'error': 'missing_page_id'}, status_code=400)
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if user and not page_allowed_for_user(user, str(page_id)):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    profile_data = body.get('profile', {}) or {}
    icp_data = body.get('icp', {}) or {}
    allowed = ['brand_name', 'tagline', 'description', 'key_products', 'target_audience',
               'tone', 'best_offer', 'visual_style', 'font_preference', 'reference_style_prompt']
    updates = {k: str(v or '').strip() for k, v in profile_data.items() if k in allowed}
    raw_colors = profile_data.get('colors', [])
    if isinstance(raw_colors, str):
        parsed_colors = [v.strip() for v in raw_colors.split(',') if v.strip()]
    elif isinstance(raw_colors, list):
        parsed_colors = [str(v).strip() for v in raw_colors if str(v).strip()]
    else:
        parsed_colors = []
    if parsed_colors:
        updates['colors'] = parsed_colors
    competitors = profile_data.get('competitors', '')
    if isinstance(competitors, str) and competitors.strip():
        updates['competitors'] = [v.strip() for v in competitors.split(',') if v.strip()]
    elif isinstance(competitors, list):
        updates['competitors'] = [str(v).strip() for v in competitors if str(v).strip()]
    if icp_data:
        lines = []
        if icp_data.get('icp_summary'):
            lines.append(f"Resumo: {icp_data.get('icp_summary', '')}")
        lines.extend([
            f"Dores: {icp_data.get('icp_pain_points', '')}",
            f"Desejos: {icp_data.get('icp_desires', '')}",
            f"Objeções: {icp_data.get('icp_objections', '')}",
        ])
        updates['icp_onboarding_text'] = '\n'.join(lines)
    profile = upsert_brand_profile(page_id, updates)
    try:
        _build_company_agent_adjustments(page_id)
    except Exception:
        pass
    profile = get_brand_profile(page_id)
    return {'ok': True, 'profile': profile}


# ══════════════════════════════════════════════════════════════════════════════
# API EXTERNA – Autenticação por API Key (Bearer token)
# ══════════════════════════════════════════════════════════════════════════════

def _generate_api_key() -> str:
    import secrets
    return 'mpk_' + secrets.token_hex(32)


def _api_key_auth(request: Request) -> dict:
    """Valida o header Authorization: Bearer mpk_... e retorna o registro da key ou None."""
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None
    key = auth_header[7:].strip()
    if not key:
        return None
    keys = load_api_keys()
    return keys.get(key)


def _require_admin_or_api_key(request: Request, admin_token: str = '') -> bool:
    """Retorna True se a requisição tem admin_token válido OU uma API key válida."""
    master = get_secret(PANEL_ADMIN_TOKEN_NAME)
    if admin_token and master and admin_token == master:
        return True
    return bool(_api_key_auth(request))


@app.post('/api/keys/create')
async def api_key_create(request: Request):
    """
    Cria uma nova API key para uso externo.
    Body: { admin_token: str, name: str, page_id?: str, scopes?: [str] }
    Requer admin_token master.
    Retorna a key UMA VEZ – guarde-a, não é possível recuperar depois.
    """
    body = await request.json()
    master = get_secret(PANEL_ADMIN_TOKEN_NAME)
    if not master or body.get('admin_token', '') != master:
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    name = (body.get('name', '') or '').strip()
    if not name:
        return JSONResponse({'ok': False, 'error': 'missing_name'}, status_code=400)
    key = _generate_api_key()
    record = {
        'key': key,
        'name': name,
        'page_id': body.get('page_id', ''),
        'scopes': body.get('scopes', ['instagram', 'facebook', 'ads', 'leads']),
        'created_at': int(time.time()),
        'active': True,
    }
    keys = load_api_keys()
    keys[key] = record
    save_api_keys(keys)
    return {'ok': True, 'key': key, 'record': record}


@app.get('/api/keys')
async def api_key_list(request: Request):
    """
    Lista todas as API keys ativas. Requer admin_token no header X-Admin-Token.
    """
    master = get_secret(PANEL_ADMIN_TOKEN_NAME)
    if not master or request.headers.get('X-Admin-Token', '') != master:
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    keys = load_api_keys()
    safe = []
    for k, v in keys.items():
        row = dict(v)
        masked = k[:8] + '****' + k[-4:]
        row['key_masked'] = masked
        row.pop('key', None)
        safe.append(row)
    safe.sort(key=lambda r: r.get('created_at', 0), reverse=True)
    return {'ok': True, 'keys': safe, 'total': len(safe)}


@app.delete('/api/keys/{key_prefix}')
async def api_key_revoke(key_prefix: str, request: Request):
    """
    Revoga uma API key pelo prefixo (primeiros 12 chars).
    Requer admin_token no header X-Admin-Token.
    """
    master = get_secret(PANEL_ADMIN_TOKEN_NAME)
    if not master or request.headers.get('X-Admin-Token', '') != master:
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    keys = load_api_keys()
    matched = [k for k in keys if k.startswith(key_prefix)]
    if not matched:
        return JSONResponse({'ok': False, 'error': 'key_not_found'}, status_code=404)
    for k in matched:
        del keys[k]
    save_api_keys(keys)
    return {'ok': True, 'revoked': len(matched)}


# ══════════════════════════════════════════════════════════════════════════════
# API EXTERNA – Instagram: Preparar post (criar container + poll até FINISHED)
# ══════════════════════════════════════════════════════════════════════════════

@app.post('/api/instagram/prepare-post')
async def api_instagram_prepare_post(request: Request):
    """
    Endpoint unificado: cria o container de mídia Instagram + faz poll até FINISHED.
    Retorna o container_id pronto para ser publicado via /meta/instagram-media/publish
    ou agendado via /schedule/post/add.

    Auth: Authorization: Bearer mpk_... OU admin_token no body.
    Body: {
        image_url: str,          # URL pública da imagem (obrigatório)
        caption: str,            # legenda (opcional)
        ig_user_id: str,         # ID da conta Instagram Business (obrigatório se page_id ausente)
        access_token: str,       # page access token (obrigatório se page_id ausente)
        page_id: str,            # alternativa a ig_user_id+access_token
        admin_token: str,        # alternativa ao Bearer token
        poll_timeout_s: int,     # segundos máx de espera pelo FINISHED (default: 30)
    }
    """
    cfg = load_config()
    body = await request.json()

    if not _require_admin_or_api_key(request, body.get('admin_token', '')):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)

    image_url = (body.get('image_url', '') or '').strip()
    caption = body.get('caption', '') or ''
    if not image_url:
        return JSONResponse({'ok': False, 'error': 'missing_image_url'}, status_code=400)

    effective_ig_user_id, effective_token, effective_host = _resolve_ig_context(body)
    if not effective_ig_user_id or not effective_token:
        return JSONResponse({'ok': False, 'error': 'missing_instagram_auth_context', 'detail': 'Passe ig_user_id+access_token ou page_id no body'}, status_code=400)

    poll_timeout = min(int(body.get('poll_timeout_s', 30) or 30), 120)

    try:
        create_result = instagram_create_media(cfg, effective_ig_user_id, effective_token, image_url, caption, host=effective_host)
        if 'error' in create_result:
            return JSONResponse({'ok': False, 'error': 'container_create_failed', 'detail': create_result['error']}, status_code=400)
        container_id = create_result.get('id', '')
        if not container_id:
            return JSONResponse({'ok': False, 'error': 'container_create_failed', 'detail': create_result}, status_code=400)
    except urllib.error.HTTPError as e:
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': e.read().decode('utf-8', errors='replace')}, status_code=400)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'container_create_failed', 'detail': str(e)}, status_code=400)

    # Poll até FINISHED ou timeout
    import asyncio
    deadline = time.time() + poll_timeout
    status_result = {}
    status_code = ''
    poll_count = 0
    while time.time() < deadline:
        try:
            status_result = instagram_check_container_status(cfg, container_id, effective_token, host=effective_host)
            status_code = status_result.get('status_code', '')
            poll_count += 1
            if status_code == 'FINISHED':
                break
            if status_code == 'ERROR':
                return JSONResponse({'ok': False, 'error': 'container_processing_error', 'container_id': container_id, 'status': status_result}, status_code=400)
            if status_code == 'EXPIRED':
                return JSONResponse({'ok': False, 'error': 'container_expired', 'container_id': container_id}, status_code=400)
        except Exception:
            pass
        await asyncio.sleep(2)

    if status_code != 'FINISHED':
        return JSONResponse({
            'ok': False,
            'error': 'container_not_ready',
            'container_id': container_id,
            'status_code': status_code,
            'detail': f'Container ainda não FINISHED após {poll_timeout}s. Verifique o status manualmente e publique depois.',
            'publish_url': f'/meta/instagram-media/publish',
        }, status_code=202)

    return {
        'ok': True,
        'container_id': container_id,
        'ig_user_id': effective_ig_user_id,
        'access_token': effective_token,
        'status_code': status_code,
        'poll_count': poll_count,
        'image_url': image_url,
        'caption': caption,
        'next_steps': {
            'publish_now': {
                'method': 'POST',
                'url': '/meta/instagram-media/publish',
                'body': {'admin_token': '...', 'ig_user_id': effective_ig_user_id, 'creation_id': container_id, 'access_token': effective_token},
            },
            'schedule': {
                'method': 'POST',
                'url': '/schedule/post/add',
                'body': {'admin_token': '...', 'ig_user_id': effective_ig_user_id, 'access_token': effective_token, 'image_url': image_url, 'caption': caption, 'scheduled_at': '<unix_timestamp>'},
            },
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# API EXTERNA – Lead Form Responses (submissões de formulários de Lead Ads)
# ══════════════════════════════════════════════════════════════════════════════

@app.get('/meta/leadgen-form/{form_id}/leads')
def meta_leadgen_form_leads(
    form_id: str,
    request: Request,
    page_id: str = '',
    limit: int = 100,
    after: str = '',
):
    """
    Retorna as submissões (respostas) de um formulário de Lead Ad.
    Auth: Authorization: Bearer mpk_... OU X-Admin-Token: master_token OU page_id que resolve token interno.

    Query params:
      page_id  – ID da Página Facebook para buscar o access_token internamente (recomendado)
      limit    – máx de leads por página (default 100, máx 100)
      after    – cursor de paginação para a próxima página
    """
    cfg = load_config()

    # Auth: API key ou admin token no header
    api_key_record = _api_key_auth(request)
    master = get_secret(PANEL_ADMIN_TOKEN_NAME)
    admin_header = request.headers.get('X-Admin-Token', '')
    has_admin = bool(master and admin_header == master)
    if not api_key_record and not has_admin and not page_id:
        return JSONResponse({'ok': False, 'error': 'forbidden', 'detail': 'Passe Authorization: Bearer mpk_... ou X-Admin-Token, ou page_id para resolução automática'}, status_code=403)

    # Resolve access token
    access_token = ''
    if page_id:
        access_token = get_page_access_token(page_id)
    if not access_token:
        access_token = get_meta_access_token()
    if not access_token:
        return JSONResponse({'ok': False, 'error': 'no_access_token', 'detail': 'Não foi possível obter access_token para este page_id'}, status_code=400)

    limit = max(1, min(int(limit), 100))
    params = {
        'fields': 'id,created_time,field_data,ad_id,ad_name,adset_id,adset_name,campaign_id,campaign_name,form_id,is_organic,platform',
        'access_token': access_token,
        'limit': str(limit),
    }
    if after:
        params['after'] = after

    url = f"https://graph.facebook.com/{cfg['graph_api_version']}/{form_id}/leads?{urllib.parse.urlencode(params)}"
    try:
        result = graph_get(url)
        leads = result.get('data', [])
        paging = result.get('paging', {})
        cursors = paging.get('cursors', {})
        return {
            'ok': True,
            'form_id': form_id,
            'total_returned': len(leads),
            'leads': leads,
            'paging': {
                'has_next': bool(paging.get('next', '')),
                'cursor_after': cursors.get('after', ''),
                'cursor_before': cursors.get('before', ''),
                'next': paging.get('next', ''),
            },
        }
    except urllib.error.HTTPError as e:
        body_text = e.read().decode('utf-8', errors='replace')
        return JSONResponse({'ok': False, 'error': 'http_error', 'detail': body_text}, status_code=400)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'leads_fetch_failed', 'detail': str(e)}, status_code=400)


@app.get('/meta/leadgen-form/{form_id}/leads/export')
def meta_leadgen_form_leads_export(
    form_id: str,
    request: Request,
    page_id: str = '',
    format: str = 'json',
):
    """
    Exporta TODAS as submissões de um formulário (pagina automaticamente até buscar tudo).
    format: 'json' | 'csv'
    """
    cfg = load_config()

    api_key_record = _api_key_auth(request)
    master = get_secret(PANEL_ADMIN_TOKEN_NAME)
    admin_header = request.headers.get('X-Admin-Token', '')
    has_admin = bool(master and admin_header == master)
    if not api_key_record and not has_admin and not page_id:
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)

    access_token = ''
    if page_id:
        access_token = get_page_access_token(page_id)
    if not access_token:
        access_token = get_meta_access_token()
    if not access_token:
        return JSONResponse({'ok': False, 'error': 'no_access_token'}, status_code=400)

    all_leads = []
    cursor_after = ''
    page_num = 0
    max_pages = 50  # segurança: máx 5000 leads

    while page_num < max_pages:
        params = {
            'fields': 'id,created_time,field_data,ad_id,ad_name,adset_name,campaign_name,is_organic,platform',
            'access_token': access_token,
            'limit': '100',
        }
        if cursor_after:
            params['after'] = cursor_after
        url = f"https://graph.facebook.com/{cfg['graph_api_version']}/{form_id}/leads?{urllib.parse.urlencode(params)}"
        try:
            result = graph_get(url)
        except Exception as e:
            return JSONResponse({'ok': False, 'error': 'leads_fetch_failed', 'detail': str(e), 'collected_so_far': len(all_leads)}, status_code=400)

        batch = result.get('data', [])
        all_leads.extend(batch)
        page_num += 1
        paging = result.get('paging', {})
        cursor_after = paging.get('cursors', {}).get('after', '')
        if not paging.get('next') or not batch:
            break

    if format == 'csv':
        import csv, io
        # Flatten field_data para colunas
        field_names_set = []
        for lead in all_leads:
            for fd in lead.get('field_data', []):
                n = fd.get('name', '')
                if n and n not in field_names_set:
                    field_names_set.append(n)
        base_cols = ['id', 'created_time', 'ad_name', 'adset_name', 'campaign_name', 'is_organic', 'platform']
        all_cols = base_cols + field_names_set
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=all_cols, extrasaction='ignore')
        writer.writeheader()
        for lead in all_leads:
            row = {c: lead.get(c, '') for c in base_cols}
            for fd in lead.get('field_data', []):
                vals = fd.get('values', [])
                row[fd.get('name', '')] = ', '.join(vals) if vals else ''
            writer.writerow(row)
        csv_content = buf.getvalue()
        from fastapi.responses import Response as FastResponse
        return FastResponse(
            content=csv_content.encode('utf-8-sig'),
            media_type='text/csv',
            headers={'Content-Disposition': f'attachment; filename="leads_{form_id}.csv"'},
        )

    return {
        'ok': True,
        'form_id': form_id,
        'total': len(all_leads),
        'pages_fetched': page_num,
        'leads': all_leads,
    }


# ── CRM routes ──────────────────────────────────────────────────────────────

@app.get('/panel/companies/{company_id}/leadgen-forms')
def panel_company_leadgen_forms(company_id: str, request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not user:
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    companies = load_companies()
    company = companies.get(company_id)
    if not company:
        return JSONResponse({'ok': False, 'error': 'not_found'}, status_code=404)
    page_id = str(((company.get('bindings') or {}).get('meta') or {}).get('page_id') or '')
    if not page_id:
        return {'ok': True, 'forms': []}
    if not is_admin_user(user) and not page_allowed_for_user(user, page_id):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    cfg = load_config()
    try:
        result = fetch_page_leadgen_forms(cfg, page_id, timeout=12)
        return {'ok': True, 'forms': result.get('data', [])}
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=400)


@app.get('/panel/companies/{company_id}/crm-config')
def panel_company_crm_config_get(company_id: str, request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not user:
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    companies = load_companies()
    company = companies.get(company_id)
    if not company:
        return JSONResponse({'ok': False, 'error': 'not_found'}, status_code=404)
    page_id = str(((company.get('bindings') or {}).get('meta') or {}).get('page_id') or '')
    if page_id and not is_admin_user(user) and not page_allowed_for_user(user, page_id):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    crm = (company.get('bindings') or {}).get('crm') or {}
    return {'ok': True, 'crm': crm}


@app.post('/panel/companies/{company_id}/crm-config')
async def panel_company_crm_config_save(company_id: str, request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not user:
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    companies = load_companies()
    company = companies.get(company_id)
    if not company:
        return JSONResponse({'ok': False, 'error': 'not_found'}, status_code=404)
    page_id = str(((company.get('bindings') or {}).get('meta') or {}).get('page_id') or '')
    if page_id and not is_admin_user(user) and not page_allowed_for_user(user, page_id):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    body = await request.json()
    crm = company.setdefault('bindings', {}).setdefault('crm', {})
    crm['enabled'] = bool(body.get('enabled', False))
    crm['webhook_url'] = str(body.get('webhook_url') or '').strip()
    pipeline_raw = body.get('pipeline_id')
    stage_raw = body.get('stage_id')
    crm['pipeline_id'] = int(pipeline_raw) if pipeline_raw and str(pipeline_raw).strip().isdigit() else (pipeline_raw or None)
    crm['stage_id'] = int(stage_raw) if stage_raw and str(stage_raw).strip().isdigit() else (stage_raw or None)
    if 'custom_fields' in body:
        crm['custom_fields'] = body['custom_fields'] or {}
    if 'form_ids' in body:
        crm['form_ids'] = [str(f) for f in (body['form_ids'] or []) if str(f).strip()]
    if 'field_map' in body:
        crm['field_map'] = body['field_map'] or {}
    companies[company_id] = company
    save_companies(companies)
    return {'ok': True, 'crm': crm}


@app.post('/panel/companies/{company_id}/crm-sync')
async def panel_company_crm_sync(company_id: str, request: Request, panel_auth: Optional[str] = Cookie(default=None), panel_user: Optional[str] = Cookie(default=None)):
    user = current_panel_user(panel_auth or '', panel_user or '', request=request)
    if not user:
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    companies = load_companies()
    company = companies.get(company_id)
    if not company:
        return JSONResponse({'ok': False, 'error': 'not_found'}, status_code=404)
    page_id = str(((company.get('bindings') or {}).get('meta') or {}).get('page_id') or '')
    if page_id and not is_admin_user(user) and not page_allowed_for_user(user, page_id):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    result = sync_company_leads_to_crm(company_id, company)
    if result.get('ok') and not result.get('skipped'):
        companies = load_companies()
        if company_id in companies:
            companies[company_id].setdefault('bindings', {}).setdefault('crm', {})['last_sync_at'] = int(time.time())
            companies[company_id]['bindings']['crm']['last_sync_result'] = result.get('summary', '')
            save_companies(companies)
    return {**result, 'ok': True}


@app.get('/studio', response_class=HTMLResponse)
def studio_page():
    admin_token = get_secret(PANEL_ADMIN_TOKEN_NAME)
    html = '''<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Studio — Marketing Inc.Digital</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f1f5f9;color:#1e293b}
#app{display:flex;min-height:100vh}
#sidebar{width:240px;flex-shrink:0;background:#1a1f2e;display:flex;flex-direction:column;min-height:100vh;overflow-y:auto}
.sidebar-brand{padding:18px 20px;color:#fff;font-size:15px;font-weight:800;border-bottom:1px solid #232b3e;letter-spacing:-.3px;line-height:1.3}.sidebar-brand span{color:#F97316}.sidebar-brand .sub{font-size:10px;font-weight:400;color:#64748b;letter-spacing:.05em;text-transform:uppercase;display:block;margin-top:2px}
.sidebar-nav{flex:1;padding:8px 0}.sidebar-nav a{display:flex;align-items:center;gap:10px;padding:10px 20px;color:#94a3b8;font-size:14px;cursor:pointer;text-decoration:none;transition:all .15s}.sidebar-nav a:hover{background:#232b3e;color:#e2e8f0}.sidebar-nav a.active{background:#232b3e;color:#F97316;font-weight:600;border-left:3px solid #F97316}.sidebar-nav .divider{height:1px;background:#232b3e;margin:6px 0}.sidebar-footer{padding:14px 20px;border-top:1px solid #232b3e}.sidebar-footer a{color:#64748b;font-size:13px;cursor:pointer;text-decoration:none}
#content{flex:1;padding:28px;overflow-y:auto}
.page-header{display:flex;align-items:center;justify-content:space-between;gap:14px;margin-bottom:24px}.page-header h1{font-size:22px;font-weight:800;letter-spacing:-.3px}.page-header h1 span{color:#F97316}.page-header a{font-size:13px;color:#F97316;text-decoration:none}
.card{background:#fff;border-radius:12px;padding:20px;box-shadow:0 1px 3px rgba(0,0,0,.08);margin-bottom:16px}
.card-title{font-size:14px;font-weight:600;color:#0f172a;margin-bottom:14px}
label{display:block;font-size:11px;font-weight:600;color:#475569;margin-bottom:4px;text-transform:uppercase;letter-spacing:.04em;margin-top:12px}
input,textarea,select{width:100%;padding:9px 12px;border:1px solid #e2e8f0;border-radius:8px;font-size:14px;outline:none;background:#fff;color:#1e293b;font-family:inherit}
input:focus,textarea:focus,select:focus{border-color:#F97316;box-shadow:0 0 0 3px rgba(249,115,22,.12)}
textarea{resize:vertical;min-height:80px}
.btn{display:inline-flex;align-items:center;gap:6px;padding:9px 16px;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;border:none;transition:all .15s;font-family:inherit}
.btn-primary{background:#F97316;color:#fff}.btn-primary:hover{background:#EA580C}
.btn-success{background:#22c55e;color:#fff}.btn-success:hover{background:#16a34a}
.btn-outline{background:transparent;border:1px solid #e2e8f0;color:#475569}.btn-outline:hover{background:#f8fafc}
.btn:disabled{background:#cbd5e1;color:#94a3b8;cursor:not-allowed}
.btn-group{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
.tabs{display:flex;gap:3px;background:#f1f5f9;padding:4px;border-radius:10px;margin-bottom:16px}.tab{padding:7px 16px;border-radius:7px;font-size:13px;font-weight:500;cursor:pointer;color:#64748b;border:none;background:transparent;font-family:inherit}.tab.active{background:#fff;color:#F97316;box-shadow:0 1px 3px rgba(0,0,0,.1)}
.tab-panel{display:none}.tab-panel.active{display:block}
.loader{color:#64748b;font-size:13px;font-style:italic;margin-top:8px;display:none}.result-ok{color:#16a34a;font-size:13px;font-weight:600;margin-top:8px}.result-err{color:#dc2626;font-size:13px;font-weight:600;margin-top:8px}
.preview-img{max-width:100%;max-height:360px;border-radius:8px;border:1px solid #e2e8f0;display:block;margin-bottom:8px}.debug-box{background:#1a1f2e;color:#86efac;font-family:monospace;font-size:11px;padding:12px;border-radius:8px;max-height:280px;overflow-y:auto;margin-top:10px;white-space:pre-wrap;display:none}
.upload-area{border:2px dashed #cbd5e1;border-radius:8px;padding:24px;text-align:center;cursor:pointer;transition:border-color .15s}.upload-area:hover{border-color:#F97316}
.step-badge{display:inline-block;background:#fff7ed;color:#C2410C;border-radius:12px;font-size:11px;font-weight:700;padding:2px 10px;margin-right:6px}
@media (max-width: 900px){#app{display:block}#sidebar{width:100%;min-height:auto}#content{padding:18px}}
</style>
</head>
<body>
<div id="app">
  <nav id="sidebar">
    <div class="sidebar-brand">Marketing <span>Inc.Digital</span><span class="sub">Painel de Marketing</span></div>
    <div class="sidebar-nav">
      <a href="/">📊 Dashboard</a>
      <a href="/">🏢 Empresas</a>
      <a href="/">⚙️ Configuração</a>
      <a href="/">🔗 Conexões & OAuth</a>
      <a href="/">📄 Páginas</a>
      <a href="/">🎨 Brand Profiles</a>
      <a href="/">👥 Usuários</a>
      <a href="/">🔑 API Keys</a>
      <div class="divider"></div>
      <a href="/">✉️ Publicar</a>
      <a href="/" class="active">🧠 Planejamento</a>
      <a href="/">📅 Agenda</a>
      <a href="/">📢 Anúncios</a>
      <div class="divider"></div>
      <a href="/studio" class="active">🖼️ Studio</a>
    </div>
    <div class="sidebar-footer"><a href="/">← Voltar ao Painel</a></div>
  </nav>
  <main id="content">
<div class="page-header">
  <h1>🖼️ Studio <span style="font-size:14px;font-weight:400;color:#64748b">— Marketing <span>Inc.Digital</span></span></h1>
  <a href="/">← Voltar ao Painel</a>
</div>

<!-- Conta -->
<div class="card">
  <div class="card-title"><span class="step-badge">1</span>Conta Instagram</div>
  <label>Selecionar conta</label>
  <select id="account-select"><option value="">Carregando contas...</option></select>
</div>

<!-- Origem da imagem -->
<div class="card">
  <div class="card-title"><span class="step-badge">2</span>Origem da Imagem & Copy</div>
  <div class="tabs">
    <button class="tab active" onclick="switchTab('tab-ai')">🤖 Gerar com IA</button>
    <button class="tab" onclick="switchTab('tab-upload')">📁 Importar Arquivo</button>
    <button class="tab" onclick="switchTab('tab-url')">🔗 Colar URL</button>
    <button class="tab" onclick="switchTab('tab-gallery')">🗂️ Galeria</button>
  </div>

  <!-- Tab IA -->
  <div id="tab-ai" class="tab-panel active">
    <label>Briefing (descreva o post)</label>
    <textarea id="briefing" rows="3" placeholder="Ex: Post sobre lançamento de apartamentos de luxo em Alphaville, destaque para piscina e área gourmet..."></textarea>
    <label>Logo da marca (URL PNG)</label>
    <input id="art-logo-url" placeholder="https://...logo.png"/>
    <label>Cores da marca</label>
    <input id="art-colors" placeholder="#F97316, #FFFFFF, #111827"/>
    <label>Formato</label>
    <select id="art-aspect-ratio"><option value="1:1">1:1</option><option value="4:5">4:5</option><option value="16:9">16:9</option><option value="4:1">4:1</option></select>
    <label>Fonte desejada</label>
    <input id="art-font" placeholder="Ex: Montserrat Bold ou usar da referência"/>
    <label>Referências visuais (uma por linha)</label>
    <textarea id="art-references" rows="3" placeholder="https://...\nhttps://...\nOu descreva a referência"></textarea>
    <label>Regras de texto na arte</label>
    <textarea id="art-text-rule" rows="2" placeholder="Ex: sem texto, ou headline curta central"></textarea>
    <label>O que NÃO pode inventar</label>
    <textarea id="art-negative-rules" rows="3" placeholder="Ex: não inventar marca, não criar travel brand, não usar avião, não usar praia"></textarea>
    <div class="btn-group">
      <button class="btn btn-outline" id="btn-copy-only" onclick="generateCopy()">✍️ Gerar Copy</button>
      <button class="btn btn-primary" id="btn-gen-full" onclick="generateFull()">🚀 Gerar Copy + Imagem IA</button>
    </div>
    <div id="loader-copy" class="loader">Gerando copy com IA...</div>
    <div id="loader-image" class="loader">Gerando imagem com IA... (30-60s)</div>
    <div id="image-prompt-row" style="display:none">
      <label>Prompt da imagem (editável)</label>
      <textarea id="image-prompt-txt" rows="2"></textarea>
      <div class="btn-group">
        <button class="btn btn-outline" id="btn-gen-img" onclick="generateImageFromPrompt()">🎨 Gerar Imagem com esse Prompt</button>
      </div>
    </div>
  </div>

  <!-- Tab Upload -->
  <div id="tab-upload" class="tab-panel">
    <div class="upload-area" id="upload-area" onclick="document.getElementById('file-input').click()">
      <div style="font-size:32px;margin-bottom:8px">📂</div>
      <div style="font-size:14px;color:#475569">Clique para selecionar ou arraste a imagem aqui</div>
      <div style="font-size:12px;color:#94a3b8;margin-top:4px">JPG, PNG, WEBP — será convertida para JPEG</div>
    </div>
    <input type="file" id="file-input" accept="image/*" style="display:none" onchange="uploadFile(this)"/>
    <div id="loader-upload" class="loader">Enviando imagem...</div>
  </div>

  <!-- Tab URL -->
  <div id="tab-url" class="tab-panel">
    <label>URL pública da imagem (HTTPS)</label>
    <input type="url" id="url-input" placeholder="https://exemplo.com/imagem.jpg"/>
    <div class="btn-group">
      <button class="btn btn-outline" onclick="useUrl()">✅ Usar esta URL</button>
    </div>
  </div>

  <!-- Tab Galeria -->
  <div id="tab-gallery" class="tab-panel">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
      <span style="font-size:13px;color:#64748b">Imagens já geradas — clique para usar</span>
      <button class="btn btn-outline" style="padding:5px 10px;font-size:12px" onclick="loadGallery()">🔄 Atualizar</button>
    </div>
    <div id="gallery-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:10px">
      <div style="color:#94a3b8;font-size:13px;grid-column:1/-1">Carregando galeria...</div>
    </div>
  </div>
</div>

<!-- Preview & Copy -->
<div class="card" id="preview-section" style="display:none">
  <div class="card-title"><span class="step-badge">3</span>Preview & Edição</div>
  <img id="preview-img" class="preview-img" src="" alt="Preview">
  <input type="hidden" id="image-url"/>
  <label>Legenda (Copy)</label>
  <textarea id="caption" rows="6" placeholder="Escreva a legenda do post..."></textarea>
</div>

<!-- Publicar -->
<div class="card" id="publish-section" style="display:none">
  <div class="card-title"><span class="step-badge">4</span>Publicar no Instagram</div>
  <div class="btn-group">
    <button class="btn btn-outline" id="btn-validate" onclick="validateMedia()">🔍 Validar Mídia</button>
    <button class="btn btn-outline" id="btn-create" onclick="createContainer()">📦 Criar Container</button>
    <button class="btn btn-success" id="btn-post" onclick="publishPost()">🚀 Publicar</button>
  </div>
  <div id="loader-post" class="loader">Processando...</div>
  <div id="post-result"></div>
  <div id="creation-id-row" style="display:none;margin-top:10px">
    <label>Container ID (criado)</label>
    <input id="creation-id-txt" readonly style="background:#f8fafc"/>
  </div>
  <div id="debug-box" class="debug-box"></div>
</div>

<script>
const ADMIN_TOKEN = ''' + json.dumps(admin_token or '') + ''';
let lastCreationId = '';

function j(id){return document.getElementById(id);}
function g(id){return (j(id)||{}).value||'';}
function show(id){const el=j(id);if(el)el.style.display='block';}
function hide(id){const el=j(id);if(el)el.style.display='none';}

const TAB_ORDER=['tab-ai','tab-upload','tab-url','tab-gallery'];
function switchTab(tabId){
  document.querySelectorAll('.tab-panel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  j(tabId).classList.add('active');
  const idx=TAB_ORDER.indexOf(tabId);
  if(idx>=0)document.querySelectorAll('.tab')[idx].classList.add('active');
  if(tabId==='tab-gallery')loadGallery();
}

function setResult(msg, ok){
  const el=j('post-result');
  el.className=ok?'result-ok':'result-err';
  el.textContent=msg;
}
function setBusy(on){
  j('loader-post').style.display=on?'block':'none';
  ['btn-validate','btn-create','btn-post'].forEach(id=>{const el=j(id);if(el)el.disabled=on;});
}
function debug(data){
  const box=j('debug-box');
  box.style.display='block';
  box.textContent=JSON.stringify(data,null,2);
}
function showPreview(url, copyText){
  j('preview-img').src=url;
  j('image-url').value=url;
  if(copyText !== undefined) j('caption').value=copyText;
  show('preview-section');
  show('publish-section');
  lastCreationId='';
}
async function postJson(url, body){
  const res=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const data=await res.json().catch(()=>({ok:false,error:'invalid_json'}));
  return {status:res.status,data};
}
function selectedAccount(){
  const raw=g('account-select');
  if(!raw)throw new Error('Selecione uma conta do Instagram.');
  return JSON.parse(raw);
}
function artDirection(){
  return {
    logo_url:g('art-logo-url'),
    colors:(g('art-colors')||'').split(',').map(x=>x.trim()).filter(Boolean),
    aspect_ratio:g('art-aspect-ratio')||'1:1',
    font_preference:g('art-font'),
    references:(g('art-references')||'').split('\n').map(x=>x.trim()).filter(Boolean),
    text_rule:g('art-text-rule'),
    negative_rules:g('art-negative-rules'),
  };
}

// ── Load accounts ────────────────────────────────────────────────────────────
fetch('/meta/instagram-accounts')
  .then(r=>r.json())
  .then(data=>{
    const sel=j('account-select');
    sel.innerHTML='<option value="">— selecione a conta —</option>';
    (data.instagram_accounts||[]).forEach(acc=>{
      const ig=acc.instagram_business_account||{};
      if(!ig.id)return;
      const opt=document.createElement('option');
      opt.value=JSON.stringify({ig_user_id:ig.id,access_token:acc.page_access_token,page_id:acc.page_id,page_name:acc.page_name,username:ig.username});
      opt.text='@'+(ig.username||ig.id)+' — '+acc.page_name;
      sel.appendChild(opt);
    });
    if(!sel.options.length||sel.options.length===1)sel.innerHTML='<option value="">Nenhuma conta Instagram conectada</option>';
  }).catch(()=>{j('account-select').innerHTML='<option>Erro ao carregar contas</option>';});

// ── Tab IA: gerar só copy ────────────────────────────────────────────────────
async function generateCopy(){
  const briefing=g('briefing');
  if(!briefing)return alert('Preencha o briefing.');
  j('loader-copy').style.display='block';
  j('btn-copy-only').disabled=true;
  j('btn-gen-full').disabled=true;
  try{
    const res=await postJson('/meta/ai-copy',{briefing,art_direction:artDirection()});
    debug({step:'ai_copy',response:res.data});
    if(!res.data.ok)throw new Error(res.data.error||'falha');
    j('caption').value=res.data.copy||'';
    if(res.data.image_prompt){j('image-prompt-txt').value=res.data.image_prompt;j('image-prompt-row').style.display='block';}
    const prov=res.data.provider||'';
    j('loader-copy').textContent=prov?('✅ Copy gerada via '+prov):'✅ Copy gerada';
    j('loader-copy').style.color=prov==='fallback'?'#dc2626':'#16a34a';
    show('preview-section');
    show('publish-section');
  }catch(e){alert('Erro ao gerar copy: '+e.message);}
  finally{j('loader-copy').style.display='block';j('btn-copy-only').disabled=false;j('btn-gen-full').disabled=false;}
}

// ── Tab IA: gerar copy + imagem ──────────────────────────────────────────────
async function generateFull(){
  const briefing=g('briefing');
  if(!briefing)return alert('Preencha o briefing.');
  j('loader-image').style.display='block';
  j('btn-copy-only').disabled=true;
  j('btn-gen-full').disabled=true;
  try{
    const res=await postJson('/meta/image/generate',{briefing,prefix:'igpost',art_direction:artDirection()});
    debug({step:'generate_full',response:res.data});
    if(!res.data.ok||!res.data.public_url)throw new Error(res.data.error||'sem URL de imagem');
    showPreview(res.data.public_url,res.data.copy||'');
    if(res.data.generated?.image_prompt){j('image-prompt-txt').value=res.data.generated.image_prompt;j('image-prompt-row').style.display='block';}
  }catch(e){alert('Erro ao gerar imagem: '+e.message);}
  finally{j('loader-image').style.display='none';j('btn-copy-only').disabled=false;j('btn-gen-full').disabled=false;}
}

// ── Tab IA: gerar imagem a partir do prompt editado ──────────────────────────
async function generateImageFromPrompt(){
  const prompt=g('image-prompt-txt');
  if(!prompt)return alert('Prompt vazio.');
  j('loader-image').style.display='block';
  j('btn-gen-img').disabled=true;
  try{
    const res=await postJson('/meta/image/generate',{prompt,prefix:'igpost'});
    debug({step:'generate_from_prompt',response:res.data});
    if(!res.data.ok||!res.data.public_url)throw new Error(res.data.error||'sem URL de imagem');
    showPreview(res.data.public_url);
  }catch(e){alert('Erro: '+e.message);}
  finally{j('loader-image').style.display='none';j('btn-gen-img').disabled=false;}
}

// ── Tab Upload ───────────────────────────────────────────────────────────────
async function uploadFile(input){
  if(!input.files||!input.files[0])return;
  j('loader-upload').style.display='block';
  const form=new FormData();
  form.append('file',input.files[0]);
  try{
    const res=await fetch('/studio/upload-image',{method:'POST',body:form});
    const data=await res.json();
    debug({step:'upload',response:data});
    if(!data.ok||!data.public_url)throw new Error(data.error||data.detail||'upload falhou');
    showPreview(data.public_url);
  }catch(e){alert('Erro no upload: '+e.message);}
  finally{j('loader-upload').style.display='none';}
}

// ── Tab Galeria ──────────────────────────────────────────────────────────────
let _galleryLoaded=false;
async function loadGallery(force){
  if(_galleryLoaded&&!force)return;
  _galleryLoaded=true;
  const grid=j('gallery-grid');
  grid.innerHTML='<div style="color:#94a3b8;font-size:13px;grid-column:1/-1">Carregando...</div>';
  try{
    const res=await fetch('/studio/gallery');
    const data=await res.json();
    const imgs=data.images||[];
    if(!imgs.length){grid.innerHTML='<div style="color:#94a3b8;font-size:13px;grid-column:1/-1">Nenhuma imagem gerada ainda.</div>';return;}
    grid.innerHTML=imgs.map(img=>`
      <div onclick="selectFromGallery('${img.public_url}')" style="cursor:pointer;border-radius:8px;overflow:hidden;border:2px solid transparent;transition:border-color .15s"
           onmouseover="this.style.borderColor='#6366f1'" onmouseout="this.style.borderColor='transparent'">
        <img src="${img.public_url}" style="width:100%;aspect-ratio:1;object-fit:cover;display:block" loading="lazy" onerror="this.parentElement.style.display='none'"/>
        <div style="font-size:10px;color:#94a3b8;padding:3px 5px;background:#f8fafc;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${img.filename}</div>
      </div>`).join('');
  }catch(e){grid.innerHTML='<div style="color:#dc2626;font-size:13px;grid-column:1/-1">Erro ao carregar: '+e.message+'</div>';}
}
function selectFromGallery(url){
  showPreview(url);
  // Highlight selected
  j('gallery-grid').querySelectorAll('div[onclick]').forEach(el=>{
    el.style.borderColor=el.getAttribute('onclick').includes(url)?'#6366f1':'transparent';
  });
}

// ── Tab URL ──────────────────────────────────────────────────────────────────
function useUrl(){
  const url=g('url-input').trim();
  if(!url)return alert('Digite uma URL.');
  if(!url.startsWith('https://'))return alert('Use HTTPS.');
  showPreview(url);
}

// ── Validar mídia ────────────────────────────────────────────────────────────
async function validateMedia(){
  const imageUrl=g('image-url');
  if(!imageUrl)return setResult('Imagem ausente. Gere ou importe uma imagem primeiro.',false);
  setBusy(true);setResult('',true);
  try{
    const res=await fetch(imageUrl,{method:'HEAD'});
    const ct=res.headers.get('content-type')||'';
    debug({step:'validate',url:imageUrl,status:res.status,contentType:ct});
    if(!res.ok)throw new Error('URL retornou HTTP '+res.status);
    if(!ct.startsWith('image/'))throw new Error('URL não é imagem: '+ct);
    setResult('✅ Validação OK — URL acessível e é imagem ('+ct+')',true);
  }catch(e){setResult('❌ '+e.message,false);}
  finally{setBusy(false);}
}

// ── Criar container ──────────────────────────────────────────────────────────
async function createContainer(){
  const imageUrl=g('image-url');
  const caption=g('caption');
  if(!imageUrl)return setResult('Imagem ausente.',false);
  let acc;
  try{acc=selectedAccount();}catch(e){return setResult(e.message,false);}
  setBusy(true);setResult('',true);
  try{
    const payload={admin_token:ADMIN_TOKEN,ig_user_id:acc.ig_user_id,image_url:imageUrl,caption,access_token:acc.access_token};
    const r=await postJson('/meta/instagram-media/create',payload);
    debug({step:'create_container',request:payload,response:r});
    if(!r.data.ok||!r.data.result?.id)throw new Error('Falha: '+JSON.stringify(r.data.detail||r.data.error||r.data));
    lastCreationId=r.data.result.id;
    j('creation-id-txt').value=lastCreationId;
    j('creation-id-row').style.display='block';
    setResult('✅ Container criado — ID: '+lastCreationId,true);
  }catch(e){setResult('❌ '+e.message,false);}
  finally{setBusy(false);}
}

// ── Publicar ─────────────────────────────────────────────────────────────────
async function publishPost(){
  let acc;
  try{acc=selectedAccount();}catch(e){return setResult(e.message,false);}
  setBusy(true);setResult('',true);
  try{
    if(!lastCreationId){
      const imageUrl=g('image-url');
      const caption=g('caption');
      if(!imageUrl)throw new Error('Imagem ausente. Valide e crie o container primeiro.');
      const payload={admin_token:ADMIN_TOKEN,ig_user_id:acc.ig_user_id,image_url:imageUrl,caption,access_token:acc.access_token};
      const r=await postJson('/meta/instagram-media/create',payload);
      debug({step:'auto_create',request:payload,response:r});
      if(!r.data.ok||!r.data.result?.id)throw new Error('Falha ao criar container: '+JSON.stringify(r.data.detail||r.data.error));
      lastCreationId=r.data.result.id;
      j('creation-id-txt').value=lastCreationId;
      j('creation-id-row').style.display='block';
    }
    const pubPayload={admin_token:ADMIN_TOKEN,ig_user_id:acc.ig_user_id,creation_id:lastCreationId,access_token:acc.access_token};
    const pubRes=await postJson('/meta/instagram-media/publish',pubPayload);
    debug({step:'publish',request:pubPayload,response:pubRes});
    if(pubRes.data.ok&&pubRes.data.result?.id){
      setResult('🎉 Publicado com sucesso! Post ID: '+pubRes.data.result.id,true);
      lastCreationId='';
    }else{
      throw new Error('Falha na publicação: '+JSON.stringify(pubRes.data.detail||pubRes.data.error||pubRes.data));
    }
  }catch(e){setResult('❌ '+e.message,false);}
  finally{setBusy(false);}
}
</script>
  </main>
</div>
</body>
</html>'''
    return HTMLResponse(html)
