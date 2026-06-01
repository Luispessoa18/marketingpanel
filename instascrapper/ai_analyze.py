"""
Análise de ZIPs de perfis do Instagram via IA.

Configura via variáveis de ambiente:
  AI_PROVIDER   = claude | gemini | openai | openrouter  (padrão: claude)
  AI_MODEL      = nome do modelo (padrão varia por provider)
  ANTHROPIC_API_KEY
  GOOGLE_API_KEY
  OPENAI_API_KEY
  OPENROUTER_API_KEY
"""

import base64
import json
import os
import re
import urllib.error
import urllib.request
import zipfile

AI_PRICE_TABLE = {
    "gemini-2.5-pro": {"input_per_million": 3.50, "output_per_million": 10.50},
    "gemini-2.5-flash": {"input_per_million": 0.30, "output_per_million": 2.50},
    "gemini-2.0-flash": {"input_per_million": 0.10, "output_per_million": 0.40},
    "gemini-2.0-flash-lite": {"input_per_million": 0.10, "output_per_million": 0.40},
    "gemini-1.5-pro": {"input_per_million": 3.50, "output_per_million": 10.50},
    "gemini-1.5-flash": {"input_per_million": 0.35, "output_per_million": 1.05},
    "gemini-1.5-flash-8b": {"input_per_million": 0.04, "output_per_million": 0.15},
    "gpt-4o": {"input_per_million": 2.50, "output_per_million": 10.00},
    "gpt-4o-mini": {"input_per_million": 0.15, "output_per_million": 0.60},
}


# ── JSON schema para relatório estruturado ────────────────────────────────────

REPORT_SCHEMA_PROMPT = """\
Você é um especialista em estratégia de Instagram e marketing digital.
Analise o perfil fornecido e retorne APENAS um JSON válido, sem markdown, sem ```json, sem texto adicional.

O JSON deve seguir EXATAMENTE este schema (adapte todos os dados ao perfil analisado):

{
  "header": {
    "username": "nome_usuario",
    "full_name": "Nome Completo",
    "subtitle": "Cargo/Empresa · Mês Ano",
    "stats": {
      "posts": "número",
      "followers": "ex: 13.5K",
      "following": "número",
      "engagement_rate": "ex: ~0.6%"
    }
  },
  "diagnosis": {
    "current_positioning": "Análise do posicionamento percebido nos primeiros 5 segundos.",
    "positioning_verdict": "Veredicto objetivo em 1-2 frases.",
    "content_pillars": [
      {"label": "Nome do Pilar", "pct": 35, "color_var": "purple"}
    ],
    "central_problem": "Problema central de conteúdo do perfil.",
    "formats": [
      {"format": "Nome", "presence": "~X%", "note": "Observação"}
    ],
    "tone": "Análise do tom de voz atual.",
    "visual": "Análise da identidade visual.",
    "audience_current": "Quem está sendo atraído hoje.",
    "audience_target": "Quem deveria ser o público ideal.",
    "audience_gap": "Gap entre público atual e ideal.",
    "critical_gaps": [
      {"title": "Título do Gap", "description": "Descrição detalhada."}
    ]
  },
  "icp": {
    "primary_title": "Nome do Perfil Primário",
    "primary_demographics": "Descrição demográfica.",
    "primary_psychographics": "Descrição psicográfica.",
    "secondary_title": "Nome do Perfil Secundário",
    "secondary_demographics": "Descrição demográfica.",
    "secondary_psychographics": "Descrição psicográfica.",
    "pains": ["Dor 1", "Dor 2", "Dor 3"],
    "desires": ["Desejo 1", "Desejo 2", "Desejo 3"],
    "objections": ["Objeção 1 → como tratar", "Objeção 2", "Objeção 3", "Objeção 4"],
    "consumption_channels": "Onde esse público consome conteúdo."
  },
  "strategy": {
    "new_positioning": "Novo posicionamento proposto com destaque para a frase principal.",
    "bio_versions": [
      {"title": "Versão 1 — Nome", "content": "Texto completo da bio com emojis e quebras de linha usando \\n"}
    ],
    "content_pillars": [
      {"name": "Nome do Pilar", "tag": "TAG", "pct": "30%", "objective": "Objetivo", "examples": "Ex 1, Ex 2, Ex 3"}
    ],
    "format_mix": [
      {"format": "Nome do formato", "qty": "número ou faixa", "when": "Quando publicar"}
    ],
    "weekly_calendar": [
      {
        "day_label": "Segunda — Reel",
        "title": "Título do conteúdo",
        "meta": "Formato: X | Pilar: Y",
        "hook": "Gancho: texto de abertura",
        "cta": "CTA: chamada para ação"
      }
    ],
    "viral_hooks": [
      "\"Texto do hook 1\" — Gatilho: tipo",
      "\"Texto do hook 2\" — Gatilho: tipo",
      "\"Texto do hook 3\" — Gatilho: tipo",
      "\"Texto do hook 4\" — Gatilho: tipo",
      "\"Texto do hook 5\" — Gatilho: tipo"
    ],
    "funnel_top": "Estratégia de topo (descoberta).",
    "funnel_middle": "Estratégia de meio (nutrição).",
    "funnel_bottom": "Estratégia de fundo (conversão).",
    "funnel_paths": [
      {"label": "Caminho A", "text": "Descrição do caminho"},
      {"label": "Caminho B", "text": "Descrição do caminho"},
      {"label": "Caminho C", "text": "Descrição do caminho"}
    ],
    "funnel_post_conversion": "Estratégia pós-conversão.",
    "kpis": [
      {"kpi": "Nome do KPI", "target": "Meta", "reason": "Por que esse KPI importa"}
    ]
  },
  "posts_analysis": {
    "overview": "Análise geral dos últimos posts: padrão visual, coerência de identidade e linha editorial em 2-3 frases.",
    "consistency_score": 7,
    "consistency_label": "ex: Moderada",
    "positives": [
      "Ponto positivo 1 observado nos posts",
      "Ponto positivo 2",
      "Ponto positivo 3"
    ],
    "improvements": [
      "Ponto a melhorar 1",
      "Ponto a melhorar 2",
      "Ponto a melhorar 3"
    ],
    "pattern_verdict": "Veredicto direto: o perfil segue um padrão claro OU está fragmentado/sem identidade definida. Explique em 1-2 frases.",
    "caption_quality": "Análise da qualidade das legendas: são estratégicas? Têm CTA? Contam história? Engajam?",
    "format_variety": "Quais formatos aparecem nos posts analisados e se há equilíbrio.",
    "posts": [
      {
        "ref": "post_01.jpg ou pinned_01.jpg (use o filename exato)",
        "type": "Reel | Carrossel | Foto",
        "caption_summary": "Resumo de até 30 palavras da legenda (ou 'sem legenda')",
        "what_works": "O que funciona neste post",
        "what_to_improve": "O que poderia ser melhor",
        "coherence": "Alto | Médio | Baixo — se está alinhado à identidade do perfil"
      }
    ]
  },
  "quick_wins": [
    {"title": "Título da ação", "description": "Descrição com tempo estimado."}
  ],
  "generated_at": "Mês Ano",
  "next_steps": "Próximos passos após os quick wins."
}

REGRAS OBRIGATÓRIAS:
- Retorne APENAS o JSON, nada mais
- color_var deve ser um de: purple, blue, accent, cyan, green, red
- content_pillars[].pct (diagnosis) é número inteiro sem %
- weekly_calendar: 7 entradas (segunda a domingo)
- viral_hooks: exatamente 5 itens
- quick_wins: exatamente 5 itens
- critical_gaps: entre 4 e 6 itens
- bio_versions: 3 versões
- strategy.content_pillars: 5 pilares
- kpis: 3 itens
- posts_analysis.positives: 3 a 5 itens
- posts_analysis.improvements: 3 a 5 itens
- posts_analysis.consistency_score: inteiro de 1 a 10
- posts_analysis.posts: 1 entrada por post analisado (use os filenames exatos das imagens enviadas)
"""


