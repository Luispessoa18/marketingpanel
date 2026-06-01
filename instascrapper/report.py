"""
Renderiza JSON de análise → HTML report e opcionalmente → PDF.
"""
import json
import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader


def render_html(data: dict, output_path: str) -> str:
    """Renderiza o dict de análise no template Jinja2 e salva o HTML."""
    template_dir = Path(__file__).parent
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=False,  # conteúdo vem da IA local, não de input externo
    )
    template = env.get_template("report_template.html")
    html = template.render(data=data)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[report] HTML → {output_path}")
    return output_path


def render_comparison_html(data: dict, output_path: str) -> str:
    """Renderiza o dict de análise comparativa no template e salva o HTML."""
    template_dir = Path(__file__).parent
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=False,
    )
    template = env.get_template("compare_template.html")
    html = template.render(data=data)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[report] Comparativo HTML → {output_path}")
    return output_path


def html_to_pdf(html_path: str, pdf_path: str) -> str:
    """Converte HTML em PDF usando Playwright Chromium."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError(
            "Playwright não encontrado. Execute:\n"
            "  pip install playwright\n"
            "  playwright install chromium"
        )

    abs_html = os.path.abspath(html_path)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(f"file://{abs_html}", wait_until="networkidle")
        page.pdf(
            path=pdf_path,
            format="A4",
            print_background=True,
            margin={"top": "0px", "bottom": "0px", "left": "0px", "right": "0px"},
        )
        browser.close()

    print(f"[report] PDF  → {pdf_path}")
    return pdf_path
