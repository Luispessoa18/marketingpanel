#!/usr/bin/env python3
"""Run full AI analysis and output structured JSON to stdout."""
import sys, json, os
from pathlib import Path

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))

try:
    from dotenv import load_dotenv
    load_dotenv(BASE / '.env')
except Exception:
    pass

INSTAGRAM_SESSION_EXPIRED = {
    'ok': False,
    'error': 'instagram_session_expired',
    'detail': 'Sessão inválida ou expirada. Rode: python3 instascrapper/main.py login <usuario> <senha>',
}


def _panel_metrics_from_analysis(analysis: dict) -> dict:
    header = analysis.get('header', {}) if isinstance(analysis, dict) else {}
    stats = header.get('stats', {}) if isinstance(header, dict) else {}
    diagnosis = analysis.get('diagnosis', {}) if isinstance(analysis, dict) else {}
    strategy = analysis.get('strategy', {}) if isinstance(analysis, dict) else {}
    icp = analysis.get('icp', {}) if isinstance(analysis, dict) else {}
    return {
        'followers': stats.get('followers', ''),
        'posts': stats.get('posts', ''),
        'engagement_rate': stats.get('engagement_rate', ''),
        'positioning_verdict': diagnosis.get('positioning_verdict', ''),
        'central_problem': diagnosis.get('central_problem', ''),
        'new_positioning': strategy.get('new_positioning', ''),
        'primary_icp': icp.get('primary_title', ''),
    }

target = sys.argv[1] if len(sys.argv) > 1 else ''
as_user = sys.argv[3] if (len(sys.argv) > 3 and sys.argv[2] == '--as') else ''
force = '--force' in sys.argv  # ignore cache

if not target:
    print(json.dumps({'ok': False, 'error': 'missing_username'}), flush=True)
    sys.exit(1)