# ── helpers ───────────────────────────────────────────────────────────────────

def _extract_json(raw: str) -> dict:
    """
    Extrai o primeiro objeto JSON válido de uma string de resposta da IA.
    Lida com:
      - Markdown code fences (```json ... ```)
      - Texto antes/depois do JSON
      - Múltiplos objetos separados por texto extra
    """
    raw = raw.strip()

    # Remove code fences
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```.*$", "", raw, flags=re.DOTALL)
        raw = raw.strip()

    # Tenta parse direto (caso ideal)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Encontra o primeiro '{' e usa o decoder para parar no fim do objeto
    start = raw.find("{")
    if start == -1:
        raise RuntimeError(f"Nenhum objeto JSON encontrado na resposta.\nResposta:\n{raw[:500]}")

    decoder = json.JSONDecoder()
    try:
        obj, _ = decoder.raw_decode(raw, start)
        return obj
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"A IA não retornou JSON válido: {e}\n"
            f"Primeiros 500 chars da resposta:\n{raw[:500]}"
        )


def _read_zip(zip_path: str) -> tuple[str, list[tuple[str, str, str]]]:
    """
    Lê o ZIP e retorna (profile_json_str, [(filename, base64_data, mime_type), ...]).
    Ordem: avatar.jpg primeiro, depois posts/{pinned/post}_XX.jpg em ordem alfabética.
    screenshot.png é excluído (não agrega para análise de conteúdo).
    """
    profile_json = ""
    images: list[tuple[str, str, str]] = []
    avatar: tuple | None = None

    with zipfile.ZipFile(zip_path) as zf:
        names = sorted(zf.namelist())
        for name in names:
            basename = os.path.basename(name)
            if basename == "profile.json":
                profile_json = zf.read(name).decode("utf-8")
            elif basename == "screenshot.png":
                continue  # ignora screenshot
            elif basename.endswith((".jpg", ".jpeg", ".png", ".webp")):
                raw = zf.read(name)
                b64 = base64.standard_b64encode(raw).decode()
                mime = "image/png" if basename.endswith(".png") else "image/jpeg"
                if basename == "avatar.jpg":
                    avatar = (basename, b64, mime)
                else:
                    images.append((basename, b64, mime))

    ordered = ([avatar] if avatar else []) + images
    return profile_json, ordered


def _build_posts_context(profile_data: dict) -> str:
    """Constrói bloco de texto com legendas dos posts selecionados."""
    posts = profile_data.get("selected_posts") or profile_data.get("recent_posts") or []
    if not posts:
        return ""
    lines = ["\n--- Últimos posts (imagem + legenda) ---"]
    for i, p in enumerate(posts[:6], 1):
        fname = p.get("filename") or f"post_{i:02d}.jpg"
        pinned = " [FIXADO]" if p.get("is_pinned") else ""
        likes = p.get("likes")
        comments = p.get("comments")
        engagement = ""
        if likes is not None or comments is not None:
            parts = []
            if likes is not None:
                parts.append(f"{likes} curtidas")
            if comments is not None:
                parts.append(f"{comments} comentários")
            engagement = f" | {', '.join(parts)}"
        caption = (p.get("caption") or "").strip()
        caption_str = f'"{caption[:600]}"' if caption else "(sem legenda)"
        lines.append(f"\n[Post {i}{pinned} — {fname}{engagement}]\nLegenda: {caption_str}")
    return "\n".join(lines)


def _build_text_prompt(user_prompt: str, profile_json: str) -> str:
    try:
        data = json.loads(profile_json)
        summary = (
            f"@{data.get('username')} | {data.get('full_name')} | "
            f"Seguidores: {data.get('followers')} | Posts: {data.get('posts_count')} | "
            f"Verificado: {data.get('verified')} | Bio: {data.get('bio')}"
        )
        posts_ctx = _build_posts_context(data)
    except Exception:
        summary = profile_json
        posts_ctx = ""

    return (
        f"{user_prompt}\n\n"
        f"--- Dados do perfil ---\n{summary}"
        f"{posts_ctx}\n\n"
        "As imagens a seguir são: avatar do perfil e os posts acima (fixados primeiro, na mesma ordem)."
    )


def _build_text_prompt_with_html(user_prompt: str, profile_json: str, html_text: str = "") -> str:
    base = _build_text_prompt(user_prompt, profile_json)
    cleaned_html = " ".join(str(html_text or "").split())
    if cleaned_html:
        cleaned_html = cleaned_html[:12000]
        base += f"\n\n--- HTML bruto da página do perfil (recorte) ---\n{cleaned_html}"
    return base


def _estimate_tokens(text: str) -> int:
    text = str(text or "")
    if not text:
        return 0
    return max(1, int(len(text) / 4))


def _calculate_cost(model: str, usage: dict | None = None) -> float:
    usage = usage or {}
    price = AI_PRICE_TABLE.get(model, {})
    prompt_tokens = float(usage.get("input_tokens") or 0)
    completion_tokens = float(usage.get("output_tokens") or 0)
    return round(
        (prompt_tokens / 1_000_000.0) * float(price.get("input_per_million") or 0.0) +
        (completion_tokens / 1_000_000.0) * float(price.get("output_per_million") or 0.0),
        6,
    )


# ── providers ─────────────────────────────────────────────────────────────────

def _analyze_claude(prompt: str, images: list, model: str, system: str | None = None) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    content: list = []
    for fname, b64, mime in images:
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": mime, "data": b64},
        })
    content.append({"type": "text", "text": prompt})

    kwargs: dict = {
        "model": model,
        "max_tokens": 8192,
        "messages": [{"role": "user", "content": content}],
    }
    if system:
        kwargs["system"] = system

    resp = client.messages.create(**kwargs)
    return resp.content[0].text


def _analyze_gemini(prompt: str, images: list, model: str, system: str | None = None) -> str:
    import google.generativeai as genai

    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

    parts: list = []
    for fname, b64, mime in images:
        parts.append({"inline_data": {"mime_type": mime, "data": b64}})
    # Para Gemini, o system prompt é prefixado ao user prompt
    full = f"{system}\n\n{prompt}" if system else prompt
    parts.append(full)

    m = genai.GenerativeModel(model)
    resp = m.generate_content(parts)
    return resp.text


def _analyze_gemini_rich(prompt: str, images: list, model: str, system: str | None = None) -> dict:
    import google.generativeai as genai

    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

    parts: list = []
    for fname, b64, mime in images:
        parts.append({"inline_data": {"mime_type": mime, "data": b64}})
    full = f"{system}\n\n{prompt}" if system else prompt
    parts.append(full)

    m = genai.GenerativeModel(model)
    resp = m.generate_content(parts)
    usage_meta = getattr(resp, "usage_metadata", None)
    usage = {
        "input_tokens": int(getattr(usage_meta, "prompt_token_count", 0) or 0),
        "output_tokens": int(getattr(usage_meta, "candidates_token_count", 0) or 0),
    }
    usage["total_tokens"] = int(getattr(usage_meta, "total_token_count", usage["input_tokens"] + usage["output_tokens"]) or (usage["input_tokens"] + usage["output_tokens"]))
    text = getattr(resp, "text", "") or ""
    if not usage["total_tokens"]:
        usage = {
            "input_tokens": _estimate_tokens(prompt),
            "output_tokens": _estimate_tokens(text),
            "total_tokens": _estimate_tokens(prompt) + _estimate_tokens(text),
        }
    return {"text": text, "usage": usage, "provider": "gemini", "model": model, "cost_usd": _calculate_cost(model, usage)}


def _openai_http_call(api_base: str, api_key: str, body: bytes, retries: int = 4) -> dict:
    """Faz POST para /chat/completions com retry em rate-limit e leitura de body em caso de erro."""
    import urllib.error as _ue
    last_exc = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                f"{api_base}/chat/completions",
                data=body,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except _ue.HTTPError as e:
            last_exc = e
            # Lê body do erro para diagnóstico
            try:
                err_body = json.loads(e.read().decode("utf-8"))
                err_msg = (err_body.get("error") or {}).get("message") or str(err_body)
            except Exception:
                err_msg = str(e)
            print(f"[openai] HTTP {e.code}: {err_msg[:300]}", flush=True)
            if _is_rate_limit(e) and attempt < retries - 1:
                import time
                time.sleep(min(10.0, 1.5 * (2 ** attempt)))
                continue
            raise RuntimeError(f"OpenAI HTTP {e.code}: {err_msg[:300]}") from e
        except Exception as e:
            last_exc = e
            if _is_rate_limit(e) and attempt < retries - 1:
                import time
                time.sleep(min(10.0, 1.5 * (2 ** attempt)))
                continue
            raise
    raise RuntimeError(f"OpenAI chat falhou: {last_exc}")


def _openai_model_uses_responses_api(model: str) -> bool:
    model = str(model or "").strip().lower()
    return model.startswith("gpt-5") or model.startswith("o")


def _build_openai_messages(prompt: str, images: list, system: str | None, json_mode: bool, model: str) -> dict:
    messages: list = []
    if system:
        messages.append({"role": "system", "content": system})
    content: list = [{"type": "text", "text": prompt}]
    for fname, b64, mime in images:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{b64}"},
        })
    messages.append({"role": "user", "content": content})
    kwargs: dict = {"model": model, "messages": messages}
    if _openai_model_uses_responses_api(model):
        kwargs["max_completion_tokens"] = 8192
    else:
        kwargs["max_tokens"] = 8192
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    return kwargs


def _build_openai_responses_payload(prompt: str, images: list, system: str | None, json_mode: bool, model: str) -> dict:
    payload: dict = {
        "model": model,
        "input": [],
        "max_output_tokens": 8192,
    }
    if system:
        payload["input"].append({
            "role": "system",
            "content": [{"type": "input_text", "text": system}],
        })
    user_content: list = [{"type": "input_text", "text": prompt}]
    for _fname, b64, mime in images:
        user_content.append({
            "type": "input_image",
            "image_url": f"data:{mime};base64,{b64}",
        })
    payload["input"].append({
        "role": "user",
        "content": user_content,
    })
    if json_mode:
        payload["text"] = {"format": {"type": "json_object"}}
    return payload


def _extract_openai_responses_text(data: dict) -> str:
    text = str(data.get("output_text") or "").strip()
    if text:
        return text
    parts: list[str] = []
    for item in data.get("output") or []:
        for content in item.get("content") or []:
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                parts.append(str(content.get("text")))
    return "\n".join(parts).strip()


def _extract_openai_usage(data: dict, responses_api: bool = False) -> dict:
    raw_usage = data.get("usage") or {}
    if responses_api:
        input_tokens = int(raw_usage.get("input_tokens") or 0)
        output_tokens = int(raw_usage.get("output_tokens") or 0)
    else:
        input_tokens = int(raw_usage.get("prompt_tokens") or raw_usage.get("input_tokens") or 0)
        output_tokens = int(raw_usage.get("completion_tokens") or raw_usage.get("output_tokens") or 0)
    total_tokens = int(raw_usage.get("total_tokens") or (input_tokens + output_tokens))
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def _openai_responses_http_call(api_base: str, api_key: str, body: bytes, retries: int = 4) -> dict:
    import urllib.error as _ue
    last_exc = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                f"{api_base}/responses",
                data=body,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except _ue.HTTPError as e:
            last_exc = e
            try:
                err_body = json.loads(e.read().decode("utf-8"))
                err_msg = (err_body.get("error") or {}).get("message") or str(err_body)
            except Exception:
                err_msg = str(e)
            print(f"[openai] HTTP {e.code}: {err_msg[:300]}", flush=True)
            if _is_rate_limit(e) and attempt < retries - 1:
                import time
                time.sleep(min(10.0, 1.5 * (2 ** attempt)))
                continue
            raise RuntimeError(f"OpenAI HTTP {e.code}: {err_msg[:300]}") from e
        except Exception as e:
            last_exc = e
            if _is_rate_limit(e) and attempt < retries - 1:
                import time
                time.sleep(min(10.0, 1.5 * (2 ** attempt)))
                continue
            raise
    raise RuntimeError(f"OpenAI responses falhou: {last_exc}")


def _analyze_openai_compat(
    prompt: str,
    images: list,
    model: str,
    api_key: str,
    base_url: str | None = None,
    system: str | None = None,
    json_mode: bool = False,
) -> str:
    api_base = (base_url or "https://api.openai.com/v1").rstrip("/")
    if _openai_model_uses_responses_api(model):
        kwargs = _build_openai_responses_payload(prompt, images, system, json_mode, model)
        data = _openai_responses_http_call(api_base, api_key, json.dumps(kwargs).encode("utf-8"))
        return _extract_openai_responses_text(data)
    kwargs = _build_openai_messages(prompt, images, system, json_mode, model)
    data = _openai_http_call(api_base, api_key, json.dumps(kwargs).encode("utf-8"))
    return (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "")


def _analyze_openai_compat_rich(
    prompt: str,
    images: list,
    model: str,
    api_key: str,
    base_url: str | None = None,
    system: str | None = None,
    json_mode: bool = False,
) -> dict:
    api_base = (base_url or "https://api.openai.com/v1").rstrip("/")
    responses_api = _openai_model_uses_responses_api(model)
    if responses_api:
        kwargs = _build_openai_responses_payload(prompt, images, system, json_mode, model)
        data = _openai_responses_http_call(api_base, api_key, json.dumps(kwargs).encode("utf-8"))
        text = _extract_openai_responses_text(data)
    else:
        kwargs = _build_openai_messages(prompt, images, system, json_mode, model)
        data = _openai_http_call(api_base, api_key, json.dumps(kwargs).encode("utf-8"))
        text = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "")
    usage = _extract_openai_usage(data, responses_api=responses_api)
    if not usage["total_tokens"]:
        usage = {
            "input_tokens": _estimate_tokens(prompt),
            "output_tokens": _estimate_tokens(text),
            "total_tokens": _estimate_tokens(prompt) + _estimate_tokens(text),
        }
    return {"text": text, "usage": usage, "provider": "openai", "model": model, "cost_usd": _calculate_cost(model, usage)}


# ── public API ────────────────────────────────────────────────────────────────

DEFAULT_MODELS = {
    "claude": "claude-sonnet-4-6",
    "gemini": "gemini-2.0-flash",
    "openai": "gpt-4o",
    "openrouter": "openai/gpt-4o",
}

# Fallback chain para OpenRouter /free — tentados em ordem
# Nota: modelos :free exigem que a conta tenha crédito adicionado em openrouter.ai/credits
OPENROUTER_FREE_FALLBACKS = [
    "meta-llama/llama-4-scout:free",          # multimodal (visão)
    "meta-llama/llama-4-maverick:free",        # multimodal (visão)
    "qwen/qwen2.5-vl-72b-instruct:free",       # multimodal (visão)
    "google/gemini-2.0-flash-exp:free",        # multimodal (visão)
    "google/gemma-3-27b-it:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "qwen/qwen3-235b-a22b:free",
    "qwen/qwen3-30b-a3b:free",
    "mistralai/mistral-nemo:free",
    "deepseek/deepseek-chat:free",
]

# Ordem de preferência para Gemini — será filtrada pelos modelos disponíveis na chave
GEMINI_PREFERENCE = [
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
]


def _is_rate_limit(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(k in msg for k in ("429", "quota", "rate limit", "resource_exhausted",
                                  "too many requests", "ratelimiterror"))


def _is_retryable_gemini(exc: Exception) -> bool:
    """Erros que justificam tentar o próximo modelo."""
    msg = str(exc).lower()
    return _is_rate_limit(exc) or any(k in msg for k in (
        "404", "not found", "not supported", "model not found",
        "permission", "disabled", "unavailable", "overloaded",
    ))


def _get_gemini_models() -> list[str]:
    """
    Consulta a API e retorna modelos disponíveis para a chave,
    ordenados pela preferência em GEMINI_PREFERENCE.
    """
    import google.generativeai as genai
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

    try:
        available = {
            m.name.replace("models/", "")
            for m in genai.list_models()
            if "generateContent" in m.supported_generation_methods
        }
    except Exception as e:
        print(f"[ai] Aviso: não foi possível listar modelos Gemini ({e}). Usando lista padrão.")
        return GEMINI_PREFERENCE

    ordered = [m for m in GEMINI_PREFERENCE if m in available]
    extras  = sorted(available - set(GEMINI_PREFERENCE))  # modelos não listados acima

    if ordered:
        print(f"[ai] Modelos Gemini disponíveis para esta chave: {ordered + extras}")
    else:
        print(f"[ai] Nenhum modelo preferido disponível. Disponíveis: {sorted(available)}")
        ordered = extras  # tenta o que tiver

    return ordered or GEMINI_PREFERENCE  # fallback para a lista estática se a API retornar vazio


def _dispatch(
    prompt: str,
    images: list,
    provider: str,
    model: str,
    system: str | None = None,
    json_mode: bool = False,
) -> str:
    """Chama o provider com fallback automático em caso de erro de quota/rate-limit."""

    if provider == "gemini":
        # Consulta quais modelos a chave tem acesso, depois ordena por preferência
        available = _get_gemini_models()
        # Modelo explícito do usuário vai na frente se não estiver na lista
        chain = ([model] if model not in available else []) + available
        last_exc: Exception | None = None
        for m in chain:
            try:
                print(f"[ai] Gemini → {m}")
                return _analyze_gemini(prompt, images, m, system=system)
            except Exception as e:
                if _is_retryable_gemini(e):
                    print(f"[ai] Falhou ({type(e).__name__}: {str(e)[:80]}), tentando próximo...")
                    last_exc = e
                    continue
                raise
        raise RuntimeError(f"Todos os modelos Gemini falharam. Último erro: {last_exc}")

    elif provider == "openrouter":
        # Se o modelo for /free (ou começar com openrouter/free), usa a cadeia de fallback
        is_free = model in ("openrouter/free", "") or model.endswith(":free")
        chain = OPENROUTER_FREE_FALLBACKS if is_free else [model]
        last_exc = None
        for m in chain:
            try:
                print(f"[ai] OpenRouter → {m}")
                return _analyze_openai_compat(
                    prompt, images, m,
                    api_key=os.environ["OPENROUTER_API_KEY"],
                    base_url="https://openrouter.ai/api/v1",
                    system=system,
                )
            except Exception as e:
                msg = str(e).lower()
                if _is_rate_limit(e) or any(k in msg for k in ("404", "not found", "no endpoints", "unavailable", "provider returned error")):
                    print(f"[ai] Falhou ({type(e).__name__}), tentando próximo...")
                    last_exc = e
                    continue
                raise
        raise RuntimeError(f"Todos os modelos OpenRouter falharam. Último erro: {last_exc}")

    elif provider == "claude":
        return _analyze_claude(prompt, images, model, system=system)

    elif provider == "openai":
        return _analyze_openai_compat(
            prompt, images, model,
            api_key=os.environ["OPENAI_API_KEY"],
            base_url=os.environ.get("OPENAI_BASE_URL") or None,
            system=system,
            json_mode=json_mode,
        )

    else:
        raise ValueError(
            f"AI_PROVIDER inválido: '{provider}'. "
            "Valores aceitos: claude, gemini, openai, openrouter"
        )


def _dispatch_rich(
    prompt: str,
    images: list,
    provider: str,
    model: str,
    system: str | None = None,
    json_mode: bool = False,
) -> dict:
    if provider == "gemini":
        available = _get_gemini_models()
        chain = ([model] if model and model not in available else []) + available
        last_exc: Exception | None = None
        for m in chain:
            try:
                print(f"[ai] Gemini → {m}")
                return _analyze_gemini_rich(prompt, images, m, system=system)
            except Exception as e:
                if _is_retryable_gemini(e):
                    print(f"[ai] Falhou ({type(e).__name__}: {str(e)[:80]}), tentando próximo...")
                    last_exc = e
                    continue
                raise
        raise RuntimeError(f"Todos os modelos Gemini falharam. Último erro: {last_exc}")

    if provider == "openai":
        return _analyze_openai_compat_rich(
            prompt, images, model,
            api_key=os.environ["OPENAI_API_KEY"],
            base_url=os.environ.get("OPENAI_BASE_URL") or None,
            system=system,
            json_mode=json_mode,
        )

    raw = _dispatch(prompt, images, provider, model, system=system, json_mode=json_mode)
    usage = {
        "input_tokens": _estimate_tokens(prompt),
        "output_tokens": _estimate_tokens(raw),
        "total_tokens": _estimate_tokens(prompt) + _estimate_tokens(raw),
    }
    return {"text": raw, "usage": usage, "provider": provider, "model": model, "cost_usd": _calculate_cost(model, usage)}


# ── JSON schema para relatório comparativo ───────────────────────────────────

COMPARISON_SCHEMA_PROMPT = """\
Você é um especialista em estratégia de Instagram e análise competitiva de mercado.
Você receberá dados completos de múltiplos perfis do Instagram já analisados individualmente.
Sua tarefa é gerar uma análise comparativa profunda entre todos eles.
Retorne APENAS um JSON válido, sem markdown, sem ```json, sem texto adicional.

