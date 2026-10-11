"""UI de tmux para ws: selector de sesiones (prefix+s) y asistente (prefix+S).

Corre dentro de un `display-popup -E`; usa fzf para elegir e input() para
escribir. Todo lo que crea lo añade al final de ~/.config/ws/ws.toml.
"""
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

import ws

import tema as _tema
from i18n import idioma, t

# Tema definido en tmux.conf (@ws-color-*, @ws-nerd-font…; ver tema.py).
TEMA = _tema.Tema()
ACENTO, ACTIVO, SECUNDARIO = TEMA.ACENTO, TEMA.ACTIVO, TEMA.SECUNDARIO
TENUE, INFO, TEXTO = TEMA.TENUE, TEMA.INFO, TEMA.TEXTO
NEGRITA, FIN = "\033[1m", "\033[0m"

# Opciones propias, sin heredar FZF_DEFAULT_OPTS (su --height o su fondo
# romperían el popup). Pantalla completa y fondo del terminal (-1). Sin
# buscador visible: se navega con j/k o las flechas y "/" abre la búsqueda.
FZF = ["fzf", "--ansi", "--layout=reverse", "--no-sort", "--cycle", "--info=hidden",
       "--no-input", "--border=none", "--no-separator", "--highlight-line",
       "--padding=1,2,0,1", f"--prompt={TEMA.iconos['search']}  ", f"--ghost={t('search')}",
       f"--pointer={TEMA.o['pointer']}", "--marker=✓", f"--color={TEMA.fzf()}",
       "--bind", "/:show-input+unbind(j,k,q)",
       "--bind", "esc:transform:[[ $FZF_INPUT_STATE = enabled ]] && echo 'clear-query+hide-input+rebind(j,k,q)' || echo abort",
       "--bind", "j:down,k:up,q:abort"]
ENV_FZF = {**os.environ, "FZF_DEFAULT_OPTS": ""}
VISTA = TEMA.o["preview"]


def atajos(*pares):
    """Pie con los atajos: tecla en el color de acento, acción en el secundario."""
    return "  ".join(f"{ACENTO}{t}{FIN} {SECUNDARIO}{a}{FIN}" for t, a in pares)


# ─── tmux ────────────────────────────────────────────────────────────────────

def tmux(*args, salida=False):
    r = subprocess.run(["tmux", *args], capture_output=True, text=True)
    return r.stdout.strip() if salida else r.returncode == 0


def sesiones():
    """{nombre: marca @ws} de las sesiones abiertas, sin las flotantes f-*."""
    fmt = "#{session_name}\t#{@ws}"
    res = {}
    for linea in tmux("list-sessions", "-F", fmt, salida=True).splitlines():
        nombre, _, marca = linea.partition("\t")
        if not nombre.startswith(ws.prefijo_flotante()):
            res[nombre] = marca
    return res


def sesion_de_proyecto(cfg, clave, abiertas=None):
    """La sesión abierta marcada con ese proyecto o, si no hay, su nombre estándar."""
    abiertas = sesiones() if abiertas is None else abiertas
    estandar = nombre_sesion(cfg, clave)
    if estandar in abiertas:
        return estandar
    for nombre, marca in abiertas.items():
        if marca == clave:
            return nombre
    return estandar


def nombre_sesion(cfg, clave_proyecto):
    grupo, _, nombre = clave_proyecto.partition("/")
    prefijo = ws.grupos(cfg)[grupo].get("prefijo", grupo)
    return f"{prefijo}-{nombre}"


# Lo pasa ws-selector.sh: cliente principal, sesión de origen y si se abrió
# desde una flotante (que se cerró sola para mostrar el selector).
CLIENTE = os.environ.get("WS_CLIENTE", "")
ORIGEN = os.environ.get("WS_ORIGEN", "")
DESDE_FLOTANTE = os.environ.get("WS_DESDE_FLOTANTE") == "1"
SALTO = False
# Integración opcional con ventanas flotantes: un script que abre la flotante
# de una sesión (`<script> <sesión> <cliente>`), configurado en tmux con
# `set -g @ws-float-script …`. Sin él, ws no cierra ni reabre flotantes.
FLOAT_OPEN = None


