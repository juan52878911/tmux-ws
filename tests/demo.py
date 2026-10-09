#!/usr/bin/env python3
"""Demo aislada para grabar el GIF del README.

    python3 tests/demo.py            # abre un tmux aparte en este terminal
    DEMO_PREFIX=C-b python3 tests/demo.py

Organizaciones, cuentas y repos inventados (Acme, Globex): nada real sale en
pantalla. Al salir del tmux (prefix + d) se borra todo.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mundo import RAIZ, Mundo  # noqa: E402

PREFIJO = os.environ.get("DEMO_PREFIX", "C-a")


def construir():
    m = Mundo()
    m.secreto("MCP_TOKEN", "demo")
    (m.mcp("docs", url="https://mcp.example.dev/docs", headers={"Authorization": "Bearer ${MCP_TOKEN}"})
      .mcp("tree-sitter", cmd=["npx", "-y", "mcp-server-tree-sitter"])
      .mcp("notes", cmd=["notes-mcp"]))
    (m.bloque("base", mcps=["docs", "tree-sitter"], agentes=["claude"])
      .bloque("notes", mcps=["notes"])
      .bloque("node", herramientas=["nodejs_24"]))
    m.cuenta_github("acme", usuario="jane-acme", token="tok")
    m.organizacion("acme", nombre="Acme", prefijo="ac", github="acme", claude="propia",
                   git_correo="jane@acme.io", github_orgs=["acme-inc"], bloques=["base", "notes"])
    m.organizacion("globex", nombre="Globex", prefijo="gx", github="personal", claude="personal",
                   git_correo="jane@globex.dev", bloques=["base"])
    m.entorno("lab", nombre="Lab", bloques=["base", "node"])
    m.cfg["github"]["personal"]["usuario"] = "jane"
    m._json(m.home / ".config/gh/hosts.json", {"jane": "tok"})
    m.proyecto("acme/api", ruta=m.home / "work/acme/api", remoto="https://github.com/acme-inc/api.git")
    m.proyecto("acme/web", ruta=m.home / "work/acme/web", remoto="https://github.com/acme-inc/web.git")
    m.proyecto("globex/site", ruta=m.home / "work/globex/site", remoto="https://github.com/jane/site.git")
    m.proyecto("lab/sandbox", ruta=m.home / "lab/sandbox", git=False)
    m.escribir()
    m.instalar_shims()
    m.ws("sync")
    # zsh limpio con un prompt corto
    (m.home / ".zshrc").write_text(
        f'export PATH="{m.home}/.local/share/ws/shims:{m.bin}:$PATH"\n'
        "PROMPT='%F{#6c7086}%2~%f %F{#cba6f7}❯%f '\n"
        "alias gh-user='gh api user'\n")
    return m


def conf_tmux(m):
    flotante = m.dir / "float.sh"
    flotante.write_text('#!/bin/sh\nexec tmux display-popup -c "$2" -w 80% -h 80% -E "tmux new-session -A -s f-$1"\n')
    flotante.chmod(0o755)
    conf = m.dir / "tmux.conf"
    conf.write_text(f"""
set -g prefix {PREFIJO}
unbind C-b
bind {PREFIJO} send-prefix
set -g default-shell /bin/zsh
set -g default-terminal tmux-256color
set -g escape-time 0
set -g mouse on
setw -g automatic-rename off
set -g allow-rename off
set -g status-style bg=default
set -g status-left "#[fg=#a6e3a1,bold]  #S #{{?@ws,#[fg=#cba6f7#,nobold] #{{@ws}} ,}}#[fg=#585b70]▐ "
set -g status-left-length 80
set -g status-right "#[fg=#585b70]tmux-ws demo "
set -g window-status-format "#[fg=#6c7086] #W "
set -g window-status-current-format "#[fg=#cdd6f4,bold] #W "
set -g popup-style "fg=#cdd6f4,bg=#181825"
set -g popup-border-style "fg=#585b70"
set -g popup-border-lines rounded
set -g @ws-bin '{m.bin / "ws"}'
set -g @ws-float-script '{flotante}'
set -g @ws-color-accent '#cba6f7'
set -g @ws-color-active '#a6e3a1'
set -g @ws-color-muted '#6c7086'
set -g @ws-color-dim '#585b70'
set -g @ws-color-info '#89b4fa'
set -g @ws-color-text '#cdd6f4'
set -g @ws-color-match '#f38ba8'
set -g @ws-color-selection '#313244'
set -g @ws-color-border '#45475a'
set -g @ws-nerd-font on
run-shell '{RAIZ / "ws.tmux"}'
""")
    return conf


def main():
    m = construir()
    conf = conf_tmux(m)
    m.socket = m.socket_corto()
    env = m.env(WS_DEMO=1, ZDOTDIR=m.home, SHELL="/bin/zsh", TERM=os.environ.get("TERM", "xterm-256color"))
    env.pop("TMUX", None)
    try:
        subprocess.run(["tmux", "-S", m.socket, "-f", str(conf), "new-session", "-d", "-s", "main",
                        "-c", str(m.home)], check=True, env=env)
        subprocess.run(["tmux", "-S", m.socket, "attach", "-t", "main"], env=env)
    finally:
        m.cerrar()


if __name__ == "__main__":
    main()
