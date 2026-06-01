from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


BASE_DIR = Path(__file__).resolve().parent
MAIN_FILE = BASE_DIR / "main.py"
ALLOWED_COMMANDS = {
    "login",
    "inspect",
    "profile",
    "analyze",
    "scrape",
    "compare",
    "cache",
    "sessions",
    "logout",
}

COMMAND_SPECS = {
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


class CommandRequest(BaseModel):
    command: Literal[
        "login",
        "inspect",
        "profile",
        "analyze",
        "scrape",
        "compare",
        "cache",
        "sessions",
        "logout",
    ]
    args: list[str] = Field(default_factory=list)
    as_user: str | None = None


class CommandResponse(BaseModel):
    ok: bool
    command: str
    invoked: list[str]
    exit_code: int
    stdout: str
    stderr: str


class LoginRequest(BaseModel):
    usuario: str = Field(..., description="Usuario para login.")
    senha: str = Field(..., description="Senha da conta.")


class TargetAsRequest(BaseModel):
    alvo: str = Field(..., description="Perfil alvo.")
    as_user: str | None = Field(default=None, description="Sessao a usar com --as.")


class ScrapeRequest(TargetAsRequest):
    prompt: str | None = Field(default=None, description="Texto para --prompt.")
    out: str | None = Field(default=None, description="Diretorio de saida para --out.")
    html: bool = Field(default=False, description="Adiciona --html.")
    pdf: bool = Field(default=False, description="Adiciona --pdf.")
    no_ai: bool = Field(default=False, description="Adiciona --no-ai.")


class CompareRequest(BaseModel):
    perfis: list[str] = Field(..., min_length=2, description="Lista de perfis para comparar.")
    html: bool = Field(default=False, description="Adiciona --html.")
    pdf: bool = Field(default=False, description="Adiciona --pdf.")
    out: str | None = Field(default=None, description="Diretorio de saida para --out.")
    as_user: str | None = Field(default=None, description="Sessao a usar com --as.")


class LogoutRequest(BaseModel):
    usuario: str = Field(..., description="Usuario da sessao a remover.")


app = FastAPI(
    title="InstaScrapper Command API",
    description="API que encaminha comandos permitidos para o main.py.",
    version="1.0.0",
)


def build_command(payload: CommandRequest) -> list[str]:
    if payload.command not in ALLOWED_COMMANDS:
        raise HTTPException(status_code=400, detail="Comando nao permitido.")

    if payload.as_user and not COMMAND_SPECS[payload.command]["supports_as"]:
        raise HTTPException(
            status_code=400,
            detail=f"O comando '{payload.command}' nao aceita 'as_user'.",
        )

    command = [sys.executable, str(MAIN_FILE), payload.command, *payload.args]
    if payload.as_user:
        command.extend(["--as", payload.as_user])
    return command


def run_main_command(payload: CommandRequest) -> CommandResponse:
    command = build_command(payload)
    result = subprocess.run(
        command,
        cwd=str(BASE_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return CommandResponse(
        ok=result.returncode == 0,
        command=payload.command,
        invoked=command,
        exit_code=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )


def run_command_name(command: str, args: list[str] | None = None, as_user: str | None = None) -> CommandResponse:
    return run_main_command(
        CommandRequest(
            command=command,
            args=args or [],
            as_user=as_user,
        )
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/commands")
def commands() -> dict[str, object]:
    return {
        "main_file": str(MAIN_FILE),
        "commands": COMMAND_SPECS,
    }


@app.post("/run", response_model=CommandResponse)
def run_command(payload: CommandRequest) -> CommandResponse:
    return run_main_command(payload)


@app.post("/login", response_model=CommandResponse, tags=["commands"], summary="Login")
def login_route(payload: LoginRequest) -> CommandResponse:
    return run_command_name("login", [payload.usuario, payload.senha])


@app.post("/inspect", response_model=CommandResponse, tags=["commands"], summary="Inspect")
def inspect_route(payload: TargetAsRequest) -> CommandResponse:
    return run_command_name("inspect", [payload.alvo], payload.as_user)


@app.post("/profile", response_model=CommandResponse, tags=["commands"], summary="Profile")
def profile_route(payload: TargetAsRequest) -> CommandResponse:
    return run_command_name("profile", [payload.alvo], payload.as_user)


@app.post("/analyze", response_model=CommandResponse, tags=["commands"], summary="Analyze")
def analyze_route(payload: TargetAsRequest) -> CommandResponse:
    return run_command_name("analyze", [payload.alvo], payload.as_user)


@app.post("/scrape", response_model=CommandResponse, tags=["commands"], summary="Scrape")
def scrape_route(payload: ScrapeRequest) -> CommandResponse:
    args = [payload.alvo]
    if payload.prompt:
        args.extend(["--prompt", payload.prompt])
    if payload.out:
        args.extend(["--out", payload.out])
    if payload.html:
        args.append("--html")
    if payload.pdf:
        args.append("--pdf")
    if payload.no_ai:
        args.append("--no-ai")
    return run_command_name("scrape", args, payload.as_user)


@app.post("/compare", response_model=CommandResponse, tags=["commands"], summary="Compare")
def compare_route(payload: CompareRequest) -> CommandResponse:
    args = list(payload.perfis)
    if payload.html:
        args.append("--html")
    if payload.pdf:
        args.append("--pdf")
    if payload.out:
        args.extend(["--out", payload.out])
    return run_command_name("compare", args, payload.as_user)


@app.get("/cache", response_model=CommandResponse, tags=["commands"], summary="Cache")
def cache_route() -> CommandResponse:
    return run_command_name("cache")


@app.get("/sessions", response_model=CommandResponse, tags=["commands"], summary="Sessions")
def sessions_route() -> CommandResponse:
    return run_command_name("sessions")


@app.post("/logout", response_model=CommandResponse, tags=["commands"], summary="Logout")
def logout_route(payload: LogoutRequest) -> CommandResponse:
    return run_command_name("logout", [payload.usuario])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api_fastapi:app", host="0.0.0.0", port=8000, reload=False)