def float_script():
    global FLOAT_OPEN
    if FLOAT_OPEN is None:
        FLOAT_OPEN = os.path.expanduser(tmux("show", "-gqv", "@ws-float-script", salida=True))
    return FLOAT_OPEN


def reabrir_flotante(sesion):
    """Vuelve a abrir la flotante de `sesion` en cuanto se cierre este popup
    (un cliente no puede tener dos popups a la vez)."""
    if not float_script():
        return
    cliente = CLIENTE or tmux("display", "-p", "#{client_name}", salida=True)
    tmux("run-shell", "-b", f"sleep 0.2; {shlex.quote(float_script())} "
         f"{shlex.quote(sesion)} {shlex.quote(cliente)}")


def saltar(sesion):
    global SALTO
    SALTO = True
    if not os.environ.get("TMUX"):
        os.execvp("tmux", ["tmux", "attach", "-t", f"={sesion}"])
    tmux("switch-client", *(["-c", CLIENTE] if CLIENTE else []), "-t", f"={sesion}")
    if tmux("show", "-t", f"={sesion}:", "-qv", "@float_abierta", salida=True) == "1":
        reabrir_flotante(sesion)


def abrir(cfg, grupo, proyecto=None, nombre=None, ruta=None):
    """Abre (o crea) la sesión de un proyecto o de un grupo y salta a ella.

    Ventana 1: shell. Una ventana más por agente, con el comando escrito y sin
    Enter: el agente no gasta RAM hasta que tú lo lanzas.
    """
    if proyecto:
        nombre = sesion_de_proyecto(cfg, proyecto)
        ruta = ws.proyectos(cfg)[proyecto]["ruta"]
    ruta = Path(ruta or ws.expandir(ws.grupos(cfg)[grupo].get("raiz")) or Path.home())
    ruta.mkdir(parents=True, exist_ok=True)
    if not tmux("has-session", "-t", f"={nombre}"):
        tmux("new-session", "-d", "-s", nombre, "-c", str(ruta))
        tmux("set", "-t", f"={nombre}:", "@ws", proyecto or grupo)
        ef = ws.efectiva(cfg, {"grupo": grupo, "proyecto": proyecto})
        for agente in ef["agentes"]:
            # [agentes.<nombre>] cmd = "…" en ws.toml; si no, el propio nombre.
            orden = cfg.get("agentes", {}).get(agente, {}).get("cmd", agente)
            tmux("new-window", "-d", "-t", f"={nombre}:", "-n", agente, "-c", str(ruta))
            tmux("send-keys", "-t", f"={nombre}:{agente}", orden)
    saltar(nombre)


# ─── fzf / entrada ───────────────────────────────────────────────────────────

def elegir(opciones, cabecera="", multi=False, preview=None, teclas=None, binds=None, pie=None):
    """opciones: [(clave, texto)]. Devuelve (tecla, [claves]) o (None, [])."""
    if not opciones:
        return None, []
    args = FZF + ["--delimiter=\t", "--with-nth=2.."]
    if cabecera:
        args += ["--header", cabecera, "--header-first"]
    if pie is None:
        pie = atajos(("enter", t("k_choose")), ("tab", t("k_mark")), ("/", t("k_search")), ("esc", t("k_back"))) if multi \
            else atajos(("enter", t("k_choose")), ("/", t("k_search")), ("esc", t("k_back")))
    args += ["--footer", pie]
    if multi:
        args += ["--multi", "--bind", "tab:toggle+down"]
    if preview:
        args += ["--preview", preview, "--preview-window", VISTA]
    if teclas:
        args += ["--expect", ",".join(teclas)]
    for b in binds or []:
        args += ["--bind", b]
    entrada = "\n".join(f"{k}\t{t}" for k, t in opciones)
    r = subprocess.run(args, input=entrada, stdout=subprocess.PIPE, text=True, env=ENV_FZF)
    if r.returncode not in (0, 1) or not r.stdout:
        return None, []
    lineas = r.stdout.splitlines()
    tecla = lineas.pop(0) if teclas else ""
    return tecla, [l.split("\t", 1)[0] for l in lineas if l]


def limpiar(titulo=None):
    """Pantalla limpia antes de cada pregunta: nada se apila en el popup."""
    sys.stdout.write("\033[2J\033[3J\033[H")
    if titulo:
        sys.stdout.write(f"\n {ACENTO}{NEGRITA}{titulo}{FIN}\n\n")
    sys.stdout.flush()