O JSON deve seguir EXATAMENTE este schema:

{
  "title": "Análise Comparativa — Benchmarking de Concorrentes",
  "subtitle": "texto descritivo do mercado/nicho analisado",
  "generated_at": "Mês Ano",
  "profiles_analyzed": ["username1", "username2"],
  "market_overview": "Visão geral do mercado/nicho em 3-4 parágrafos: quem são esses players, como se posicionam coletivamente, qual o nível de maturidade do mercado, quais as tendências.",
  "benchmark": [
    {
      "username": "nomeusuario",
      "full_name": "Nome Completo",
      "followers": "ex: 13.5K",
      "posts": "ex: 85",
      "engagement_est": "ex: ~0.6%",
      "score_overall": 82,
      "score_conteudo": 80,
      "score_visual": 75,
      "score_estrategia": 85,
      "score_engajamento": 78,
      "positioning_summary": "Uma frase resumindo o posicionamento deste perfil no mercado.",
      "top_strength": "Principal ponto forte em relação aos concorrentes.",
      "top_weakness": "Principal ponto fraco em relação aos concorrentes.",
      "rank": 1
    }
  ],
  "category_winners": [
    {"category": "Melhor Bio", "winner": "nomeusuario", "why": "Motivo objetivo em 1-2 frases."},
    {"category": "Melhor Estratégia de Conteúdo", "winner": "nomeusuario", "why": "..."},
    {"category": "Melhor Consistência de Publicação", "winner": "nomeusuario", "why": "..."},
    {"category": "Melhor Identidade Visual", "winner": "nomeusuario", "why": "..."},
    {"category": "Maior Potencial de Crescimento", "winner": "nomeusuario", "why": "..."},
    {"category": "Mais Orientado a Conversão", "winner": "nomeusuario", "why": "..."}
  ],
  "market_gaps": [
    {
      "gap": "Desafio ou lacuna identificada no mercado.",
      "opportunity": "Como explorar essa lacuna.",
      "who_benefits": "nomeusuario ou 'todos os perfis'"
    }
  ],
  "profile_deep_dives": [
    {
      "username": "nomeusuario",
      "what_works": ["Ponto forte 1", "Ponto forte 2", "Ponto forte 3"],
      "what_doesnt": ["Ponto fraco 1", "Ponto fraco 2"],
      "steal_this": "O que os outros concorrentes podem aprender ou adaptar deste perfil.",
      "avoid_this": "Erro ou fraqueza que os outros devem evitar."
    }
  ],
  "final_recommendations": [
    {
      "for": "nomeusuario",
      "priority": "Alta",
      "action": "Ação específica recomendada.",
      "rationale": "Por que esta ação é prioritária para este perfil agora."
    }
  ],
  "content_comparison": [
    {
      "username": "nomeusuario",
      "consistency_score": 7,
      "caption_quality": "Alta | Média | Baixa — avaliação das legendas",
      "visual_pattern": "Descreva o padrão visual identificado nos posts",
      "best_post_type": "Formato que mais funciona para este perfil",
      "content_gap_vs_competitors": "O que os outros fazem e este perfil não faz"
    }
  ],
  "executive_summary": "Resumo executivo em 3-4 parágrafos: ranking final com justificativa, quem está melhor posicionado e por quê, as maiores oportunidades de mercado, e os principais takeaways para qualquer player neste nicho."
}

