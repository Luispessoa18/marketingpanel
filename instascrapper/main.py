"""
InstaScrap — CLI para análise de perfis do Instagram com Camoufox.

Comandos:
  login     <usuario> <senha>       Faz login e salva a sessão
  profile   <usuario>               Exibe dados de um perfil
  analyze   <usuario>               Análise detalhada de um perfil
  scrape    <usuario>               Raspa perfil, gera ZIP e envia para IA
  compare   <p1> <p2> [p3 ...]      Compara múltiplos perfis (usa cache do dia)
  cache                             Lista perfis cacheados hoje
  sessions                          Lista sessões salvas
  logout    <usuario>               Remove sessão salva

Opções do scrape:
  --prompt  "texto"   Prompt de análise para a IA
  --out     /caminho  Diretório de saída do ZIP (padrão: .)
  --html              Gera relatório HTML formatado (JSON → template)
  --pdf               Gera HTML + PDF (requer: playwright install chromium)
  --no-ai             Só gera o ZIP, sem chamar a IA

Opções do compare:
  --out     /caminho  Diretório de saída (padrão: .)
  --html              Gera relatórios individuais + comparativo HTML
  --pdf               Gera também PDFs

Configuração da IA (variáveis de ambiente ou .env):
  AI_PROVIDER   = claude | gemini | openai | openrouter  (padrão: claude)
  AI_MODEL      = nome do modelo
  ANTHROPIC_API_KEY / GOOGLE_API_KEY / OPENAI_API_KEY / OPENROUTER_API_KEY

Exemplos:
  python3 main.py login meuuser minhasenha
  python3 main.py scrape algum_perfil --html
  python3 main.py compare perfil1 perfil2 perfil3 --html
  python3 main.py cache
"""

import sys
import json
import os
from collections.abc import Callable
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

# Carrega .env se existir
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from instagram import InstagramClient
from session import list_sessions, delete_session

console = Console()

COMMANDS: dict[str, dict[str, object]] = {
    "login": {
        "usage": "login <usuario> <senha>",
        "description": "Faz login e salva a sessao.",
        "supports_as": False,
    },
    "inspect": {
        "usage": "inspect <alvo> [--as usuario]",
        "description": "Abre a inspecao de um perfil usando a sessao salva.",
        "supports_as": True,
    },
    "profile": {
        "usage": "profile <alvo> [--as usuario]",
        "description": "Exibe dados de um perfil.",
        "supports_as": True,
    },
    "analyze": {
        "usage": "analyze <alvo> [--as usuario]",
        "description": "Roda a analise detalhada de um perfil.",
        "supports_as": True,
    },
    "scrape": {
        "usage": "scrape <alvo> [--prompt texto] [--out dir] [--html] [--pdf] [--no-ai] [--as usuario]",
        "description": "Raspa o perfil e opcionalmente envia para IA.",
        "supports_as": True,
    },
    "compare": {
        "usage": "compare <p1> <p2> [p3 ...] [--html] [--pdf] [--out dir] [--as usuario]",
        "description": "Compara multiplos perfis.",
        "supports_as": True,
    },
    "cache": {
        "usage": "cache",
        "description": "Lista o cache do dia.",
        "supports_as": False,
    },
    "sessions": {
        "usage": "sessions",
        "description": "Lista sessoes salvas.",
        "supports_as": False,
    },
    "logout": {
        "usage": "logout <usuario>",
        "description": "Remove uma sessao salva.",
        "supports_as": False,
    },
}


def cmd_login(args: list[str]) -> None:
    if len(args) < 2:
        console.print("[red]Uso: python3 main.py login <usuario> <senha>[/red]")
        sys.exit(1)
    username, password = args[0], args[1]
    with InstagramClient(headless=True) as client:
        ok = client.login(username, password, save=True)
        if ok:
            console.print(f"[green]Logado como[/green] [bold]{username}[/bold]")
        else:
            console.print("[red]Falha no login.[/red]")
            sys.exit(1)


def cmd_profile(logged_user: str, args: list[str]) -> None:
    if not args:
        console.print("[red]Uso: python3 main.py profile <alvo>[/red]")
        sys.exit(1)
    target = args[0]

    with InstagramClient(headless=True) as client:
        if logged_user:
            if not client.login(logged_user, "", save=False):
                console.print(
                    "[red]Sessão do Instagram inexistente ou expirada. "
                    "Rode: [bold]python3 main.py login <usuario> <senha>[/bold] nesta pasta.[/red]"
                )
                sys.exit(1)
        data = client.get_profile(target)

    _print_profile(data)


