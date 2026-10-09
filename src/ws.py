#!/usr/bin/env python3
"""ws: organizaciones y espacios de trabajo transparentes.

No es un comando para el día a día: lo usan los shims (claude, opencode, gh),
direnv (`use ws`), git (includeIf generado) y el selector de tmux.

  ws exec <programa> [args…]   lanza el programa real con la config del contexto
  ws contexto [--json]         qué organización/proyecto aplica en $PWD
  ws direnv                    líneas para el `use ws` de direnvrc
  ws sync                      regenera todo lo derivado de ws.toml
  ws apply <sesión>            hook de tmux: marca la sesión con su contexto
  ws menu | ws nueva           UI de tmux (prefix+s / prefix+S), en ws_menu.py
  ws doctor                    comprueba dependencias e integración

Configuración: ~/.config/ws/ws.toml. Estado generado: ~/.local/state/ws/.
"""
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

HOME = Path.home()
CONFIG = Path(os.environ.get("WS_CONFIG", HOME / ".config/ws/ws.toml"))
ESTADO = HOME / ".local/state/ws"
SHIMS = HOME / ".local/share/ws/shims"
CLAUDE_PERSONAL = HOME / ".claude"
# nixpkgs que fijan los devShells generados. El módulo de home-manager lo pasa
# (WS_NIXPKGS) con el mismo commit que tu flake, para compartir store; si no,
# se usa [nix].nixpkgs de ws.toml o nixpkgs-unstable.
NIXPKGS_POR_DEFECTO = "github:NixOS/nixpkgs/nixpkgs-unstable"


# ─── Configuración ───────────────────────────────────────────────────────────

def expandir(ruta):
    return Path(os.path.expanduser(ruta)) if ruta else None


def cargar():
    if not CONFIG.exists():
        return {}
    with open(CONFIG, "rb") as f:
        return tomllib.load(f)


def grupos(cfg):
    """Organizaciones y entornos, con el tipo anotado."""
    salida = {}
    for tipo, seccion in (("organizacion", "organizaciones"), ("entorno", "entornos")):
        for clave, datos in cfg.get(seccion, {}).items():
            salida[clave] = {"clave": clave, "tipo": tipo, **datos}
    return salida


def proyectos(cfg):
    salida = {}
    for clave, datos in cfg.get("proyectos", {}).items():
        grupo, _, nombre = clave.partition("/")
        salida[clave] = {"clave": clave, "grupo": grupo, "nombre": nombre,
                         **datos, "ruta": expandir(datos.get("ruta"))}
    return salida


# ─── Contexto ────────────────────────────────────────────────────────────────

def _real(p):
    try:
        return Path(p).resolve()
    except OSError:
        return Path(p)


_PREFIJO_FLOTANTE = None


def prefijo_flotante():
    """Prefijo de las sesiones flotantes (@ws-float-prefix, por defecto "f-").
    Una flotante comparte organización con su sesión principal."""
    global _PREFIJO_FLOTANTE
    if _PREFIJO_FLOTANTE is None:
        r = subprocess.run(["tmux", "show", "-gqv", "@ws-float-prefix"], capture_output=True, text=True)
        _PREFIJO_FLOTANTE = r.stdout.strip() or "f-"
    return _PREFIJO_FLOTANTE


def sesion_base(sesion):
    pf = prefijo_flotante()
    return sesion[len(pf):] if sesion.startswith(pf) else sesion


def sesion_tmux():
    """Contexto marcado en la sesión de tmux del pane actual (@ws), o None."""
    pane = os.environ.get("TMUX_PANE")
    if not os.environ.get("TMUX") or not pane:
        return None
    r = subprocess.run(["tmux", "display", "-p", "-t", pane, "#{@ws}"],
                       capture_output=True, text=True)
    return r.stdout.strip() or None


def contexto(cfg, pwd=None, usar_tmux=True):
    """Devuelve {grupo, proyecto, origen} o None (Normal).

    Manda la carpeta: el proyecto con la ruta más larga que contiene a pwd.
    Después, la raíz de una organización/entorno. Por último, la sesión de tmux.
    """
    pwd = _real(pwd or os.getcwd())
    gs = grupos(cfg)
    candidatos = []
    for p in proyectos(cfg).values():
        if p["ruta"] and p["grupo"] in gs:
            candidatos.append((_real(p["ruta"]), p["grupo"], p["clave"]))
    for g in gs.values():
        if g.get("raiz"):
            candidatos.append((_real(expandir(g["raiz"])), g["clave"], None))
    mejor = None
    for ruta, grupo, proyecto in candidatos:
        if pwd == ruta or ruta in pwd.parents:
            peso = (len(ruta.parts), proyecto is not None)
            if mejor is None or peso > mejor[0]:
                mejor = (peso, grupo, proyecto)
    if mejor:
        return {"grupo": mejor[1], "proyecto": mejor[2], "origen": "carpeta"}
    # Fuera de cualquier carpeta conocida, la sesión de tmux aporta solo la
    # organización: las excepciones de un proyecto (p. ej. github/claude
    # "personal" en un repo propio) valen dentro de su carpeta, no fuera.
    marca = sesion_tmux() if usar_tmux else None
    if marca:
        grupo = marca.partition("/")[0]
        if grupo in gs:
            return {"grupo": grupo, "proyecto": None, "origen": "tmux"}
    return None