def confirmar(texto):
    """Sí/No con «Sí» primero (Enter confirma) y respuesta de una tecla:
    y/n en inglés, s/n en español. Esc o q cancelan."""
    si, no = t("yes_key"), t("no_key")
    pregunta = texto[0].upper() + texto[1:] + "?"
    if idioma() == "es":
        pregunta = "¿" + pregunta
    tecla, sel = elegir([("si", f"{t('yes')}, {texto}"), ("no", t("no"))], pregunta,
                        teclas=[si, no],
                        pie=atajos((si, t("k_yes")), (no, t("k_no")), ("enter", t("k_choose")),
                                   ("esc", t("k_back"))))
    if tecla == si:
        return True
    if tecla == no:
        return False
    return sel == ["si"]


def preguntar(texto, defecto=""):
    try:
        v = input(f"  {ACENTO}{texto}{FIN}" + (f" {SECUNDARIO}[{defecto}]{FIN}" if defecto else "") + ": ").strip()
    except EOFError:
        sys.exit(0)
    return v or defecto


def slug(texto):
    return re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-")


# ─── Edición de ws.toml ──────────────────────────────────────────────────────

def toml_str(v):
    if isinstance(v, list):
        return "[" + ", ".join(toml_str(x) for x in v) + "]"
    return '"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'


def anadir_seccion(cabecera, datos):
    with ws.cerrojo():
        _anadir_seccion(cabecera, datos)


def _anadir_seccion(cabecera, datos):
    lineas = [f"\n[{cabecera}]"] + [f"{k} = {toml_str(v)}" for k, v in datos.items() if v not in (None, "", [])]
    with open(ws.CONFIG, "a") as f:
        f.write("\n".join(lineas) + "\n")


def poner_campo(cabecera, campo, valor):
    """Fija campo = valor dentro de [cabecera], conservando el resto del archivo."""
    with ws.cerrojo():
        _poner_campo(cabecera, campo, valor)


def _poner_campo(cabecera, campo, valor):
    texto = ws.CONFIG.read_text()
    m = re.search(rf"^\[{re.escape(cabecera)}\]\s*$", texto, re.M)
    if not m:
        _anadir_seccion(cabecera, {campo: valor})
        return
    fin = re.search(r"^\[", texto[m.end():], re.M)
    fin = m.end() + fin.start() if fin else len(texto)
    seccion = texto[m.end():fin]
    linea = f"{campo} = {toml_str(valor)}"
    patron = rf"^{re.escape(campo)}\s*=.*$"
    if re.search(patron, seccion, re.M):
        seccion = re.sub(patron, lambda _: linea, seccion, count=1, flags=re.M)
    else:
        seccion = "\n" + linea + seccion
    ws._escribir(ws.CONFIG, texto[:m.end()] + seccion + texto[fin:])


# ─── Cuentas ─────────────────────────────────────────────────────────────────

def conectar_github(cuenta):
    """Login web de gh para una cuenta que no es la personal.

    La página se abre con el navegador de la cuenta ([navegadores], o el
    "defecto"), así que tu sesión personal no interviene. El token se guarda en
    el hosts.yml de su GH_CONFIG_DIR (--insecure-storage, chmod 600): en el
    Llavero compartiría la entrada por defecto con tu cuenta personal.
    """
    cfg = ws.cargar()
    datos = cfg.get("github", {}).get(cuenta, {})
    d = ws.dir_gh(cuenta)
    d.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "GH_CONFIG_DIR": str(d)}
    nav = ws.script_navegador(cfg, datos.get("navegador"))
    if nav:
        env["GH_BROWSER"] = nav
    gh = ws.binario_real("gh") or "gh"
    limpiar(t("connect_title", c=cuenta))
    print(f"  {t('connect_1')}")
    print(f"  {SECUNDARIO}{t('connect_2')}{FIN}\n")
    r = subprocess.run([gh, "auth", "login", "--web", "--hostname", "github.com",
                        "--git-protocol", "https", "--insecure-storage", "--skip-ssh-key"], env=env)
    if r.returncode != 0:
        input(f"\n{t('login_failed')}")
        return None
    usuario = subprocess.run([gh, "api", "user", "-q", ".login"], env=env,
                             capture_output=True, text=True).stdout.strip()
    if usuario:
        poner_campo(f"github.{cuenta}", "usuario", usuario)
        ws.sync()
        print(f"\n{ACTIVO}{t('connected_as', c=cuenta, u=usuario)}{FIN}")
    return usuario