try:
    from database import get_cache, save_cache
    from instagram import InstagramClient
    from ai_analyze import analyze_zip_json_rich, analyze_profile_json_rich

    # Check cache first (unless --force)
    if not force:
        cached = get_cache(target.lower())
        if cached and cached.get('report_data'):
            rd = cached['report_data']
            analysis = json.loads(rd) if isinstance(rd, str) else rd
            pj = cached.get('profile_json')
            profile = json.loads(pj) if (pj and isinstance(pj, str)) else {}
            _ak = len([k for k in (analysis or {}) if not str(k).startswith('_')])
            print(
                json.dumps(
                    {
                        'ok': True,
                        'cached': True,
                        'username': target,
                        'profile': profile,
                        'analysis': analysis,
                        'provider': os.environ.get('AI_PROVIDER', 'gemini'),
                        'model': os.environ.get('AI_MODEL', ''),
                        'usage': {},
                        'cost_usd': 0.0,
                        'ai_ran': True,
                        'ai_skip_reason': None,
                        'zip_ok': True,
                        'ai_key_configured': True,
                        'profile_error': (profile or {}).get('error') if isinstance(profile, dict) else None,
                        'analysis_key_count': _ak,
                        'source': 'disk_cache',
                        'panel': {
                            'provider': os.environ.get('AI_PROVIDER', 'gemini'),
                            'model': os.environ.get('AI_MODEL', ''),
                            'usage': {},
                            'cost_usd': 0.0,
                            'metrics': _panel_metrics_from_analysis(analysis),
                        },
                    }
                ),
                flush=True,
            )
            sys.exit(0)

    # Scrape profile
    with InstagramClient(headless=True) as client:
        if as_user:
            if not client.login(as_user, '', save=False):
                print(json.dumps(INSTAGRAM_SESSION_EXPIRED), flush=True)
                sys.exit(1)
        profile = client.get_profile(target, out_dir=str(BASE / 'debug'))
        profile_telemetry = client.get_last_telemetry()
        zip_data = client.scrape_profile(target, out_dir=str(BASE / 'debug'))
        scrape_telemetry = client.get_last_telemetry()

    # Save profile to cache
    save_cache(target.lower(), profile_json=profile)

    def _ai_key_configured() -> bool:
        prov = (os.environ.get('AI_PROVIDER') or 'gemini').lower().strip()
        if prov == 'openai':
            return bool((os.environ.get('OPENAI_API_KEY') or '').strip())
        return bool(
            (os.environ.get('GOOGLE_API_KEY') or '').strip()
            or (os.environ.get('ANTHROPIC_API_KEY') or '').strip()
            or (os.environ.get('OPENAI_API_KEY') or '').strip()
        )

    def _analysis_non_empty(a) -> bool:
        if not isinstance(a, dict):
            return False
        return any(not str(k).startswith('_') for k in a)

    def _classify_stage(zip_ok: bool, has_key: bool, profile_error: str, ai_ran: bool, analysis: dict, warning: str = '', skip_reason: str = '') -> tuple[str, str]:
        if profile_error:
            return 'profile_fetch', 'profile_fetch_failed'
        if not zip_ok and ai_ran and _analysis_non_empty(analysis):
            return 'ai_fallback_html', 'success'
        if not zip_ok:
            return 'scrape_zip', 'scrape_failed'
        if not has_key:
            return 'ai_config', 'ai_key_missing'
        if warning and ('json' in warning.lower() or 'expecting value' in warning.lower()):
            return 'ai_parse', 'ai_json_parse_failed'
        if skip_reason and ('json' in skip_reason.lower() or 'vazia' in skip_reason.lower() or 'invalido' in skip_reason.lower()):
            return 'ai_parse', 'ai_json_parse_failed'
        if not ai_ran:
            return 'ai_provider', 'ai_provider_failed'
        if not _analysis_non_empty(analysis):
            return 'ai_output', 'analysis_empty'
        return 'done', 'success'

    # Run AI analysis on zip data
    provider = os.environ.get('AI_PROVIDER', 'gemini')
    model = os.environ.get('AI_MODEL', '')
    has_key = _ai_key_configured()
    pe = profile.get('error') if isinstance(profile, dict) else None
    zip_ok = bool(zip_data)

    ai_ran = False
    ai_skip_reason = None
    if not zip_ok:
        ai_skip_reason = 'sem_zip_ou_falha_ao_gerar_zip_do_perfil'
    elif not has_key:
        ai_skip_reason = 'sem_chave_de_api_no_ambiente_gestor_instascrapper_recebe_GOOGLE_OU_OPENAI'
    elif pe:
        ai_skip_reason = f"perfil_com_erro_{pe}"
    if zip_ok and has_key and not pe:
        try:
            rich = analyze_zip_json_rich(
                zip_data,
                "Faça uma auditoria completa deste perfil do Instagram com foco em posicionamento, conteúdo, ICP, funil e recomendações práticas.",
            )
        except Exception as ai_exc:
            ai_skip_reason = f'falha_na_ia: {str(ai_exc)[:300]}'
            print(f'[analyze_json] Erro na IA: {ai_exc}', file=sys.stderr)
            rich = {'provider': provider, 'model': model, 'usage': {}, 'cost_usd': 0.0, 'panel_metrics': {}}
        analysis = rich.get('analysis', {}) if isinstance(rich.get('analysis'), dict) else {}
        save_cache(target.lower(), report_data=analysis, profile_json=profile)
        ai_ran = bool(rich) and _analysis_non_empty(analysis)
        if not ai_ran and zip_ok and has_key:
            ai_skip_reason = ai_skip_reason or 'ia_executou_mas_resposta_vazia_ou_json_invalido'
    elif has_key and not pe and isinstance(profile, dict) and profile:
        html_text = ''
        telemetry_html_path = ''
        for source in (profile_telemetry, scrape_telemetry, (profile.get('_telemetry') if isinstance(profile, dict) else {})):
            if isinstance(source, dict) and source.get('html_path'):
                telemetry_html_path = source.get('html_path') or ''
                break
        if telemetry_html_path:
            try:
                html_text = Path(telemetry_html_path).read_text(encoding='utf-8')
            except Exception:
                html_text = ''
        rich = analyze_profile_json_rich(
            profile,
            "Faça uma auditoria completa deste perfil do Instagram com foco em posicionamento, conteúdo, ICP, funil e recomendações práticas. Se o scrape visual completo falhou, use o profile.json e o HTML da página para inferir a análise com a melhor precisão possível.",
            html_text=html_text,
        )
        analysis = rich.get('analysis', {}) if isinstance(rich.get('analysis'), dict) else {}
        save_cache(target.lower(), report_data=analysis, profile_json=profile)
        ai_ran = bool(rich) and _analysis_non_empty(analysis)
        if ai_ran:
            ai_skip_reason = None
            zip_ok = False
        else:
            ai_skip_reason = ai_skip_reason or 'ia_executou_mas_resposta_vazia_ou_json_invalido_mesmo_sem_zip'
    else:
        analysis = {}
        rich = {'provider': provider, 'model': model, 'usage': {}, 'cost_usd': 0.0, 'panel_metrics': {}}
    stage, failure_category = _classify_stage(zip_ok, has_key, pe, ai_ran, analysis, '', ai_skip_reason or '')

    print(
        json.dumps(
            {
                'ok': True,
                'cached': False,
                'username': target,
                'profile': profile,
                'analysis': analysis,
                'provider': rich.get('provider', provider),
                'model': rich.get('model', model),
                'usage': rich.get('usage', {}),
                'cost_usd': rich.get('cost_usd', 0.0),
                'ai_ran': ai_ran,
                'ai_skip_reason': ai_skip_reason,
                'zip_ok': zip_ok,
                'ai_key_configured': has_key,
                'profile_error': pe,
                'profile_http_status': (profile or {}).get('http_status') if isinstance(profile, dict) else None,
                'profile_hint': (profile or {}).get('hint') if isinstance(profile, dict) else None,
                'analysis_key_count': len([k for k in (analysis or {}) if not str(k).startswith('_')]),
                'stage': stage,
                'failure_category': failure_category,
                'telemetry': {
                    'profile': profile_telemetry,
                    'scrape': scrape_telemetry,
                },
                'panel': {
                    'provider': rich.get('provider', provider),
                    'model': rich.get('model', model),
                    'usage': rich.get('usage', {}),
                    'cost_usd': rich.get('cost_usd', 0.0),
                    'metrics': rich.get('panel_metrics', {}),
                },
            }
        ),
        flush=True,
    )