def cmd_analyze(logged_user: str, args: list[str]) -> None:
    if not args:
        console.print("[red]Uso: python3 main.py analyze <alvo>[/red]")
        sys.exit(1)
    target = args[0]

    with InstagramClient(headless=True) as client:
        if logged_user:
            if not client.login(logged_user, "", save=False):
                console.print(
                    "[red]Sessão do Instagram inexistente ou expirada. "
                    "Rode: [bold]python3 main.py login <usuario> <senha>[/bold] nesta pasta.[/red]"
                )
                sys.exit(1)
        result = client.analyze_profile(target)

    _print_profile(result["profile"])
    _print_analysis(result["analysis"])


def cmd_scrape(logged_user: str, args: list[str]) -> None:
    if not args:
        console.print(
            "[red]Uso: python3 main.py scrape <alvo> "
            "[--prompt 'texto'] [--out /dir] [--html] [--pdf] [--no-ai][/red]"
        )
        sys.exit(1)

    target = args[0]
    rest = args[1:]

    # Parse flags
    prompt = (
        "Faça uma auditoria completa deste perfil do Instagram: "
        "diagnóstico de posicionamento, público-alvo ideal (ICP), "
        "estratégia de 90 dias com calendário de conteúdo, e quick wins para as próximas 48h."
    )
    out_dir = "."
    no_ai   = "--no-ai" in rest
    gen_html = "--html" in rest or "--pdf" in rest
    gen_pdf  = "--pdf" in rest

    if "--prompt" in rest:
        idx = rest.index("--prompt")
        prompt = rest[idx + 1]
    if "--out" in rest:
        idx = rest.index("--out")
        out_dir = rest[idx + 1]

    from database import get_cache, save_cache
    from ai_analyze import _read_zip as _az_read_zip

    # Verifica cache antes de scraping
    cache = get_cache(target)
    if cache and cache.get("zip_path") and os.path.exists(cache["zip_path"]):
        console.print(f"[dim]Cache hit: @{target} já scraped hoje. Usando ZIP existente.[/dim]")
        zip_path = cache["zip_path"]
    else:
        with InstagramClient(headless=True) as client:
            if logged_user:
                if not client.login(logged_user, "", save=False):
                    console.print(
                        "[red]Sessão do Instagram inexistente ou expirada. "
                        "Rode: [bold]python3 main.py login <usuario> <senha>[/bold] nesta pasta.[/red]"
                    )
                    sys.exit(1)
            zip_path = client.scrape_profile(target, out_dir=out_dir)

        pjson, _ = _az_read_zip(zip_path)
        save_cache(target, zip_path=zip_path, profile_json=pjson)

    console.print(f"[green]ZIP:[/green] {zip_path}")

    if no_ai:
        return

    provider = os.getenv("AI_PROVIDER", "claude")
    console.print(f"[cyan]Enviando para IA ({provider})...[/cyan]")

    try:
        if gen_html:
            from ai_analyze import analyze_zip_json
            from report import render_html, html_to_pdf

            # Reutiliza análise IA cacheada se disponível
            cache = get_cache(target)
            if cache and cache.get("report_data"):
                console.print("[dim]Cache hit: dados IA já existem para hoje.[/dim]")
                data = json.loads(cache["report_data"])
            else:
                data = analyze_zip_json(zip_path, prompt)
                save_cache(target, report_data=data)

            html_path = zip_path.replace(".zip", "_report.html")
            render_html(data, html_path)
            save_cache(target, report_html=html_path)
            console.print(f"[green]HTML gerado:[/green] {html_path}")

            if gen_pdf:
                pdf_path = zip_path.replace(".zip", "_report.pdf")
                console.print("[cyan]Gerando PDF (aguarde o Chromium carregar)...[/cyan]")
                html_to_pdf(html_path, pdf_path)
                console.print(f"[green]PDF gerado:[/green]  {pdf_path}")
        else:
            from ai_analyze import analyze_zip
            result = analyze_zip(zip_path, prompt)
            console.print(Panel(result, title="Análise da IA", border_style="green", expand=False))
            txt_path = zip_path.replace(".zip", "_analysis.txt")
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(result)
            console.print(f"[green]Análise salva em:[/green] {txt_path}")

    except KeyError as e:
        console.print(f"[red]Chave de API não encontrada: {e}. Verifique seu .env[/red]")
        sys.exit(1)
    except RuntimeError as e:
        console.print(f"[red]Erro:[/red] {e}")
        sys.exit(1)