def comprobar_github(cfg, grupo):
    cuenta = ws.credenciales(cfg, grupo)["github"]
    if cuenta != "personal" and not cfg.get("github", {}).get(cuenta, {}).get("usuario"):
        if confirmar(t("connect_now", c=cuenta)):
            limpiar()
            conectar_github(cuenta)


# ─── Selector: prefix+s ──────────────────────────────────────────────────────



def icono(tipo):
    clave = {"normal": "normal", "organizacion": "organization", "entorno": "environment"}[tipo]
    i = TEMA.iconos[clave]
    return f"{i}  " if i else ""


def lineas_menu(cfg):
    """Filas del selector. Las cabeceras de grupo también se eligen: Enter en
    una cabecera crea una sesión nueva en ese grupo (o una normal)."""
    abiertas = sesiones()
    actual = ws.sesion_base(ORIGEN)
    gs = ws.grupos(cfg)
    ps = ws.proyectos(cfg)
    usadas = set()
    filas = []

    def item(sesion, nombre, extra=""):
        if sesion == actual:
            punto = f"{ACENTO}●{FIN}"
        elif sesion in abiertas:
            punto = f"{ACTIVO}●{FIN}"
        else:
            punto = f"{TENUE}○{FIN}"
        return f"   {punto} {TEXTO}{nombre}{FIN}{extra}"

    def cabecera(tipo, nombre, info=""):
        return f"{ACENTO}{NEGRITA}{icono(tipo)}{nombre}{FIN}" + (f"   {TENUE}{info}{FIN}" if info else "")

    filas.append(("h:normal", cabecera("normal", t("normal"))))
    for s, marca in abiertas.items():
        if not marca or marca.split("/")[0] not in gs:
            filas.append((f"s:{s}", item(s, s)))
            usadas.add(s)

    for g in gs.values():
        c = ws.credenciales(cfg, g["clave"])
        cuenta = c["github"]
        usuario = t("personal") if cuenta == "personal" else \
            (cfg.get("github", {}).get(cuenta, {}).get("usuario") or t("not_connected"))
        claude = t("own") if c["claude"] == "propia" else t("personal")
        info = f"{TEMA.iconos['github']} {usuario}  ·  claude {claude}"
        filas.append((f"g:{g['clave']}", cabecera(g["tipo"], g.get("nombre", g["clave"]), info)))
        for p in ps.values():
            if p["grupo"] != g["clave"]:
                continue
            s = sesion_de_proyecto(cfg, p["clave"], abiertas)
            ef = ws.efectiva(cfg, {"grupo": g["clave"], "proyecto": p["clave"]})
            extra = ""
            if s in abiertas and s != nombre_sesion(cfg, p["clave"]):
                extra += f"  {TENUE}{s}{FIN}"
            if ef["herramientas"]:
                extra += f"  {INFO}❄ {' '.join(ef['herramientas'])}{FIN}"
            filas.append((f"p:{p['clave']}", item(s, p["nombre"], extra)))
            usadas.add(s)
        for s, marca in abiertas.items():
            if s not in usadas and marca.split("/")[0] == g["clave"]:
                filas.append((f"s:{s}", item(s, s)))
                usadas.add(s)
    return filas


def _dato(etiqueta, valor):
    print(f"  {SECUNDARIO}{etiqueta:<13}{FIN}{TEXTO}{valor}{FIN}")