def efectiva(cfg, ctx):
    """Une los bloques del grupo y del proyecto, menos `quitar`."""
    g = grupos(cfg)[ctx["grupo"]]
    p = cfg.get("proyectos", {}).get(ctx["proyecto"] or "", {})
    nombres = list(dict.fromkeys(g.get("bloques", []) + p.get("bloques", [])))
    quitar = set(p.get("quitar", []))
    res = {"bloques": [], "mcps": [], "agentes": [], "herramientas": [],
           "permitir": [], "claude_motor": "anthropic", "hook_guardian": False, "env": {}}
    for n in nombres:
        if n in quitar:
            continue
        b = cfg.get("bloques", {}).get(n, {})
        res["bloques"].append(n)
        for k in ("mcps", "agentes", "herramientas", "permitir"):
            res[k] += [x for x in b.get(k, []) if x not in res[k]]
        res["claude_motor"] = b.get("claude_motor", res["claude_motor"])
        res["hook_guardian"] |= bool(b.get("hook_guardian"))
        res["env"].update(b.get("env", {}))
    for k in ("mcps", "agentes", "herramientas", "permitir"):
        res[k] = [x for x in res[k] if x not in quitar]
    # Variables propias: bloques < grupo < proyecto. Cualquier comando que pase
    # por ws las recibe (AWS_PROFILE, KUBECONFIG, NPM_CONFIG_USERCONFIG…).
    res["env"].update(g.get("env", {}))
    res["env"].update(p.get("env", {}))
    return res


def resolver_env(env):
    """Expande ${SECRETO} en los valores con el Llavero/libsecret/entorno."""
    salida = {}
    for k, v in env.items():
        v = os.path.expanduser(str(v))
        salida[k] = VAR.sub(lambda m: secreto(m.group(1)) or "", v)
    return salida


CREDENCIALES = ("github", "git_correo", "ssh_clave", "claude", "navegador")


def credenciales(cfg, grupo, proyecto=None):
    """Credenciales del grupo; un proyecto puede sobrescribir cualquiera
    (p. ej. un repo personal dentro de una organización: github = "personal")."""
    g = grupos(cfg)[grupo]
    p = cfg.get("proyectos", {}).get(proyecto or "", {})
    c = {k: g.get(k) for k in CREDENCIALES}
    c["github"] = c["github"] or "personal"
    c["claude"] = c["claude"] or "personal"
    c.update({k: p[k] for k in CREDENCIALES if k in p})
    return c


def dir_estado(ctx):
    return ESTADO / "p" / ctx["grupo"] / (ctx["proyecto"] or "_").split("/")[-1]


# ─── Secretos (Llavero) ──────────────────────────────────────────────────────

VAR = re.compile(r"\$\{([A-Z0-9_]+)\}")


MACOS = sys.platform == "darwin"


def secreto(nombre):
    """Lee ws/<nombre> del Llavero de macOS o, en Linux, de libsecret
    (secret-tool, atributo service=ws/<nombre>); si no está, del entorno."""
    if MACOS:
        orden = ["security", "find-generic-password", "-s", f"ws/{nombre}", "-w"]
    else:
        orden = ["secret-tool", "lookup", "service", f"ws/{nombre}"]
    try:
        r = subprocess.run(orden, capture_output=True, text=True)
    except FileNotFoundError:
        return os.environ.get(nombre)
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else os.environ.get(nombre)


def variables_en(obj):
    return set(VAR.findall(json.dumps(obj)))


# ─── Navegador para logins (gh, claude) ──────────────────────────────────────

def perfil_chrome(nombre):
    estado = (HOME / "Library/Application Support/Google/Chrome/Local State" if MACOS
              else HOME / ".config/google-chrome/Local State")
    try:
        info = json.loads(estado.read_text())["profile"]["info_cache"]
    except (OSError, KeyError, ValueError):
        return None
    for directorio, datos in info.items():
        if datos.get("name") == nombre:
            return directorio
    return None