def cmd_compare(logged_user: str, args: list[str]) -> None:
    """
    Raspa múltiplos perfis (com cache do dia), gera relatórios individuais
    e um relatório comparativo final.

    Uso: python3 main.py compare <p1> <p2> [p3 ...] [--html] [--pdf] [--out /dir]
    """
    if len(args) < 2:
        console.print(
            "[red]Uso: python3 main.py compare <p1> <p2> [p3 ...] "
            "[--html] [--pdf] [--out /dir][/red]"
        )
        sys.exit(1)

    # Flags
    gen_html = "--html" in args or "--pdf" in args
    gen_pdf  = "--pdf" in args
    out_dir  = "."
    if "--out" in args:
        idx     = args.index("--out")
        out_dir = args[idx + 1]
        args    = [a for i, a in enumerate(args) if i not in (idx, idx + 1)]

    targets = [a.lstrip("@") for a in args if not a.startswith("--")]

    if len(targets) < 2:
        console.print("[red]Compare precisa de pelo menos 2 perfis.[/red]")
        sys.exit(1)

    from database import get_cache, save_cache
    from ai_analyze import _read_zip as _az_read_zip

    provider = os.getenv("AI_PROVIDER", "claude")

    # ── FASE 1: Scraping (só o que não está em cache) ──────────────────────────
    zip_paths: dict[str, str] = {}

    needs_scraping = []
    for target in targets:
        cache = get_cache(target)
        if cache and cache.get("zip_path") and os.path.exists(cache["zip_path"]):
            console.print(f"[dim]Cache hit (zip): @{target}[/dim]")
            zip_paths[target] = cache["zip_path"]
        else:
            needs_scraping.append(target)

    if needs_scraping:
        console.print(f"[cyan]Scraping {len(needs_scraping)} perfil(s): {needs_scraping}[/cyan]")
        with InstagramClient(headless=True) as client:
            if logged_user:
                if not client.login(logged_user, "", save=False):
                    console.print(
                        "[red]Sessão do Instagram inexistente ou expirada. "
                        "Rode: [bold]python3 main.py login <usuario> <senha>[/bold] nesta pasta.[/red]"
                    )
                    sys.exit(1)
            for target in needs_scraping:
                console.print(f"[cyan]  → @{target}...[/cyan]")
                zip_path = client.scrape_profile(target, out_dir=out_dir)
                zip_paths[target] = zip_path
                pjson, _ = _az_read_zip(zip_path)
                save_cache(target, zip_path=zip_path, profile_json=pjson)
                console.print(f"[green]  ZIP: {zip_path}[/green]")
    else:
        console.print("[green]Todos os perfis encontrados no cache de hoje.[/green]")

    # ── FASE 2: Análise IA individual ──────────────────────────────────────────
    all_report_data: dict[str, dict] = {}
    default_prompt = (
        "Faça uma auditoria completa deste perfil do Instagram: "
        "diagnóstico de posicionamento, público-alvo ideal (ICP), "
        "estratégia de 90 dias com calendário de conteúdo, e quick wins para as próximas 48h."
    )

    from ai_analyze import analyze_zip_json
    from report import render_html

    for target in targets:
        cache = get_cache(target)

        # Dados já analisados pela IA?
        if cache and cache.get("report_data"):
            console.print(f"[dim]Cache hit (IA): @{target}[/dim]")
            all_report_data[target] = json.loads(cache["report_data"])
        else:
            console.print(f"[cyan]Analisando @{target} com IA ({provider})...[/cyan]")
            data = analyze_zip_json(zip_paths[target], default_prompt)
            all_report_data[target] = data
            save_cache(target, report_data=data)

        # Relatório HTML individual
        if gen_html:
            if cache and cache.get("report_html") and os.path.exists(cache["report_html"]):
                console.print(f"[dim]Cache hit (HTML): @{target}[/dim]")
            else:
                html_path = zip_paths[target].replace(".zip", "_report.html")
                render_html(all_report_data[target], html_path)
                save_cache(target, report_html=html_path)
                console.print(f"[green]  HTML individual: {html_path}[/green]")

    # ── FASE 3: Relatório comparativo ─────────────────────────────────────────
    console.print(f"\n[cyan]Gerando análise comparativa de {len(targets)} perfis...[/cyan]")

    from ai_analyze import analyze_comparison_json
    from report import render_comparison_html

    comp_data = analyze_comparison_json(
        {t: zip_paths[t] for t in targets},
        all_report_data,
    )

    import time
    ts = time.strftime("%Y%m%d_%H%M%S")
    slug = "_vs_".join(targets[:4])  # evita nomes muito longos
    comp_html = os.path.join(out_dir, f"compare_{slug}_{ts}.html")
    render_comparison_html(comp_data, comp_html)
    console.print(f"[bold green]\nComparativo HTML: {comp_html}[/bold green]")

    if gen_pdf:
        from report import html_to_pdf
        comp_pdf = comp_html.replace(".html", ".pdf")
        console.print("[cyan]Gerando PDF comparativo...[/cyan]")
        html_to_pdf(comp_html, comp_pdf)
        console.print(f"[bold green]Comparativo PDF:  {comp_pdf}[/bold green]")