REGRAS OBRIGATÓRIAS:
- Retorne APENAS o JSON, nada mais
- benchmark: inclua TODOS os perfis fornecidos, ordenados do melhor (rank 1) para o pior
- scores: números inteiros de 0 a 100
- category_winners: exatamente 6 categorias
- market_gaps: entre 3 e 5 gaps
- profile_deep_dives: inclua TODOS os perfis
- final_recommendations: pelo menos 1 recomendação por perfil, prioridade = Alta|Média|Baixa
- winner em category_winners deve ser o username sem @
- content_comparison: inclua TODOS os perfis
"""


def _build_comparison_prompt(
    profiles_report_data: dict,   # username -> dict com dados do relatório individual
    profiles_stats: dict,         # username -> dict do profile.json
) -> str:
    """Monta o texto que será enviado para a IA de comparação."""
    sections = []
    for username, data in profiles_report_data.items():
        stats = profiles_stats.get(username, {})
        h = data.get("header", {})
        d = data.get("diagnosis", {})
        s = data.get("strategy", {})
        icp = data.get("icp", {})

        pillars = ", ".join(
            f"{p.get('name')} ({p.get('pct')}%)"
            for p in s.get("content_pillars", [])
        )
        gaps = " | ".join(g.get("title", "") for g in d.get("critical_gaps", []))

        section = f"""=== @{username} ===