def script_navegador(modo):
    """Ejecutable que abre una URL en incógnito o en un perfil de Chrome.

    gh (GH_BROWSER) y claude (BROWSER) llaman a un programa con la URL como
    argumento; así el login de otra cuenta no toca tu sesión personal.
    """
    if not modo or modo == "normal":
        return None
    if modo == "incognito":
        extra = "--incognito"
    elif modo.startswith("chrome:"):
        directorio = perfil_chrome(modo.split(":", 1)[1]) or "Default"
        extra = f"--profile-directory='{directorio}'"
    elif modo == "firefox-private":
        extra = None
    else:
        return None
    if modo == "firefox-private":
        orden = 'open -na Firefox --args --private-window "$@"' if MACOS else 'exec firefox --private-window "$@"'
    elif MACOS:
        orden = f'exec open -na "Google Chrome" --args {extra} "$@"'
    else:
        chrome = next((b for b in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")
                       if shutil.which(b)), "google-chrome")
        orden = f'exec {chrome} {extra} "$@"'
    destino = ESTADO / "bin" / ("navegador-" + re.sub(r"[^a-zA-Z0-9]+", "-", modo))
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(f'#!/bin/sh\n{orden}\n')
    destino.chmod(0o755)
    return str(destino)


# ─── Generación ──────────────────────────────────────────────────────────────

def _escribir(ruta, contenido):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    texto = contenido if isinstance(contenido, str) else json.dumps(contenido, indent=2, ensure_ascii=False) + "\n"
    if not ruta.exists() or ruta.read_text() != texto:
        ruta.write_text(texto)


def _cmd(mcp):
    return [os.path.expanduser(x) for x in mcp["cmd"]]


def mcps_claude(cfg, nombres):
    salida = {}
    for n in nombres:
        m = cfg.get("mcps", {}).get(n)
        if not m:
            continue
        if "url" in m:
            salida[n] = {"type": "http", "url": m["url"], **({"headers": m["headers"]} if m.get("headers") else {})}
        else:
            c = _cmd(m)
            salida[n] = {"command": c[0], "args": c[1:], **({"env": m["env"]} if m.get("env") else {})}
    return {"mcpServers": salida}


def mcps_opencode(cfg, nombres):
    """Formato de opencode; ${VAR} pasa a {env:VAR}. Los MCPs globales de
    opencode que el proyecto no pide se desactivan."""
    a_oc = lambda o: json.loads(VAR.sub(r"{env:\1}", json.dumps(o)))
    salida = {}
    global_oc = HOME / ".config/opencode/opencode.json"
    try:
        for n in json.loads(global_oc.read_text()).get("mcp", {}):
            salida[n] = {"enabled": False}
    except (OSError, ValueError):
        pass
    for n in nombres:
        m = cfg.get("mcps", {}).get(n)
        if not m:
            continue
        if "url" in m:
            salida[n] = {"type": "remote", "url": m["url"], "enabled": True,
                         **({"headers": a_oc(m["headers"])} if m.get("headers") else {})}
        else:
            salida[n] = {"type": "local", "command": _cmd(m), "enabled": True,
                         **({"environment": a_oc(m["env"])} if m.get("env") else {})}
    return {"$schema": "https://opencode.ai/config.json", "mcp": salida}


# Órdenes con las que un agente podría sacar un token en claro. git sigue
# funcionando: su helper llama a gh por su cuenta, no a través de Bash.
DENY_SIEMPRE = ["Bash(security find-generic-password:*)", "Bash(security find-internet-password:*)",
                "Bash(security dump-keychain:*)", "Bash(gh auth token:*)", "Bash(gh auth status --show-token:*)"]


def reglas_deny(cfg, ctx):
    """Cada Claude no puede leer las credenciales ni el historial de los demás
    contextos. No es un sandbox (un `cat` por Bash sigue pudiendo), pero corta
    el caso realista: un agente que lee lo que no es suyo por accidente."""
    c = credenciales(cfg, ctx["grupo"], ctx["proyecto"]) if ctx else {"github": "personal", "claude": "personal"}
    claude_propio = ctx["grupo"] if ctx and c["claude"] == "propia" else None
    deny = list(DENY_SIEMPRE)
    for cuenta in cfg.get("github", {}):
        if cuenta not in ("personal", c["github"]):
            deny.append(f"Read(~/.local/state/ws/gh/{cuenta}/**)")
    if c["github"] != "personal":
        deny.append("Read(~/.config/gh/hosts.yml)")
    for g in grupos(cfg).values():
        if g.get("claude") == "propia" and g["clave"] != claude_propio:
            deny.append(f"Read(~/.local/state/ws/claude/{g['clave']}/**)")
    if claude_propio:
        deny += ["Read(~/.claude/projects/**)", "Read(~/.claude/history.jsonl)", "Read(~/.claude.json)"]
    return deny


def settings_claude(cfg, ctx, ef=None):
    s = {"permissions": {"deny": reglas_deny(cfg, ctx)}}
    if ef and ef["permitir"]:
        s["permissions"]["allow"] = ef["permitir"]
    return s


