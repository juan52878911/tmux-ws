#!/usr/bin/env python3
"""Programa falso para las pruebas: se instala con el nombre del programa que
imita (claude, gh, opencode, security, mock-keychain-helper) y deja en
$WS_MOCK_LOG una línea JSON por llamada con sus argumentos y variables.

Estado del mundo falso, todo bajo $WS_MOCK_DIR:
  keychain.json         {"servicio": "valor"}          (lo lee `security`)
  gh/<dir>/hosts.json   {"usuario": "token"}           (por GH_CONFIG_DIR)
  personal.json         {"usuario": "...", "token": "..."} (helper "osxkeychain")
"""
import json
import os
import sys
from pathlib import Path

nombre = Path(sys.argv[0]).name
args = sys.argv[1:]
base = Path(os.environ.get("WS_MOCK_DIR", "/nonexistent"))
VARS = ("CLAUDE_CONFIG_DIR", "GH_CONFIG_DIR", "GH_BROWSER", "BROWSER", "OPENCODE_CONFIG",
        "ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_MODEL", "WS_CONTEXTO",
        "KLING_TOKEN", "OBSIDIAN_API_KEY", "AWS_PROFILE", "NPM_TOKEN", "PATH")


def registrar(extra=None):
    log = os.environ.get("WS_MOCK_LOG")
    if not log:
        return
    entrada = {"prog": nombre, "args": args, "cwd": os.getcwd(),
               "env": {k: os.environ[k] for k in VARS if k in os.environ}, **(extra or {})}
    with open(log, "a") as f:
        f.write(json.dumps(entrada) + "\n")


def leer(ruta, defecto):
    try:
        return json.loads(Path(ruta).read_text())
    except (OSError, ValueError):
        return defecto


def gh_hosts():
    d = os.environ.get("GH_CONFIG_DIR") or os.path.expanduser("~/.config/gh")  # como gh real
    return leer(Path(d) / "hosts.json", {})


registrar()

if nombre == "security":
    # security find-generic-password -s <servicio> -w
    if args[:1] == ["find-generic-password"] and "-s" in args:
        valor = leer(base / "keychain.json", {}).get(args[args.index("-s") + 1])
        if valor is None:
            sys.exit(44)  # como el real: "item could not be found"
        print(valor)
        sys.exit(0)
    sys.exit(1)

if nombre == "gh":
    hosts = gh_hosts()
    if args[:2] == ["auth", "token"]:
        usuario = args[args.index("--user") + 1] if "--user" in args else next(iter(hosts), None)
        if usuario in hosts:
            print(hosts[usuario])
            sys.exit(0)
        print("no oauth token found", file=sys.stderr)
        sys.exit(1)
    if args[:2] == ["api", "user"]:
        if not hosts:
            sys.exit(4)
        print(next(iter(hosts)))
        sys.exit(0)
    if args[:2] == ["auth", "status"]:
        sys.exit(0 if hosts else 1)
    sys.exit(0)

if nombre == "mock-keychain-helper":
    # Helper de credenciales "personal" (hace de osxkeychain del sistema).
    sys.stdin.read()
    if args[:1] == ["get"]:
        p = leer(base / "personal.json", {})
        print(f"username={p.get('usuario', '')}\npassword={p.get('token', '')}")
    sys.exit(0)

if nombre == "claude" and os.environ.get("WS_DEMO"):
    # Para grabar la demo: enseñar con qué identidad arrancaría Claude.
    perfil = Path(os.environ["CLAUDE_CONFIG_DIR"]).name if os.environ.get("CLAUDE_CONFIG_DIR") else "personal"
    mcps = []
    if "--mcp-config" in args:
        mcps = list(leer(args[args.index("--mcp-config") + 1], {}).get("mcpServers", {}))
    print(f"\033[38;2;203;166;247m✻ Claude Code\033[0m  account: \033[1m{perfil}\033[0m"
          f"  ·  MCPs: {', '.join(mcps) or 'your usual ones'}")
    sys.exit(0)

# claude, opencode y cualquier otro: solo registrar.
sys.exit(0)