Nome: {h.get('full_name', stats.get('full_name', ''))}
Seguidores: {h.get('stats', {}).get('followers', stats.get('followers', '?'))}
Posts: {h.get('stats', {}).get('posts', stats.get('posts_count', '?'))}
Engagement Estimado: {h.get('stats', {}).get('engagement_rate', '?')}

--- DIAGNÓSTICO ---
Posicionamento Atual: {d.get('current_positioning', '')}
Veredicto: {d.get('positioning_verdict', '')}
Problema Central: {d.get('central_problem', '')}
Tom de Voz: {d.get('tone', '')}
Identidade Visual: {d.get('visual', '')}
Público Atual: {d.get('audience_current', '')}
Público Ideal: {d.get('audience_target', '')}
Gap de Público: {d.get('audience_gap', '')}
Gaps Críticos: {gaps}

--- ESTRATÉGIA ---
Novo Posicionamento: {s.get('new_positioning', '')}
Pilares de Conteúdo: {pillars}
Funil Topo: {s.get('funnel_top', '')}
Funil Fundo: {s.get('funnel_bottom', '')}

--- ICP ---
Perfil Primário: {icp.get('primary_title', '')} — {icp.get('primary_demographics', '')}
Dores: {' | '.join(icp.get('pains', [])[:3])}
"""
        # Seção de análise de posts (se disponível no relatório individual)
        pa = data.get("posts_analysis", {})
        if pa:
            posts_rows = []
            for p in (pa.get("posts") or [])[:6]:
                posts_rows.append(
                    f"  {p.get('ref','?')} | {p.get('type','?')} | coerência: {p.get('coherence','?')} | {p.get('caption_summary','')[:60]}"
                )
            posts_block = "\n".join(posts_rows) if posts_rows else "  (dados não disponíveis)"
            section += f"""
