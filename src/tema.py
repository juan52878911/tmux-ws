"""Tema de la UI de ws, definido por el usuario en tmux.conf.

Por defecto usa los colores ANSI del terminal: encaja con cualquier tema sin
configurar nada. Cada color acepta un nombre ANSI (magenta, bright-black…),
un número 0-255, "#rrggbb" o "default".

  set -g @ws-color-accent    '#cba6f7'   títulos, teclas, puntero, sesión actual
  set -g @ws-color-active    '#a6e3a1'   sesiones abiertas, marcas
  set -g @ws-color-muted     '#6c7086'   etiquetas, pie, cabecera
  set -g @ws-color-dim       '#585b70'   detalles secundarios, sesiones cerradas
  set -g @ws-color-info      '#89b4fa'   herramientas Nix
  set -g @ws-color-text      '#cdd6f4'   texto
  set -g @ws-color-match     '#f38ba8'   coincidencias de la búsqueda
  set -g @ws-color-selection '#313244'   fondo de la fila elegida
  set -g @ws-color-border    '#45475a'   bordes de la vista previa
  set -g @ws-nerd-font       on          iconos de Nerd Font
  set -g @ws-icon-normal / -organization / -environment / -github / -search
  set -g @ws-pointer         '▌'
  set -g @ws-preview         'right,58%,border-left,<120(down,55%,border-top)'
"""
import os
import shlex
import subprocess

NOMBRES = ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"]

POR_DEFECTO = {
    "color-accent": "magenta",
    "color-active": "green",
    "color-muted": "bright-black",
    "color-dim": "bright-black",
    "color-info": "blue",
    "color-text": "default",
    "color-match": "red",
    "color-selection": "",          # vacío = el de fzf
    "color-border": "bright-black",
    "nerd-font": "off",
    "pointer": "▌",
    "preview": "right,58%,border-left,<120(down,55%,border-top)",
}

ICONOS_NERD = {"normal": "", "organization": "", "environment": "",
               "github": "", "search": ""}
ICONOS_TEXTO = {"normal": "", "organization": "", "environment": "",
                "github": "gh", "search": ">"}


def _opciones_tmux():
    if not os.environ.get("TMUX"):
        return {}
    r = subprocess.run(["tmux", "show", "-g"], capture_output=True, text=True)
    res = {}
    for linea in r.stdout.splitlines():
        if linea.startswith("@ws-"):
            try:
                clave, valor = shlex.split(linea)[:2]
            except ValueError:
                continue
            res[clave[4:]] = valor
    return res


def ansi(color):
    """Secuencia de escape de primer plano para un color de tema."""
    c = (color or "default").strip().lower()
    if c in ("", "default", "-1"):
        return "\033[39m"
    if c.startswith("#") and len(c) == 7:
        return f"\033[38;2;{int(c[1:3], 16)};{int(c[3:5], 16)};{int(c[5:7], 16)}m"
    if c.isdigit():
        return f"\033[38;5;{int(c)}m"
    brillante = c.startswith("bright-")
    base = c.removeprefix("bright-")
    if base in NOMBRES:
        return f"\033[{(90 if brillante else 30) + NOMBRES.index(base)}m"
    return "\033[39m"


def fzf_color(color):
    """El mismo color en la sintaxis de --color de fzf."""
    c = (color or "").strip().lower()
    return "-1" if c in ("", "default") else c


class Tema:
    def __init__(self):
        o = {**POR_DEFECTO, **_opciones_tmux()}
        self.o = o
        self.ACENTO = ansi(o["color-accent"])
        self.ACTIVO = ansi(o["color-active"])
        self.SECUNDARIO = ansi(o["color-muted"])
        self.TENUE = ansi(o["color-dim"])
        self.INFO = ansi(o["color-info"])
        self.TEXTO = ansi(o["color-text"])
        nerd = o["nerd-font"].lower() in ("on", "1", "true", "yes")
        base = ICONOS_NERD if nerd else ICONOS_TEXTO
        self.iconos = {k: o.get(f"icon-{k}", v) for k, v in base.items()}

    def fzf(self):
        """Opciones de color de fzf derivadas del tema."""
        o = self.o
        acento, fz = fzf_color(o["color-accent"]), fzf_color
        partes = [
            "bg:-1", "preview-bg:-1",
            f"fg:{fz(o['color-text'])}", f"fg+:{fz(o['color-text'])}",
            f"hl:{fz(o['color-match'])}", f"hl+:{fz(o['color-match'])}",
            f"pointer:{acento}", f"prompt:{acento}", f"spinner:{acento}", f"header:{acento}:bold",
            f"marker:{fz(o['color-active'])}", f"ghost:{fz(o['color-dim'])}",
            f"footer:{fz(o['color-muted'])}", f"border:{fz(o['color-border'])}",
            f"preview-border:{fz(o['color-border'])}",
        ]
        if o["color-selection"]:
            partes.append(f"bg+:{fz(o['color-selection'])}")
        return ",".join(partes)