except Exception as e:
    # Fallback: at least return profile data without AI
    try:
        from instagram import InstagramClient
        telemetry = {}
        with InstagramClient(headless=True) as client:
            if as_user:
                if not client.login(as_user, '', save=False):
                    print(json.dumps(INSTAGRAM_SESSION_EXPIRED), flush=True)
                    sys.exit(1)
            profile = client.get_profile(target, out_dir=str(BASE / 'debug'))
            telemetry = client.get_last_telemetry()
        print(
            json.dumps(
                {
                    'ok': True,
                    'cached': False,
                    'username': target,
                    'profile': profile,
                    'analysis': {},
                    'warning': str(e),
                    'ai_ran': False,
                    'ai_skip_reason': f'excecao_antes_da_ia: {str(e)[:200]}',
                    'zip_ok': False,
                    'ai_key_configured': bool(
                        (os.environ.get('GOOGLE_API_KEY') or '').strip()
                        or (os.environ.get('OPENAI_API_KEY') or '').strip()
                    ),
                    'profile_error': (profile or {}).get('error') if isinstance(profile, dict) else None,
                    'analysis_key_count': 0,
                    'stage': 'bootstrap',
                    'failure_category': 'ai_provider_failed' if 'openai' in str(e).lower() or 'anthropic' in str(e).lower() or 'gemini' in str(e).lower() else 'scrape_failed',
                    'telemetry': {
                        'profile': telemetry,
                    },
                }
            ),
            flush=True,
        )
    except Exception as e2:
        print(json.dumps({'ok': False, 'error': str(e), 'detail': str(e2)}), flush=True)
        sys.exit(1)