def preview(clave):
    cfg = ws.cargar()
    tipo, _, valor = clave.partition(":")
    sesion = valor if tipo == "s" else sesion_de_proyecto(cfg, valor) if tipo == "p" else None
    if sesion and tmux("has-session", "-t", f"={sesion}"):
        marca = tmux("show", "-t", f"={sesion}:", "-qv", "@ws", salida=True)
        ventanas = []
        for v in tmux("list-windows", "-t", f"={sesion}", "-F",
                      "#{window_active}\t#{window_name}", salida=True).splitlines():
            activa, _, nombre = v.partition("\t")
            ventanas.append(f"{TEXTO}{nombre}{FIN}" if activa == "1" else f"{TENUE}{nombre}{FIN}")
        print(f" {ACENTO}{NEGRITA}{sesion}{FIN}" + (f"   {SECUNDARIO}{marca}{FIN}" if marca else ""))
        print(f" {TENUE}▐{FIN} " + f" {TENUE}·{FIN} ".join(ventanas) + "\n")
        print(tmux("capture-pane", "-ep", "-t", f"={sesion}:", salida=True))
        return
    if tipo == "h":
        print(f"\n {ACENTO}{NEGRITA}{t('p_normal_title')}{FIN}\n")
        print(f"  {TEXTO}{t('p_normal_text')}{FIN}")
        print(f"\n  {SECUNDARIO}enter{FIN} {TEXTO}{t('p_normal_enter')}{FIN}")
        return
    if tipo in ("p", "g"):
        grupo = valor.split("/")[0]
        proyecto = valor if tipo == "p" else None
        ef = ws.efectiva(cfg, {"grupo": grupo, "proyecto": proyecto})
        c = ws.credenciales(cfg, grupo, proyecto)
        g = ws.grupos(cfg)[grupo]
        titulo = ws.proyectos(cfg)[valor]["nombre"] if proyecto else g.get("nombre", grupo)
        print(f"\n {ACENTO}{NEGRITA}{titulo}{FIN}" + (f"   {SECUNDARIO}{g.get('nombre', grupo)}{FIN}" if proyecto else "") + "\n")
        if proyecto:
            ruta = str(ws.proyectos(cfg)[valor]["ruta"]).replace(str(Path.home()), "~", 1)
            _dato(t("p_folder"), ruta)
        claude = t("own") if c["claude"] == "propia" else t("personal")
        _dato(t("p_github"), t("personal") if c["github"] == "personal" else c["github"])
        _dato(t("p_claude"), claude + (f" · {ef['claude_motor']}" if ef["claude_motor"] != "anthropic" else ""))
        _dato(t("p_email"), c["git_correo"] or t("p_same_email"))
        print()
        _dato(t("p_blocks"), ", ".join(ef["bloques"]) or "—")
        _dato(t("p_mcps"), ", ".join(ef["mcps"]) or "—")
        _dato(t("p_agents"), ", ".join(ef["agentes"]) or "—")
        _dato(t("p_tools"), ", ".join(ef["herramientas"]) or t("p_host_tools"))
        accion = t("p_open") if proyecto else t("p_new_here")
        print(f"\n  {SECUNDARIO}enter{FIN} {TEXTO}{accion}{FIN}" + ("" if proyecto else f"   {SECUNDARIO}^g{FIN} {TEXTO}{t('p_connect')}{FIN}"))


def _yo():
    return f"{shlex.quote(sys.executable)} {shlex.quote(str(Path(__file__).resolve().parent / 'ws.py'))}"


def _sesion_de(cfg, clave):
    tipo, _, valor = clave.partition(":")
    if tipo == "s":
        return valor
    if tipo == "p":
        return sesion_de_proyecto(cfg, valor)
    return None


def accion_propia(cfg, clave, nombre):
    """Ejecuta [acciones.<nombre>].cmd con el contexto de la fila en variables:
    WS_GRUPO, WS_PROYECTO, WS_SESION, WS_RUTA. Punto de extensión para otros
    plugins o scripts (lazygit, un deploy, abrir el repo en el navegador…)."""
    a = cfg.get("acciones", {}).get(nombre)
    if not a:
        return
    tipo, _, valor = clave.partition(":")
    grupo = valor.split("/")[0] if tipo in ("g", "p") else ""
    proyecto = valor if tipo == "p" else ""
    sesion = _sesion_de(cfg, clave) or ""
    ruta = ""
    if proyecto:
        ruta = str(ws.proyectos(cfg)[proyecto]["ruta"])
    elif sesion and tmux("has-session", "-t", f"={sesion}"):
        ruta = tmux("display", "-p", "-t", f"={sesion}:", "#{pane_current_path}", salida=True)
    env = {**os.environ, "WS_GRUPO": grupo, "WS_PROYECTO": proyecto, "WS_SESION": sesion, "WS_RUTA": ruta}
    limpiar()
    subprocess.run(a["cmd"], shell=True, env=env, cwd=ruta or None)
    if a.get("pausa", False):
        input(f"\n  {SECUNDARIO}{t('enter_back')}{FIN}")


