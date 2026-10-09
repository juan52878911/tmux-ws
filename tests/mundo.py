"""Mundo de pruebas: un HOME temporal con cuentas, perfiles y repos falsos.

Nada toca tus cuentas reales: HOME, el Llavero (`security`), gh, claude y
opencode son programas falsos (tests/mocks/mock.py) que leen su estado de
archivos del mundo y registran cada llamada. git y tmux son los de verdad,
pero con su config y su servidor propios.

    m = Mundo()
    m.cuenta_github("empresa", usuario="yo-empresa", token="tok-emp")
    m.secreto("KLING_TOKEN", "k-123")
    m.organizacion("empresa", github="empresa", claude="propia", github_orgs=["empresa-co"])
    m.proyecto("empresa/api")                # carpeta y repo git creados solos
    r = m.ws("exec", "claude", cwd=m.ruta("empresa/api"))
    m.llamadas("claude")[-1]["env"]["CLAUDE_CONFIG_DIR"]
    m.cerrar()
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
WS_PY = RAIZ / "src" / "ws.py"
MOCK = Path(__file__).resolve().parent / "mocks" / "mock.py"
FALSOS = ("claude", "gh", "opencode", "security", "mock-keychain-helper")


def toml(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        return "[" + ", ".join(toml(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{ " + ", ".join(f'{k} = {toml(x)}' for k, x in v.items()) + " }"
    return json.dumps(str(v), ensure_ascii=False)


class Mundo:
    def __init__(self):
        self.dir = Path(tempfile.mkdtemp(prefix="ws-prueba-")).resolve()
        self.home = self.dir / "home"
        self.mock = self.dir / "mock"
        self.bin = self.dir / "bin"
        for d in (self.home, self.mock, self.bin):
            d.mkdir(parents=True)
        for nombre in FALSOS:
            (self.bin / nombre).symlink_to(MOCK)
        # fzf envuelto: deja un aviso mientras hay una lista abierta (con sus
        # argumentos), para que las pruebas de punta a punta esperen a lo que
        # pasa de verdad y no a pausas fijas.
        fzf_real = shutil.which("fzf")
        if fzf_real:
            (self.bin / "fzf").write_text(
                "#!/bin/sh\n"
                'aviso="$WS_MOCK_DIR/fzf.$$"\n'
                'printf "%s\\n" "$@" > "$aviso"\n'
                f'"{fzf_real}" "$@"\n'
                "rc=$?\n"
                'rm -f "$aviso"\n'
                "exit $rc\n")
            (self.bin / "fzf").chmod(0o755)
        # ws en sí, para el helper de git y los shims.
        ws = self.bin / "ws"
        ws.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{WS_PY}" "$@"\n')
        ws.chmod(0o755)
        self.log = self.mock / "llamadas.jsonl"
        self.cfg = {"github": {"personal": {"usuario": "yo-personal"}}, "organizaciones": {},
                    "entornos": {}, "bloques": {}, "mcps": {}, "proyectos": {}, "agentes": {},
                    "acciones": {}, "motores": {}}
        self._keychain = {}
        self.socket = None
        # Cuenta personal: la del helper "del sistema" y la de ~/.config/gh.
        self._json(self.mock / "personal.json", {"usuario": "yo-personal", "token": "tok-personal"})
        self._json(self.home / ".config/gh/hosts.json", {"yo-personal": "tok-personal"})
        (self.home / ".gitconfig").write_text(
            "[user]\n\tname = Yo\n\temail = yo@personal.dev\n"
            f"[credential]\n\thelper = !{self.bin / 'mock-keychain-helper'}\n"
            "[include]\n\tpath = ~/.local/state/ws/gitconfig\n"
            "[init]\n\tdefaultBranch = main\n")
        for d in ("skills/mi-skill", "agents", "hooks"):
            (self.home / ".claude" / d).mkdir(parents=True)
        (self.home / ".claude/settings.json").write_text('{"model": "opus"}\n')

    # ─── Construcción ────────────────────────────────────────────────────────

    def _json(self, ruta, datos):
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(datos))

    def secreto(self, nombre, valor):
        self._keychain[f"ws/{nombre}"] = valor
        self._json(self.mock / "keychain.json", self._keychain)
        return self

    def cuenta_github(self, cuenta, usuario, token=None, navegador="incognito"):
        """Cuenta no personal. Con token = ya conectada (hosts en su GH_CONFIG_DIR)."""
        self.cfg["github"][cuenta] = {"usuario": usuario if token else "", "navegador": navegador}
        if token:
            self._json(self.home / f".local/state/ws/gh/{cuenta}/hosts.json", {usuario: token})
        return self

    def mcp(self, nombre, **datos):
        self.cfg["mcps"][nombre] = datos
        return self

    def bloque(self, nombre, **datos):
        self.cfg["bloques"][nombre] = datos
        return self

    def organizacion(self, clave, **datos):
        datos.setdefault("nombre", clave.capitalize())
        datos.setdefault("prefijo", clave[:2])
        datos.setdefault("raiz", str(self.home / "Orgs" / clave))
        self.cfg["organizaciones"][clave] = datos
        return self

    def entorno(self, clave, **datos):
        datos.setdefault("nombre", clave.capitalize())
        datos.setdefault("prefijo", clave[:3])
        self.cfg["entornos"][clave] = datos
        return self

    def proyecto(self, clave, ruta=None, git=True, remoto=None, **datos):
        """Proyecto con su carpeta (y repo git, con `remoto` si se da)."""
        grupo, _, nombre = clave.partition("/")
        if ruta is None:
            ruta = self.home / "src" / f"{grupo}-{nombre}"
        ruta = Path(ruta)
        ruta.mkdir(parents=True, exist_ok=True)
        if git:
            self.repo(ruta, remoto)
        self.cfg["proyectos"][clave] = {"ruta": str(ruta), **datos}
        return self

    def repo(self, ruta, remoto=None):
        ruta = Path(ruta)
        ruta.mkdir(parents=True, exist_ok=True)
        self.run(["git", "init", "-q"], cwd=ruta)
        if remoto:
            self.run(["git", "remote", "add", "origin", remoto], cwd=ruta)
        return ruta

    def escribir(self, extra=""):
        """Vuelca self.cfg a ws.toml (más texto crudo opcional)."""
        lineas = []
        for seccion in ("github", "organizaciones", "entornos", "mcps", "proyectos",
                        "agentes", "acciones", "motores"):
            for clave, datos in self.cfg[seccion].items():
                nombre = f'"{clave}"' if "/" in clave else clave
                lineas.append(f"[{seccion}.{nombre}]")
                lineas += [f"{k} = {toml(v)}" for k, v in datos.items()]
                lineas.append("")
        if self.cfg["bloques"]:
            lineas.append("[bloques]")
            lineas += [f"{k} = {toml(v)}" for k, v in self.cfg["bloques"].items()]
        self.config.parent.mkdir(parents=True, exist_ok=True)
        self.config.write_text("\n".join(lineas) + "\n" + extra)
        return self

    @property
    def config(self):
        return self.home / ".config/ws/ws.toml"

    def ruta(self, clave):
        return Path(self.cfg["proyectos"][clave]["ruta"])

    # ─── tmux ────────────────────────────────────────────────────────────────

    def socket_corto(self):
        """Los sockets de unix no admiten rutas de más de ~104 caracteres (macOS),
        y los TMPDIR de sandboxes como el de Nix son más largos."""
        ruta = self.dir / "tmux.sock"
        if len(str(ruta)) < 90:
            return str(ruta)
        self._dir_socket = Path(tempfile.mkdtemp(prefix="wst", dir="/tmp"))
        return str(self._dir_socket / "s")

    def tmux_iniciar(self):
        self.socket = self.socket_corto()
        subprocess.run(["tmux", "-S", self.socket, "-f", "/dev/null", "new-session", "-d",
                        "-s", "_base", "-x", "120", "-y", "40"], check=True, env=self.env())
        return self

    def tmux(self, *args):
        r = subprocess.run(["tmux", "-S", self.socket, *args], capture_output=True, text=True,
                           env=self.env())
        return r.stdout.strip()

    def sesion(self, nombre, cwd, marca=None):
        self.tmux("new-session", "-d", "-s", nombre, "-c", str(cwd))
        if marca:
            self.tmux("set", "-t", f"={nombre}:", "@ws", marca)
        return self.tmux("display", "-p", "-t", f"={nombre}:", "#{pane_id}")

    # ─── Ejecución ───────────────────────────────────────────────────────────

    def env(self, **extra):
        e = {
            "HOME": str(self.home), "USER": "prueba", "LANG": "C.UTF-8",
            # tmux abre cada pane con $SHELL; en sandboxes (Nix) vale /noshell
            # y las sesiones mueren al nacer, llevándose el servidor.
            "SHELL": "/bin/sh",
            "PATH": f"{self.home}/.local/share/ws/shims:{self.bin}:{os.environ.get('PATH', '')}",
            "WS_MOCK_DIR": str(self.mock), "WS_MOCK_LOG": str(self.log),
            "WS_BIN": str(self.bin / "ws"),
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0",
            "GIT_AUTHOR_DATE": "2026-01-01T00:00:00", "GIT_COMMITTER_DATE": "2026-01-01T00:00:00",
        }
        if self.socket:
            e["TMUX"] = f"{self.socket},0,0"
        e.update({k: str(v) for k, v in extra.items() if v is not None})
        return e

    def run(self, orden, cwd=None, entrada=None, **env):
        return subprocess.run(orden, cwd=cwd or self.home, input=entrada, capture_output=True,
                              text=True, env=self.env(**env), timeout=60)

    def ws(self, *args, cwd=None, entrada=None, **env):
        return self.run([sys.executable, str(WS_PY), *args], cwd=cwd, entrada=entrada, **env)

    def instalar_shims(self, *progs):
        d = self.home / ".local/share/ws/shims"
        d.mkdir(parents=True, exist_ok=True)
        for p in progs or ("claude", "gh", "opencode"):
            s = d / p
            s.write_text(f'#!/bin/sh\nexec "{self.bin / "ws"}" exec {p} "$@"\n')
            s.chmod(0o755)
        return self

    def llamadas(self, prog=None):
        if not self.log.exists():
            return []
        todas = [json.loads(l) for l in self.log.read_text().splitlines() if l]
        return [c for c in todas if prog is None or c["prog"] == prog]

    def ultima(self, prog):
        llamadas = self.llamadas(prog)
        assert llamadas, f"{prog} no fue llamado"
        return llamadas[-1]

    def credencial(self, cwd, url="https://github.com/alguien/repo"):
        r = self.run(["git", "credential", "fill"], cwd=cwd, entrada=f"url={url}\n\n")
        datos = dict(l.split("=", 1) for l in r.stdout.splitlines() if "=" in l)
        return r.returncode, datos, r.stderr

    def listas_fzf(self):
        """Argumentos de cada fzf abierto ahora mismo en este mundo."""
        res = []
        for f in self.mock.glob("fzf.*"):
            try:
                res.append(f.read_text())
            except OSError:
                pass
        return res

    def estado(self, *partes):
        return self.home.joinpath(".local/state/ws", *partes)

    def cerrar(self):
        if self.socket:
            subprocess.run(["tmux", "-S", self.socket, "kill-server"], capture_output=True)
        shutil.rmtree(self.dir, ignore_errors=True)
        if getattr(self, "_dir_socket", None):
            shutil.rmtree(self._dir_socket, ignore_errors=True)