--- ANÁLISE DE POSTS ---
Visão Geral: {pa.get('overview', '')}
Consistência: {pa.get('consistency_score', '?')}/10 — {pa.get('consistency_label', '')}
Padrão: {pa.get('pattern_verdict', '')}
Qualidade das Legendas: {pa.get('caption_quality', '')}
Positivos: {' | '.join((pa.get('positives') or [])[:3])}
A Melhorar: {' | '.join((pa.get('improvements') or [])[:3])}
Posts:
{posts_block}"""
        else:
            # Fallback: usa dados brutos do profile.json
            raw_posts = (stats.get("selected_posts") or stats.get("recent_posts") or [])[:6]
            if raw_posts:
                posts_lines = []
                for i, p in enumerate(raw_posts, 1):
                    caption = (p.get("caption") or "")[:80]
                    posts_lines.append(f"  Post {i}: \"{caption}\"" if caption else f"  Post {i}: (sem legenda)")
                section += "\n--- POSTS RECENTES ---\n" + "\n".join(posts_lines)

        sections.append(section.strip())

    return (
        "Abaixo estão os dados completos de cada perfil analisado individualmente.\n"
        "Gere a análise comparativa conforme o schema.\n\n"
        + "\n\n".join(sections)
    )


def analyze_zip(zip_path: str, prompt: str) -> str:
    """Retorna texto livre de análise."""
    provider = os.getenv("AI_PROVIDER", "claude").lower()
    model = os.getenv("AI_MODEL", "") or DEFAULT_MODELS.get(provider, "")
    profile_json, images = _read_zip(zip_path)
    full_prompt = _build_text_prompt(prompt, profile_json)
    print(f"[ai] Provider: {provider} | Modelo inicial: {model} | Imagens: {len(images)}")
    return _dispatch(full_prompt, images, provider, model)


def analyze_comparison_json(
    zip_paths: dict,          # username -> zip_path
    reports_data: dict,       # username -> report dict (já analisado individualmente)
) -> dict:
    """
    Gera análise comparativa entre múltiplos perfis.
    Usa apenas dados de texto (sem imagens) para o relatório comparativo.
    Retorna dict pronto para render_comparison_html().
    """
    provider = os.getenv("AI_PROVIDER", "claude").lower()
    model = os.getenv("AI_MODEL", "") or DEFAULT_MODELS.get(provider, "")

    # Lê profile.json de cada ZIP para ter stats brutos
    profiles_stats: dict = {}
    for username, zip_path in zip_paths.items():
        try:
            pjson, _ = _read_zip(zip_path)
            profiles_stats[username] = json.loads(pjson) if pjson else {}
        except Exception:
            profiles_stats[username] = {}

    comparison_prompt = _build_comparison_prompt(reports_data, profiles_stats)

    print(f"[ai] Comparativo | Provider: {provider} | Modelo: {model} | Perfis: {list(zip_paths.keys())}")

    json_mode = provider == "openai"
    raw = _dispatch(
        comparison_prompt,
        [],           # sem imagens no comparativo
        provider,
        model,
        system=COMPARISON_SCHEMA_PROMPT,
        json_mode=json_mode,
    )

    return _extract_json(raw)


def analyze_zip_json(zip_path: str, prompt: str) -> dict:
    """
    Envia para a IA com o schema de relatório estruturado.
    Retorna um dict pronto para render_html().
    """
    provider = os.getenv("AI_PROVIDER", "claude").lower()
    model = os.getenv("AI_MODEL", "") or DEFAULT_MODELS.get(provider, "")
    profile_json, images = _read_zip(zip_path)
    full_prompt = _build_text_prompt(prompt, profile_json)
    print(f"[ai] JSON report | Provider: {provider} | Modelo inicial: {model} | Imagens: {len(images)}")

    json_mode = provider == "openai"
    raw = _dispatch(full_prompt, images, provider, model,
                    system=REPORT_SCHEMA_PROMPT, json_mode=json_mode)

    return _extract_json(raw)


def analyze_zip_json_rich(zip_path: str, prompt: str) -> dict:
    provider = os.getenv("AI_PROVIDER", "claude").lower()
    model = os.getenv("AI_MODEL", "") or DEFAULT_MODELS.get(provider, "")
    profile_json, images = _read_zip(zip_path)
    full_prompt = _build_text_prompt(prompt, profile_json)
    print(f"[ai] JSON report rich | Provider: {provider} | Modelo inicial: {model} | Imagens: {len(images)}")

    json_mode = provider == "openai"
    result = _dispatch_rich(full_prompt, images, provider, model, system=REPORT_SCHEMA_PROMPT, json_mode=json_mode)
    analysis = _extract_json(result.get("text", ""))
    header = analysis.get("header", {}) if isinstance(analysis, dict) else {}
    stats = header.get("stats", {}) if isinstance(header, dict) else {}
    diagnosis = analysis.get("diagnosis", {}) if isinstance(analysis, dict) else {}
    strategy = analysis.get("strategy", {}) if isinstance(analysis, dict) else {}
    icp = analysis.get("icp", {}) if isinstance(analysis, dict) else {}
    return {
        "analysis": analysis,
        "provider": result.get("provider", provider),
        "model": result.get("model", model),
        "usage": result.get("usage", {}),
        "cost_usd": result.get("cost_usd", 0.0),
        "panel_metrics": {
            "followers": stats.get("followers", ""),
            "posts": stats.get("posts", ""),
            "engagement_rate": stats.get("engagement_rate", ""),
            "positioning_verdict": diagnosis.get("positioning_verdict", ""),
            "central_problem": diagnosis.get("central_problem", ""),
            "new_positioning": strategy.get("new_positioning", ""),
            "primary_icp": icp.get("primary_title", ""),
        },
    }


def analyze_profile_json_rich(profile_data: dict | str, prompt: str, html_text: str = "") -> dict:
    provider = os.getenv("AI_PROVIDER", "claude").lower()
    model = os.getenv("AI_MODEL", "") or DEFAULT_MODELS.get(provider, "")
    profile_json = profile_data if isinstance(profile_data, str) else json.dumps(profile_data or {}, ensure_ascii=False)
    full_prompt = _build_text_prompt_with_html(prompt, profile_json, html_text)
    print(f"[ai] JSON report fallback | Provider: {provider} | Modelo inicial: {model} | HTML: {bool(html_text)}")
    json_mode = provider == "openai"
    result = _dispatch_rich(full_prompt, [], provider, model, system=REPORT_SCHEMA_PROMPT, json_mode=json_mode)
    analysis = _extract_json(result.get("text", ""))
    header = analysis.get("header", {}) if isinstance(analysis, dict) else {}
    stats = header.get("stats", {}) if isinstance(header, dict) else {}
    diagnosis = analysis.get("diagnosis", {}) if isinstance(analysis, dict) else {}
    strategy = analysis.get("strategy", {}) if isinstance(analysis, dict) else {}
    icp = analysis.get("icp", {}) if isinstance(analysis, dict) else {}
    return {
        "analysis": analysis,
        "provider": result.get("provider", provider),
        "model": result.get("model", model),
        "usage": result.get("usage", {}),
        "cost_usd": result.get("cost_usd", 0.0),
        "panel_metrics": {
            "followers": stats.get("followers", ""),
            "posts": stats.get("posts", ""),
            "engagement_rate": stats.get("engagement_rate", ""),
            "positioning_verdict": diagnosis.get("positioning_verdict", ""),
            "central_problem": diagnosis.get("central_problem", ""),
            "new_positioning": strategy.get("new_positioning", ""),
            "primary_icp": icp.get("primary_title", ""),
        },
    }