def accion(nombre, clave="", extra=""):
    """Acciones que corren DENTRO de fzf (execute + reload): no se apila nada."""
    cfg = ws.cargar()
    tipo, _, valor = clave.partition(":")
    sesion = _sesion_de(cfg, clave)
    if nombre == "lineas":
        print("\n".join(f"{k}\t{t}" for k, t in lineas_menu(cfg)))
    elif nombre == "propia":
        accion_propia(cfg, clave, extra)
    elif nombre == "cerrar" and sesion and tmux("has-session", "-t", f"={sesion}"):
        if confirmar(t("close_session", s=sesion)):
            tmux("kill-session", "-t", f"={sesion}")
    elif nombre == "renombrar" and sesion and tmux("has-session", "-t", f"={sesion}"):
        limpiar(t("rename", s=sesion))
        nuevo = preguntar(t("new_name"), sesion)
        if nuevo and nuevo != sesion:
            tmux("rename-session", "-t", f"={sesion}", nuevo)
    elif nombre == "editar":
        subprocess.run([os.environ.get("EDITOR", "nvim"), str(ws.CONFIG)])
        ws.sync()
    elif nombre == "github" and tipo in ("g", "p"):
        cuenta = ws.credenciales(cfg, valor.split("/")[0])["github"]
        limpiar()
        if cuenta == "personal":
            input(f"  {SECUNDARIO}{t('uses_personal_gh')}{FIN}")
        else:
            conectar_github(cuenta)
            input(f"\n  {SECUNDARIO}{t('enter_back')}{FIN}")


def descubrir_sesiones():
    """Registra los repos de orgs conocidas abiertos en cualquier pane y pasa
    cada sesión al proyecto donde está su pane activo (si es del mismo grupo)."""
    cfg = ws.cargar()
    rutas = {}
    salida = tmux("list-panes", "-a", "-F", "#{session_name}\t#{pane_current_path}\t#{pane_active}#{window_active}", salida=True)
    for linea in salida.splitlines():
        sesion, ruta, activo = (linea.split("\t") + ["", ""])[:3]
        if sesion.startswith(ws.prefijo_flotante()) or not ruta:
            continue
        clave = ws.descubrir(ruta, cfg)
        if clave:
            cfg = ws.cargar()
            if activo == "11":
                ws.remarcar_sesion(sesion, clave)


def menu():
    ws.sync_si_hace_falta()
    descubrir_sesiones()
    cfg = ws.cargar()
    yo = _yo()
    recargar = f"reload({yo} accion lineas)"
    # Acciones propias: [acciones.<nombre>] tecla = "ctrl-o", cmd = "…", etiqueta = "…"
    propias = [(n, a) for n, a in cfg.get("acciones", {}).items() if a.get("tecla") and a.get("cmd")]
    tecla, claves = elegir(
        lineas_menu(cfg),
        pie=atajos(("enter", t("k_open")), ("^n", t("k_new")), ("^x", t("k_close")), ("^r", t("k_rename")),
                   ("^e", t("k_edit")), ("^g", t("k_github")),
                   *[(a["tecla"].replace("ctrl-", "^"), a.get("etiqueta", n)) for n, a in propias],
                   ("/", t("k_search"))),
        preview=f"{yo} preview {{1}}",
        teclas=["ctrl-n"],
        binds=[f"ctrl-x:execute({yo} accion cerrar {{1}})+{recargar}",
               f"ctrl-r:execute({yo} accion renombrar {{1}})+{recargar}",
               f"ctrl-e:execute({yo} accion editar)+{recargar}",
               f"ctrl-g:execute({yo} accion github {{1}})+{recargar}",
               *[f"{a['tecla']}:execute({yo} accion propia {{1}} {shlex.quote(n)})+{recargar}"
                 for n, a in propias]])
    if tecla is None:
        return
    clave = claves[0] if claves else "h:normal"
    tipo, _, valor = clave.partition(":")
    if tecla == "ctrl-n" or tipo == "n":
        nueva()
    elif tipo == "s":
        saltar(valor)
    elif tipo == "p":
        abrir(cfg, valor.split("/")[0], valor)
    elif tipo == "g":
        nueva(grupo=valor)
    elif tipo == "h":
        nueva(normal=True)