def cmd_cache() -> None:
    """Lista perfis cacheados hoje no banco de dados local."""
    from database import list_cached
    from datetime import date

    rows = list_cached()
    if not rows:
        console.print(f"[yellow]Nenhum perfil cacheado hoje ({date.today().isoformat()}).[/yellow]")
        return

    t = Table(title=f"Cache de hoje ({date.today().isoformat()})")
    t.add_column("Usuário", style="cyan")
    t.add_column("ZIP", style="dim")
    t.add_column("HTML", style="dim")
    t.add_column("IA", style="green")
    t.add_column("Hora")

    for r in rows:
        t.add_row(
            f"@{r['username']}",
            "✓" if r.get("zip_path") else "—",
            "✓" if r.get("report_html") else "—",
            "✓" if r.get("has_ai") else "—",
            r.get("scraped_at", "")[:19],
        )
    console.print(t)


def cmd_inspect(logged_user: str, args: list[str]) -> None:
    if not args:
        console.print("[red]Uso: python3 main.py inspect <alvo>[/red]")
        sys.exit(1)
    target = args[0]
    with InstagramClient(headless=True) as client:
        if logged_user:
            if not client.login(logged_user, "", save=False):
                console.print(
                    "[red]Sessão do Instagram inexistente ou expirada. "
                    "Rode: [bold]python3 main.py login <usuario> <senha>[/bold] nesta pasta.[/red]"
                )
                sys.exit(1)
        client.inspect(target)


def cmd_sessions() -> None:
    sessions = list_sessions()
    if not sessions:
        console.print("[yellow]Nenhuma sessão salva.[/yellow]")
        return
    t = Table(title="Sessões salvas")
    t.add_column("Usuário", style="cyan")
    for s in sessions:
        t.add_row(s)
    console.print(t)


def cmd_logout(args: list[str]) -> None:
    if not args:
        console.print("[red]Uso: python3 main.py logout <usuario>[/red]")
        sys.exit(1)
    username = args[0]
    if delete_session(username):
        console.print(f"[green]Sessão de '{username}' removida.[/green]")
    else:
        console.print(f"[yellow]Nenhuma sessão encontrada para '{username}'.[/yellow]")


def _render_help() -> str:
    lines = [
        "InstaScrap - CLI para analise de perfis do Instagram com Camoufox.",
        "",
        "Comandos:",
    ]
    for meta in COMMANDS.values():
        lines.append(f"  {meta['usage']}")
        lines.append(f"      {meta['description']}")

    lines.extend(
        [
            "",
            "Configuracao da IA (.env ou variaveis de ambiente):",
            "  AI_PROVIDER   = claude | gemini | openai | openrouter  (padrao: claude)",
            "  AI_MODEL      = nome do modelo",
            "  ANTHROPIC_API_KEY / GOOGLE_API_KEY / OPENAI_API_KEY / OPENROUTER_API_KEY",
            "",
            "Exemplos:",
            "  python main.py login meuuser minhasenha",
            "  python main.py inspect algum_perfil --as meuuser",
            "  python main.py scrape algum_perfil --html --pdf --as meuuser",
            "  python main.py compare perfil1 perfil2 perfil3 --html",
        ]
    )
    return "\n".join(lines)


def _print_usage_error(command_name: str) -> None:
    console.print(f"[red]Uso: python main.py {COMMANDS[command_name]['usage']}[/red]")
    sys.exit(1)


def _extract_logged_user(command_name: str, args: list[str]) -> tuple[str | None, list[str]]:
    supports_as = bool(COMMANDS[command_name]["supports_as"])

    if "--as" in args and not supports_as:
        console.print(f"[red]O comando '{command_name}' nao suporta --as.[/red]")
        _print_usage_error(command_name)

    logged_user = None
    rest = list(args)

    if supports_as and "--as" in rest:
        idx = rest.index("--as")
        if idx + 1 >= len(rest):
            _print_usage_error(command_name)
        logged_user = rest[idx + 1]
        rest = rest[:idx] + rest[idx + 2:]
    elif supports_as:
        sessions = list_sessions()
        if sessions:
            logged_user = sessions[0]

    return logged_user, rest