def flake(herramientas, cfg=None):
    nixpkgs = (os.environ.get("WS_NIXPKGS") or (cfg or {}).get("nix", {}).get("nixpkgs")
               or NIXPKGS_POR_DEFECTO)
    paquetes = " ".join(f"pkgs.{h}" for h in herramientas)
    return f"""# Generado por ws a partir de ws.toml. No editar.
# Todos los proyectos usan el mismo nixpkgs: comparten store.
{{
  inputs.nixpkgs.url = "{nixpkgs}";
  outputs = {{ nixpkgs, ... }}:
    let pkgs = import nixpkgs {{ system = "aarch64-darwin"; config.allowUnfree = true; }};
    in {{ devShells.aarch64-darwin.default = pkgs.mkShell {{ packages = [ {paquetes} ]; }}; }};
}}
"""


def preparar_proyecto(cfg, ctx):
    """Escribe en el directorio de estado todo lo que necesita el contexto."""
    ef = efectiva(cfg, ctx)
    d = dir_estado(ctx)
    _escribir(d / "mcp.json", mcps_claude(cfg, ef["mcps"]))
    _escribir(d / "opencode.json", mcps_opencode(cfg, ef["mcps"]))
    _escribir(d / "settings.json", settings_claude(cfg, ctx, ef))
    if ef["herramientas"]:
        _escribir(d / "flake" / "flake.nix", flake(ef["herramientas"], cfg))
    return ef, d


def preparar_claude(cfg, g):
    """Directorio de Claude de una organización con login propio.

    Comparte skills, agentes y hooks con tu Claude personal (enlaces), importa
    tu CLAUDE.md global y parte de tus settings sin permisos. El resto
    (.claude.json con el login, proyectos, sesiones, plugins) es suyo.
    """
    d = ESTADO / "claude" / g["clave"]
    d.mkdir(parents=True, exist_ok=True)
    for n in ("skills", "agents", "hooks"):
        enlace, destino = d / n, CLAUDE_PERSONAL / n
        if destino.exists() and not enlace.exists() and not enlace.is_symlink():
            enlace.symlink_to(destino)
    md = d / "CLAUDE.md"
    propio = CONFIG.parent / "orgs" / f"{g['clave']}.CLAUDE.md"  # junto a ws.toml
    if propio.exists():
        if not md.is_symlink():
            md.unlink(missing_ok=True)
            md.symlink_to(propio)
    elif not md.exists():
        md.write_text(f"@~/.claude/CLAUDE.md\n\n# {g.get('nombre', g['clave'])}\n")
    ajustes = d / "settings.json"
    if not ajustes.exists():
        try:
            base = json.loads((CLAUDE_PERSONAL / "settings.json").read_text())
        except (OSError, ValueError):
            base = {}
        base.pop("permissions", None)
        _escribir(ajustes, base)
    return d


def dir_gh(cuenta):
    return ESTADO / "gh" / cuenta


def binario_real(prog):
    for d in os.environ.get("PATH", "").split(os.pathsep):
        if not d or _real(d) == _real(SHIMS):
            continue
        c = Path(d) / prog
        if c.is_file() and os.access(c, os.X_OK):
            return str(c)
    return None


def gitconfig(cfg):
    """~/.local/state/ws/gitconfig: includeIf por carpeta (lo incluye ~/.gitconfig).

    Por organización: correo de commits, clave SSH y, si su cuenta de GitHub no
    es la personal, credenciales de github.com vía `gh` con su GH_CONFIG_DIR en
    lugar de osxkeychain. Funciona en cualquier terminal, sin direnv.
    """
    bloques = ["# Generado por ws a partir de ws.toml. No editar.\n"]

    def archivo_para(nombre, c):
        lineas = []
        if c.get("git_correo"):
            lineas += ["[user]", f"\temail = {c['git_correo']}"]
        if c.get("ssh_clave"):
            clave = os.path.expanduser(c["ssh_clave"])
            lineas += ["[core]", f"\tsshCommand = ssh -i {clave} -o IdentitiesOnly=yes"]
        if c["github"] != "personal":
            lineas += ['[credential "https://github.com"]', "\thelper =",
                       f'\thelper = "!{ws_bin()} git-credential {c["github"]}"']
        archivo = ESTADO / "git" / f"{nombre}.gitconfig"
        _escribir(archivo, "\n".join(lineas) + "\n")
        return archivo

    def incluir(ruta, archivo):
        for variante in sorted({str(ruta), str(_real(ruta))}):
            bloques.append(f'[includeIf "gitdir:{variante}/"]\n\tpath = {archivo}\n')

    # Primero las raíces y después los proyectos: si se solapan, gana el último.
    for g in grupos(cfg).values():
        if g.get("raiz"):
            incluir(expandir(g["raiz"]), archivo_para(g["clave"], credenciales(cfg, g["clave"])))
    for p in proyectos(cfg).values():
        if p["ruta"] and p["grupo"] in grupos(cfg):
            nombre = p["clave"].replace("/", "--")
            incluir(p["ruta"], archivo_para(nombre, credenciales(cfg, p["grupo"], p["clave"])))
    _escribir(ESTADO / "gitconfig", "\n".join(bloques))