# ─── Asistente: prefix+S ─────────────────────────────────────────────────────

CWD = Path.home()


def describir_bloque(b):
    partes = []
    for k, etiqueta in (("mcps", t("blocks_mcps")), ("agentes", t("blocks_agents")),
                        ("herramientas", t("tools_lbl")), ("permitir", t("blocks_perms"))):
        if b.get(k):
            partes.append(f"{etiqueta}: {' '.join(b[k])}")
    if b.get("claude_motor"):
        partes.append(t("claude_with", m=b["claude_motor"]))
    return " · ".join(partes)


def elegir_bloques(cfg, excluir=(), cabecera=None):
    cabecera = cabecera or t("blocks")
    ops = [(n, f"{n:<11} {SECUNDARIO}{describir_bloque(b)}{FIN}")
           for n, b in cfg.get("bloques", {}).items() if n not in excluir]
    _, sel = elegir(ops, cabecera, multi=True)
    # Un bloque que cambia el motor de Claude (p. ej. minimax) sustituye tu login:
    # se confirma aparte para que no se cuele entre los marcados.
    for n in list(sel):
        motor = cfg.get("bloques", {}).get(n, {}).get("claude_motor")
        if motor and motor != "anthropic" and not confirmar(t("confirm_engine", m=motor)):
            sel.remove(n)
    return sel


def crear_grupo(tipo):
    cfg = ws.cargar()
    titulo = t("new_org") if tipo == "organizacion" else t("new_env")
    limpiar(titulo)
    nombre = preguntar(t("name"))
    if not nombre:
        return None
    clave = slug(nombre)
    datos = {"nombre": nombre, "prefijo": preguntar(t("prefix"), clave[:2]),
             "raiz": preguntar(t("root"), f"~/Orgs/{nombre}")}
    cuenta_nueva = None
    if tipo == "organizacion":
        ops = [("personal", t("gh_personal"))]
        ops += [(c, t("gh_account", c=c, u=d.get("usuario") or t("not_connected")))
                for c, d in cfg.get("github", {}).items() if c != "personal"]
        ops += [("+", t("gh_other"))]
        _, sel = elegir(ops, t("gh_of", n=nombre))
        datos["github"] = sel[0] if sel else "personal"
        if datos["github"] == "+":
            datos["github"] = cuenta_nueva = clave
        _, sel = elegir([("personal", t("claude_mine")), ("propia", t("claude_org"))],
                        t("claude_in", n=nombre))
        datos["claude"] = sel[0] if sel else "personal"
        limpiar(f"{titulo}: {nombre}")
        datos["git_correo"] = preguntar(t("commit_email"))
    datos["bloques"] = elegir_bloques(cfg, cabecera=t("org_blocks")) or ["base"]
    if cuenta_nueva:
        anadir_seccion(f"github.{cuenta_nueva}", {"usuario": ""})
    seccion = "organizaciones" if tipo == "organizacion" else "entornos"
    anadir_seccion(f"{seccion}.{clave}", datos)
    ws.sync()
    if cuenta_nueva:
        conectar_github(cuenta_nueva)
    return clave


def carpetas_conocidas():
    bases = [Path.home() / "Documents/GitHub", Path.home() / "Github", Path("/Volumes/ExternAscci/Github")]
    res = []
    for b in bases:
        try:
            res += sorted(str(e.path) for e in os.scandir(b) if e.is_dir() and not e.name.startswith("."))
        except OSError:
            pass
    return res