# ── display helpers ───────────────────────────────────────────────────────────

def _print_profile(p: dict) -> None:
    lines = []
    if p.get("full_name"):
        lines.append(f"[bold]{p['full_name']}[/bold]  (@{p['username']})")
    else:
        lines.append(f"[bold]@{p['username']}[/bold]")

    if p.get("verified"):
        lines.append("[blue]✓ Conta verificada[/blue]")
    if p.get("private"):
        lines.append("[yellow]🔒 Conta privada[/yellow]")

    lines.append("")
    if p.get("bio"):
        lines.append(f"[italic]{p['bio']}[/italic]")
    if p.get("external_link"):
        lines.append(f"[link]{p['external_link']}[/link]")

    lines.append("")
    stats = (
        f"Posts: [cyan]{p.get('posts') or '?'}[/cyan]  "
        f"Seguidores: [cyan]{p.get('followers') or '?'}[/cyan]  "
        f"Seguindo: [cyan]{p.get('following') or '?'}[/cyan]"
    )
    lines.append(stats)

    console.print(Panel("\n".join(lines), title="Perfil", border_style="magenta"))


def _print_analysis(a: dict) -> None:
    t = Table(title="Análise do Perfil", border_style="cyan")
    t.add_column("Métrica", style="bold")
    t.add_column("Valor")

    t.add_row("Tier", a.get("tier", "?"))
    t.add_row("Seguidores (int)", f"{a.get('followers_int', 0):,}")
    t.add_row("Verificado", "Sim" if a.get("is_verified") else "Não")
    t.add_row("Privado", "Sim" if a.get("is_private") else "Não")
    t.add_row("Provável negócio", "Sim" if a.get("is_business_likely") else "Não")
    t.add_row("Tamanho da bio", str(a.get("bio_length", 0)))
    t.add_row("Bio tem emoji", "Sim" if a.get("bio_has_emoji") else "Não")
    t.add_row("Bio menciona link", "Sim" if a.get("bio_has_link_mention") else "Não")

    console.print(t)


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help", "help"):
        console.print(_render_help(), markup=False)
        return

    cmd = args[0]
    rest = args[1:]

    # Para comandos que precisam de sessão, o usuário pode passar --as <user>
    logged_user = None
    if "--as" in rest:
        idx = rest.index("--as")
        logged_user = rest[idx + 1]
        rest = rest[:idx] + rest[idx + 2:]
    else:
        # Usa a primeira sessão salva automaticamente
        sessions = list_sessions()
        if sessions:
            logged_user = sessions[0]

    if cmd == "login":
        cmd_login(rest)
    elif cmd == "inspect":
        cmd_inspect(logged_user, rest)
    elif cmd == "profile":
        cmd_profile(logged_user, rest)
    elif cmd == "analyze":
        cmd_analyze(logged_user, rest)
    elif cmd == "scrape":
        cmd_scrape(logged_user, rest)
    elif cmd == "compare":
        cmd_compare(logged_user, rest)
    elif cmd == "cache":
        cmd_cache()
    elif cmd == "sessions":
        cmd_sessions()
    elif cmd == "logout":
        cmd_logout(rest)
    else:
        console.print(f"[red]Comando desconhecido: {cmd}[/red]")
        console.print(_render_help(), markup=False)
        sys.exit(1)


def run_cli() -> None:
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help", "help"):
        console.print(_render_help(), markup=False)
        return

    cmd = args[0]
    if cmd not in COMMANDS:
        console.print(f"[red]Comando desconhecido: {cmd}[/red]")
        console.print(_render_help(), markup=False)
        sys.exit(1)

    rest = args[1:]
    logged_user, rest = _extract_logged_user(cmd, rest)

    routes: dict[str, Callable[..., None]] = {
        "login": cmd_login,
        "inspect": cmd_inspect,
        "profile": cmd_profile,
        "analyze": cmd_analyze,
        "scrape": cmd_scrape,
        "compare": cmd_compare,
        "cache": cmd_cache,
        "sessions": cmd_sessions,
        "logout": cmd_logout,
    }

    handler = routes[cmd]
    if bool(COMMANDS[cmd]["supports_as"]):
        handler(logged_user, rest)
    elif rest:
        handler(rest)
    else:
        handler()


if __name__ == "__main__":
    run_cli()