def ws_bin():
    """Ruta estable de `ws` para el helper de git (que no siempre hereda el PATH)."""
    usuario = os.environ.get("USER", HOME.name)
    for c in (Path(f"/etc/profiles/per-user/{usuario}/bin/ws"), HOME / ".nix-profile/bin/ws",
              HOME / ".local/bin/ws"):
        if c.exists():
            return str(c)
    return f"{sys.executable} {Path(__file__).resolve()}"


def git_credential(cuenta, accion):
    """Helper de git para github.com con una cuenta concreta.

    No usa `gh auth git-credential`: con un GH_CONFIG_DIR vacío, gh cae al token
    por defecto del Llavero (tu cuenta personal) y el push saldría con ella.
    Aquí se pide el token de ese usuario exacto; si no está, git falla.
    """
    sys.stdin.read()
    if accion != "get":
        return
    usuario = cargar().get("github", {}).get(cuenta, {}).get("usuario")
    if not usuario:
        sys.exit(f"ws: la cuenta de GitHub «{cuenta}» no está conectada (prefix+s, ^g sobre la organización)")
    env = {**os.environ, "GH_CONFIG_DIR": str(dir_gh(cuenta))}
    r = subprocess.run([binario_real("gh") or "gh", "auth", "token", "--hostname", "github.com",
                        "--user", usuario], capture_output=True, text=True, env=env)
    if r.returncode != 0 or not r.stdout.strip():
        sys.exit(f"ws: no hay token de {usuario} para «{cuenta}» (prefix+s, ^g sobre la organización)")
    print(f"username={usuario}\npassword={r.stdout.strip()}")


def registrar_direnv(ruta):
    """`.envrc` de una línea para cargar las herramientas Nix, sin ensuciar el repo."""
    if not ruta or not ruta.is_dir():
        return
    envrc = ruta / ".envrc"
    if envrc.exists():
        if "use ws" not in envrc.read_text():
            print(f"ws: {envrc} ya existe y no carga `use ws`; añádelo a mano", file=sys.stderr)
        return
    envrc.write_text("use ws\n")
    exclude = ruta / ".git/info/exclude"
    if exclude.parent.is_dir():
        actual = exclude.read_text() if exclude.exists() else ""
        faltan = [x for x in (".envrc", ".direnv/") if x not in actual.split()]
        if faltan:
            exclude.write_text(actual.rstrip("\n") + ("\n" if actual else "") + "\n".join(faltan) + "\n")
    subprocess.run(["direnv", "allow", str(ruta)], capture_output=True)


# ─── Etiquetas de Finder ─────────────────────────────────────────────────────
# Cada organización/entorno marca sus carpetas con una etiqueta de color:
# se ve en Finder y se busca con Spotlight (tag:<Organización>). Configurable con
# `etiqueta` y `color` en el grupo; por defecto, su nombre y un color por orden.

COLORES = {"ninguno": 0, "gris": 1, "verde": 2, "morado": 3, "azul": 4,
           "amarillo": 5, "rojo": 6, "naranja": 7}
POR_DEFECTO = ["azul", "verde", "morado", "naranja", "amarillo", "rojo", "gris"]
ATRIBUTO = "com.apple.metadata:_kMDItemUserTags"


def etiquetas_de_grupos(cfg):
    res = {}
    for i, g in enumerate(grupos(cfg).values()):
        if g.get("etiqueta") is False:
            continue
        color = g.get("color", POR_DEFECTO[i % len(POR_DEFECTO)])
        res[g["clave"]] = (g.get("etiqueta") or g.get("nombre") or g["clave"], COLORES.get(color, 0))
    return res


def leer_etiquetas(ruta):
    import plistlib
    r = subprocess.run(["xattr", "-px", ATRIBUTO, str(ruta)], capture_output=True, text=True)
    if r.returncode != 0:
        return []
    try:
        return plistlib.loads(bytes.fromhex(r.stdout.replace(" ", "").replace("\n", "")))
    except Exception:
        return []


def etiquetar(ruta, etiqueta, gestionadas):
    """Pone la etiqueta del grupo y quita las de otros grupos; respeta las tuyas."""
    import plistlib
    if not ruta or not ruta.exists():
        return
    actuales = leer_etiquetas(ruta)
    nombres_ws = {n for n, _ in gestionadas}
    nuevas = [t for t in actuales if t.split("\n")[0] not in nombres_ws]
    nuevas.append(f"{etiqueta[0]}\n{etiqueta[1]}")
    if nuevas != actuales:
        datos = plistlib.dumps(nuevas, fmt=plistlib.FMT_BINARY).hex()
        subprocess.run(["xattr", "-wx", ATRIBUTO, datos, str(ruta)], capture_output=True)