def crear_proyecto(grupo):
    cfg = ws.cargar()
    g = ws.grupos(cfg)[grupo]
    limpiar(t("new_project_in", g=g.get("nombre", grupo)))
    nombre = preguntar(t("project_name"))
    if not nombre:
        return
    clave = slug(nombre)
    raiz = ws.expandir(g.get("raiz", f"~/Orgs/{g.get('nombre', grupo)}"))
    ops = [("nueva", t("new_folder", r=raiz / clave)),
           ("existente", t("existing_folder")),
           ("aqui", t("current_folder", r=CWD))]
    _, sel = elegir(ops, t("where"))
    if not sel:
        return
    if sel[0] == "nueva":
        ruta = raiz / clave
    elif sel[0] == "aqui":
        ruta = CWD
    else:
        _, elegida = elegir([(c, c) for c in carpetas_conocidas()], t("project_folder"))
        if not elegida:
            return
        ruta = Path(elegida[0])
    extra = elegir_bloques(cfg, excluir=g.get("bloques", []),
                           cabecera=t("extra_blocks"))
    casa = str(Path.home())
    datos = {"ruta": str(ruta).replace(casa, "~", 1) if str(ruta).startswith(casa) else str(ruta),
             "bloques": extra}
    anadir_seccion(f'proyectos."{grupo}/{clave}"', datos)
    ruta.mkdir(parents=True, exist_ok=True)
    ws.sync()
    abrir(ws.cargar(), grupo, f"{grupo}/{clave}")


def nueva(grupo=None, normal=False):
    cfg = ws.cargar()
    if not grupo and not normal:
        ops = [("normal", f"{t('normal')}  {SECUNDARIO}{t('normal_as_usual')}{FIN}")]
        for g in ws.grupos(cfg).values():
            tipo = t("organization") if g["tipo"] == "organizacion" else t("environment")
            ops.append((f"g:{g['clave']}", f"{g.get('nombre', g['clave'])}  {SECUNDARIO}{tipo}{FIN}"))
        ops += [("org+", f"{ACTIVO}{t('new_org_item')}{FIN}"), ("ent+", f"{ACTIVO}{t('new_env_item')}{FIN}")]
        _, sel = elegir(ops, t("new_session_q"))
        if not sel:
            return
        if sel[0] == "normal":
            normal = True
        elif sel[0] in ("org+", "ent+"):
            grupo = crear_grupo("organizacion" if sel[0] == "org+" else "entorno")
            if not grupo:
                return
            cfg = ws.cargar()
        else:
            grupo = sel[0][2:]
    if normal:
        limpiar(t("new_normal"))
        nombre = preguntar(t("session_name"))
        if nombre and not tmux("has-session", "-t", f"={nombre}"):
            tmux("new-session", "-d", "-s", nombre, "-c", str(CWD))
        if nombre:
            saltar(nombre)
        return

    comprobar_github(cfg, grupo)
    cfg = ws.cargar()
    ops = [(f"p:{p['clave']}", f"{p['nombre']}  {SECUNDARIO}{p['ruta']}{FIN}")
           for p in ws.proyectos(cfg).values() if p["grupo"] == grupo]
    ops += [("nuevo", f"{ACTIVO}{t('new_project_item')}{FIN}"),
            ("raiz", f"{t('loose_session')}  {SECUNDARIO}{t('no_project')}{FIN}")]
    _, sel = elegir(ops, t("which_project", g=ws.grupos(cfg)[grupo].get("nombre", grupo)))
    if not sel:
        return
    if sel[0] == "nuevo":
        crear_proyecto(grupo)
    elif sel[0] == "raiz":
        prefijo = ws.grupos(cfg)[grupo].get("prefijo", grupo)
        limpiar(t("loose_in", g=ws.grupos(cfg)[grupo].get("nombre", grupo)))
        nombre = preguntar(t("session_name"))
        if nombre:
            abrir(cfg, grupo, nombre=f"{prefijo}-{slug(nombre)}")
    else:
        abrir(cfg, grupo, sel[0][2:])


def main(orden, resto):
    global CWD
    if resto and orden in ("menu", "nueva") and Path(resto[0]).is_dir():
        CWD = Path(resto[0])
    if orden == "preview":
        preview(resto[0] if resto else "")
    elif orden == "accion":
        accion(*resto[:3])
    elif orden in ("menu", "nueva"):
        try:
            menu() if orden == "menu" else nueva()
        finally:
            # Cancelado desde una flotante: se devuelve la flotante como estaba.
            if DESDE_FLOTANTE and not SALTO and ORIGEN:
                reabrir_flotante(ORIGEN)