def etiquetar_todo(cfg):
    if not MACOS:  # las etiquetas de Finder son cosa de macOS
        return
    marcas = etiquetas_de_grupos(cfg)
    gestionadas = list(marcas.values())
    for g in grupos(cfg).values():
        if g["clave"] in marcas and g.get("raiz"):
            etiquetar(expandir(g["raiz"]), marcas[g["clave"]], gestionadas)
    for pr in proyectos(cfg).values():
        if pr["grupo"] in marcas:
            etiquetar(pr["ruta"], marcas[pr["grupo"]], gestionadas)


# ─── Autodescubrimiento ──────────────────────────────────────────────────────
# Un repo cuyo remoto es de una org de GitHub listada en `github_orgs` de un
# grupo se registra solo como proyecto de ese grupo (al entrar en él con cd, al
# lanzar claude/gh dentro, o al abrir el selector de tmux).

def _git(ruta, *args):
    r = subprocess.run(["git", "-C", str(ruta), *args], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def dueno_remoto(ruta):
    url = _git(ruta, "remote", "get-url", "origin")
    m = re.search(r"github\.com[:/]+([^/]+)/", url)
    return m.group(1).lower() if m else None


def _toml_str(v):
    if isinstance(v, list):
        return "[" + ", ".join(_toml_str(x) for x in v) + "]"
    return '"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'


def registrar_proyecto(grupo, nombre, ruta, **extra):
    """Añade [proyectos."grupo/nombre"] al final de ws.toml. Devuelve la clave."""
    clave = f"{grupo}/{re.sub(r'[^a-z0-9]+', '-', nombre.lower()).strip('-')}"
    casa = str(HOME)
    ruta = str(ruta)
    datos = {"ruta": "~" + ruta[len(casa):] if ruta.startswith(casa) else ruta, **extra}
    lineas = [f'\n[proyectos."{clave}"]'] + [f"{k} = {_toml_str(v)}" for k, v in datos.items() if v not in (None, "", [])]
    with open(CONFIG, "a") as f:
        f.write("\n".join(lineas) + "\n")
    return clave


def descubrir(ruta, cfg=None):
    """Registra el repo de `ruta` si pertenece a una org conocida. Devuelve su
    clave de proyecto (nueva o existente) o None."""
    cfg = cfg or cargar()
    top = _git(ruta, "rev-parse", "--show-toplevel")
    if not top:
        return None
    ctx = contexto(cfg, top, usar_tmux=False)
    if ctx and ctx["proyecto"] and _real(proyectos(cfg)[ctx["proyecto"]]["ruta"]) == _real(top):
        return ctx["proyecto"]
    dueno = dueno_remoto(top)
    if not dueno:
        return None
    for g in grupos(cfg).values():
        if dueno in [o.lower() for o in g.get("github_orgs", [])]:
            clave = registrar_proyecto(g["clave"], Path(top).name, top)
            sync()
            return clave
    return None


def remarcar_sesion(sesion, clave):
    """Si la sesión ya es de ese grupo (o de un proyecto suyo), pasa a ser del proyecto."""
    actual = subprocess.run(["tmux", "show", "-t", f"={sesion}:", "-qv", "@ws"],
                            capture_output=True, text=True).stdout.strip()
    if actual and actual != clave and actual.split("/")[0] == clave.split("/")[0]:
        base = sesion_base(sesion)
        for s in (base, f"{prefijo_flotante()}{base}"):  # la flotante sigue a su sesión
            subprocess.run(["tmux", "set", "-t", f"={s}:", "@ws", clave], capture_output=True)


def sync(cfg=None):
    cfg = cfg or cargar()
    gitconfig(cfg)
    gs = grupos(cfg)
    for g in gs.values():
        if g.get("claude") == "propia":
            preparar_claude(cfg, g)
        preparar_proyecto(cfg, {"grupo": g["clave"], "proyecto": None})
    for p in proyectos(cfg).values():
        if p["grupo"] not in gs:
            continue
        ef, _ = preparar_proyecto(cfg, {"grupo": p["grupo"], "proyecto": p["clave"]})
        if ef["herramientas"]:
            registrar_direnv(p["ruta"])
    etiquetar_todo(cfg)
    sello = ESTADO / ".sync"
    sello.parent.mkdir(parents=True, exist_ok=True)
    sello.write_text(ws_bin())


def sync_si_hace_falta():
    """Regenera si cambió ws.toml, este script o la ruta de `ws` (tras un rebuild)."""
    sello = ESTADO / ".sync"
    fuentes = [CONFIG, Path(__file__)]
    if (not sello.exists() or sello.read_text() != ws_bin()
            or any(f.exists() and f.stat().st_mtime > sello.stat().st_mtime for f in fuentes)):
        sync()


# ─── Lanzar programas (shims) ────────────────────────────────────────────────

# Subcomandos de claude que no aceptan los flags de sesión.
SUBCOMANDOS_CLAUDE = {"mcp", "config", "update", "doctor", "install", "setup-token",
                      "plugin", "plugins", "auth", "migrate-installer", "agents"}


def ejecutar(prog, args):
    real = binario_real(prog)
    if not real:
        sys.exit(f"ws: no encuentro {prog} en el PATH")
    cfg = {}
    try:
        cfg = cargar()
        if descubrir(os.getcwd(), cfg):
            cfg = cargar()
        ctx = contexto(cfg)
    except Exception as e:  # una config rota nunca debe dejarte sin claude/gh
        print(f"ws: {CONFIG}: {e} — sigo en modo normal", file=sys.stderr)
        ctx = None
    if not ctx:
        # Normal: el claude de siempre, solo con las reglas deny hacia los demás contextos.
        if prog == "claude" and (not args or args[0] not in SUBCOMANDOS_CLAUDE):
            normal = ESTADO / "normal-settings.json"
            _escribir(normal, settings_claude(cfg, None))
            args = ["--settings", str(normal), *args]
        os.execv(real, [prog, *args])

    sync_si_hace_falta()
    g = grupos(cfg)[ctx["grupo"]]
    c = credenciales(cfg, ctx["grupo"], ctx["proyecto"])
    ef, d = preparar_proyecto(cfg, ctx)
    env = dict(os.environ)
    env["WS_CONTEXTO"] = ctx["proyecto"] or ctx["grupo"]
    cuenta = c["github"]

    if prog == "claude":
        if c["claude"] == "propia":
            env["CLAUDE_CONFIG_DIR"] = str(preparar_claude(cfg, g))
            nav = script_navegador(c["navegador"] or "incognito")
            if nav:
                env["BROWSER"] = nav
        for v in variables_en(mcps_claude(cfg, ef["mcps"])):
            if (s := secreto(v)):
                env[v] = s
        motor = cfg.get("motores", {}).get(ef["claude_motor"])
        if motor:
            env["ANTHROPIC_BASE_URL"] = motor["url"]
            env["ANTHROPIC_MODEL"] = env["ANTHROPIC_SMALL_FAST_MODEL"] = motor["modelo"]
            if (s := secreto(motor["token"])):
                env["ANTHROPIC_AUTH_TOKEN"] = s
        if not args or args[0] not in SUBCOMANDOS_CLAUDE:
            args = ["--mcp-config", str(d / "mcp.json"), "--strict-mcp-config",
                    "--settings", str(d / "settings.json"), *args]
    elif prog == "opencode":
        env["OPENCODE_CONFIG"] = str(d / "opencode.json")
        for v in variables_en(mcps_claude(cfg, ef["mcps"])):
            if (s := secreto(v)):
                env[v] = s

    if prog in ("gh", "claude", "opencode") and cuenta != "personal":
        env["GH_CONFIG_DIR"] = str(dir_gh(cuenta))
        nav = script_navegador(cfg.get("github", {}).get(cuenta, {}).get("navegador", "incognito"))
        if nav:
            env["GH_BROWSER"] = nav
    # Variables de la organización/proyecto: para cualquier programa con shim.
    env.update(resolver_env(ef["env"]))
    os.execve(real, [prog, *args], env)


def direnv():
    """Lo evalúa `use_ws` en direnvrc: herramientas Nix del proyecto."""
    cfg = cargar()
    print(f'watch_file "{CONFIG}"')
    ctx = contexto(cfg, usar_tmux=False)
    if not ctx:
        return
    sync_si_hace_falta()
    ef, d = preparar_proyecto(cfg, ctx)
    print(f'export WS_CONTEXTO="{ctx["proyecto"] or ctx["grupo"]}"')
    # En el shell solo las variables sin secretos; las que llevan ${…} las pone
    # el shim al lanzar el programa, para no dejar tokens en el entorno.
    for k, v in ef["env"].items():
        if not VAR.search(str(v)):
            print(f"export {k}={shlex.quote(os.path.expanduser(str(v)))}")
    if ef["herramientas"]:
        print(f'use flake "{d / "flake"}"')


def apply(sesion):
    """Hook session-created: marca @ws según la carpeta inicial de la sesión.

    La flotante f-<sesión> hereda la marca de su sesión principal.
    """
    base = sesion_base(sesion)
    r = subprocess.run(["tmux", "show", "-t", f"={base}:", "-qv", "@ws"], capture_output=True, text=True)
    marca = r.stdout.strip()
    if not marca:
        r = subprocess.run(["tmux", "display", "-p", "-t", f"={base}:", "#{pane_current_path}"],
                           capture_output=True, text=True)
        ctx = contexto(cargar(), r.stdout.strip() or None, usar_tmux=False)
        marca = (ctx["proyecto"] or ctx["grupo"]) if ctx else ""
    if marca:
        subprocess.run(["tmux", "set", "-t", f"={sesion}:", "@ws", marca])


# ─── Diagnóstico ─────────────────────────────────────────────────────────────

REQUISITOS = [  # (programa, versión mínima, obligatorio, para qué)
    ("tmux", (3, 3), True, "selector en popup"),
    ("fzf", (0, 62), True, "selector y asistente"),
    ("git", None, True, "identidad por carpeta"),
    ("gh", None, False, "cuentas de GitHub por organización"),
    ("direnv", None, False, "herramientas Nix por proyecto (con nix-direnv)"),
    ("nix", None, False, "herramientas Nix por proyecto"),
    ("security" if sys.platform == "darwin" else "secret-tool", None, False, "secretos (${NOMBRE})"),
]


def _version(prog):
    bandera = "-V" if prog == "tmux" else "--version"
    try:
        r = subprocess.run([prog, bandera], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    m = re.search(r"(\d+)\.(\d+)", r.stdout + r.stderr)
    return (int(m.group(1)), int(m.group(2))) if m else ()


def doctor():
    ok_, mal, opc = "\033[32m✓\033[0m", "\033[31m✗\033[0m", "\033[33m–\033[0m"
    fallos = 0
    v = sys.version_info
    print(f"{ok_ if v >= (3, 11) else mal} python {v.major}.{v.minor}  (≥ 3.11, tomllib)")
    fallos += v < (3, 11)
    for prog, minimo, obligatorio, uso in REQUISITOS:
        ruta = shutil.which(prog)
        if not ruta:
            print(f"{mal if obligatorio else opc} {prog}: no está  ({uso})")
            fallos += obligatorio
            continue
        ver = _version(prog) if minimo else None
        if minimo and ver and ver < minimo:
            print(f"{mal} {prog} {'.'.join(map(str, ver))}: hace falta ≥ {'.'.join(map(str, minimo))}  ({uso})")
            fallos += obligatorio
        else:
            extra = f" {'.'.join(map(str, ver))}" if ver else ""
            print(f"{ok_} {prog}{extra}")
    try:
        cfg = cargar()
        print(f"{ok_ if cfg else opc} config {CONFIG}" + ("" if cfg else "  (no existe: parte de examples/ws.toml)"))
    except Exception as e:
        print(f"{mal} config {CONFIG}: {e}")
        fallos += 1
    for prog in ("claude", "gh", "opencode"):
        primero = shutil.which(prog)
        if primero and _real(Path(primero).parent) == _real(SHIMS):
            print(f"{ok_} {prog} pasa por ws")
        elif (SHIMS / prog).exists():
            print(f"{opc} {prog}: el shim existe pero {SHIMS} no va primero en el PATH")
    gitcfg = subprocess.run(["git", "config", "--global", "--get-all", "include.path"],
                            capture_output=True, text=True).stdout
    print(f"{ok_ if 'state/ws/gitconfig' in gitcfg else opc} ~/.gitconfig incluye ~/.local/state/ws/gitconfig")
    return 1 if fallos else 0


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    orden, resto = sys.argv[1], sys.argv[2:]
    if orden == "exec" and resto:
        ejecutar(resto[0], resto[1:])
    elif orden == "contexto":
        cfg = cargar()
        ctx = contexto(cfg)
        if "--json" in resto:
            print(json.dumps({**(ctx or {}), **({"efectiva": efectiva(cfg, ctx)} if ctx else {})}))
        else:
            print((ctx["proyecto"] or ctx["grupo"]) if ctx else "normal")
    elif orden == "direnv":
        direnv()
    elif orden == "sync":
        sync()
    elif orden == "doctor":
        sys.exit(doctor())
    elif orden == "descubrir":
        clave = descubrir(resto[0] if resto else os.getcwd())
        if clave and os.environ.get("TMUX_PANE"):
            sesion = subprocess.run(["tmux", "display", "-p", "-t", os.environ["TMUX_PANE"], "#{session_name}"],
                                    capture_output=True, text=True).stdout.strip()
            remarcar_sesion(sesion, clave)
        if clave:
            print(clave)
    elif orden == "git-credential" and len(resto) == 2:
        git_credential(*resto)
    elif orden == "apply" and resto:
        apply(resto[0])
    elif orden in ("menu", "nueva", "preview", "accion"):
        import ws_menu
        ws_menu.main(orden, resto)
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
