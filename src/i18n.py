"""Textos de la interfaz. Inglés por defecto; español con cualquiera de:

  set -g @ws-lang es          (tmux.conf)
  [ui] lang = "es"            (ws.toml)
  WS_LANG=es                  (entorno)

Para añadir un idioma: copiar el bloque "en" con su código y traducirlo.
"""
import os
import subprocess

TEXTOS = {
    "en": {
        # pie y búsqueda
        "search": "search…", "k_open": "open", "k_new": "new", "k_close": "close",
        "k_rename": "rename", "k_edit": "edit", "k_github": "github", "k_search": "search",
        "k_choose": "choose", "k_mark": "mark", "k_back": "back", "k_yes": "yes", "k_no": "no",
        # confirmación (tecla rápida para sí)
        "yes": "Yes", "no": "No", "yes_key": "y", "no_key": "n",
        # selector
        "normal": "Normal", "own": "own", "personal": "personal", "not_connected": "not connected",
        "environment": "environment", "organization": "organization",
        # vista previa
        "p_normal_title": "Normal session",
        "p_normal_text": "Your personal account and your usual MCPs.",
        "p_normal_enter": "create a normal session",
        "p_folder": "folder", "p_github": "github", "p_claude": "claude", "p_email": "git email",
        "p_blocks": "blocks", "p_mcps": "mcps", "p_agents": "agents", "p_tools": "tools",
        "p_same_email": "the usual one", "p_host_tools": "the system's",
        "p_open": "open the session", "p_new_here": "new session here", "p_connect": "connect GitHub",
        # acciones
        "close_session": "close session {s}", "rename": "Rename {s}", "new_name": "New name",
        "enter_back": "Enter to go back…", "uses_personal_gh": "This organization uses your personal GitHub account. Enter to go back…",
        # GitHub
        "connect_title": "Connect GitHub «{c}»",
        "connect_1": "A private browser window will open.",
        "connect_2": "Sign in with the organization's account, paste the code gh shows and authorize.",
        "login_failed": "Login not completed. Enter to go back…",
        "connected_as": "✓ {c} connected as {u}",
        "connect_now": "connect the GitHub account «{c}» now",
        # asistente
        "new_org": "New organization", "new_env": "New environment", "name": "Name",
        "prefix": "Session prefix", "root": "Projects folder",
        "gh_personal": "My personal GitHub account", "gh_account": "The account «{c}» ({u})",
        "gh_other": "Another GitHub account (connect now, private window)", "gh_of": "GitHub for {n}",
        "claude_mine": "My Claude account",
        "claude_org": "The organization's Claude account (separate login and history)",
        "claude_in": "Claude in {n}", "commit_email": "Commit email (empty = the usual one)",
        "org_blocks": "Organization blocks  ·  none = base", "blocks": "Blocks",
        "new_project_in": "New project in {g}", "project_name": "Project name",
        "new_folder": "New folder: {r}", "existing_folder": "A folder I already have…",
        "current_folder": "Current folder: {r}", "where": "Where does it live?",
        "project_folder": "Project folder", "extra_blocks": "Extra project blocks  ·  none = none",
        "normal_as_usual": "as usual", "new_org_item": "＋ new organization",
        "new_env_item": "＋ new environment",
        "new_session_q": "New session: normal, or inside an organization/environment?",
        "new_normal": "New normal session", "session_name": "Session name",
        "new_project_item": "＋ new project", "loose_session": "Loose session in the organization",
        "no_project": "no project", "which_project": "{g}: which project?",
        "loose_in": "Loose session in {g}", "claude_with": "claude with {m}", "tools_lbl": "❄",
        "blocks_mcps": "MCPs", "blocks_agents": "agents", "blocks_perms": "permissions",
        # ws.py
        "err_prepare": "ws: couldn't prepare «{d}» for {p}: {e}\n    Not launching it with your personal account, to avoid mixing identities.\n    Check `ws doctor`, or skip ws this once: WS_OFF=1 {p} …",
        "err_config": "ws: {c}: {e} — continuing in normal mode",
        "err_not_connected": "ws: the GitHub account «{c}» is not connected (prefix+s, ^g on the organization)",
        "err_no_token": "ws: no token for {u} in «{c}» (prefix+s, ^g on the organization)",
        "err_deny": "ws: couldn't write the deny rules ({e})",
        "err_no_direnv": "ws: {n} has Nix tools but direnv is not installed",
        "err_envrc": "ws: {f} already exists and doesn't load `use ws`; add it by hand",
        "error_close": "ws exited with an error. Press a key to close…",
        "title_menu": " sessions ", "title_new": " new session ",
        "d_missing": "not found", "d_need": "needs ≥ {v}", "d_config_missing": "(missing: start from examples/ws.toml)",
        "d_through": "{p} goes through ws", "d_shim_not_first": "{p}: the shim exists but {d} is not first in PATH",
        "d_gitconfig": "~/.gitconfig includes ~/.local/state/ws/gitconfig",
        "d_no_email": "{g}: own GitHub account but no git_correo (commits would use your personal email)",
        "d_broken_link": "broken link: {l}",
        "d_dup_path": "projects sharing a folder: {a} and {b}",
        "d_identity_ok": "per-organization identity",
        "d_secrets": "secrets (${{NAME}}) with {p}",
        "d_secrets_env": "secrets (${NAME}) only from the environment: no [secretos].comando",
    },
    "es": {
        "search": "buscar…", "k_open": "abrir", "k_new": "nueva", "k_close": "cerrar",
        "k_rename": "renombrar", "k_edit": "editar", "k_github": "github", "k_search": "buscar",
        "k_choose": "elegir", "k_mark": "marcar", "k_back": "volver", "k_yes": "sí", "k_no": "no",
        "yes": "Sí", "no": "No", "yes_key": "s", "no_key": "n",
        "normal": "Normal", "own": "propia", "personal": "personal", "not_connected": "sin conectar",
        "environment": "entorno", "organization": "organización",
        "p_normal_title": "Sesión normal",
        "p_normal_text": "Tu cuenta personal y tus MCPs de siempre.",
        "p_normal_enter": "crear una sesión normal",
        "p_folder": "carpeta", "p_github": "github", "p_claude": "claude", "p_email": "correo git",
        "p_blocks": "bloques", "p_mcps": "mcps", "p_agents": "agentes", "p_tools": "herramientas",
        "p_same_email": "el de siempre", "p_host_tools": "las del sistema",
        "p_open": "abrir la sesión", "p_new_here": "nueva sesión aquí", "p_connect": "conectar GitHub",
        "close_session": "cerrar la sesión {s}", "rename": "Renombrar {s}", "new_name": "Nuevo nombre",
        "enter_back": "Enter para volver…", "uses_personal_gh": "Esta organización usa tu cuenta personal de GitHub. Enter para volver…",
        "connect_title": "Conectar GitHub «{c}»",
        "connect_1": "Se abrirá una ventana de incógnito.",
        "connect_2": "Entra con la cuenta de la organización, pega el código que muestra gh y autoriza.",
        "login_failed": "No se completó el login. Enter para volver…",
        "connected_as": "✓ {c} conectada como {u}",
        "connect_now": "conectar ahora la cuenta de GitHub «{c}»",
        "new_org": "Nueva organización", "new_env": "Nuevo entorno", "name": "Nombre",
        "prefix": "Prefijo de sus sesiones", "root": "Carpeta de sus proyectos",
        "gh_personal": "Mi cuenta personal de GitHub", "gh_account": "La cuenta «{c}» ({u})",
        "gh_other": "Otra cuenta de GitHub (conectar ahora en incógnito)", "gh_of": "GitHub de {n}",
        "claude_mine": "Mi cuenta de Claude",
        "claude_org": "Cuenta de Claude de la organización (login e historial aparte)",
        "claude_in": "Claude en {n}", "commit_email": "Correo de los commits (vacío = el de siempre)",
        "org_blocks": "Bloques de la organización  ·  sin marcar = base", "blocks": "Bloques",
        "new_project_in": "Nuevo proyecto en {g}", "project_name": "Nombre del proyecto",
        "new_folder": "Carpeta nueva: {r}", "existing_folder": "Una carpeta que ya tengo…",
        "current_folder": "La carpeta actual: {r}", "where": "¿Dónde vive?",
        "project_folder": "Carpeta del proyecto", "extra_blocks": "Bloques extra del proyecto  ·  sin marcar = ninguno",
        "normal_as_usual": "como siempre", "new_org_item": "＋ nueva organización",
        "new_env_item": "＋ nuevo entorno",
        "new_session_q": "Nueva sesión: ¿normal o dentro de una organización/entorno?",
        "new_normal": "Nueva sesión normal", "session_name": "Nombre de la sesión",
        "new_project_item": "＋ nuevo proyecto", "loose_session": "Sesión suelta en la organización",
        "no_project": "sin proyecto", "which_project": "{g}: ¿qué proyecto?",
        "loose_in": "Sesión suelta en {g}", "claude_with": "claude con {m}", "tools_lbl": "❄",
        "blocks_mcps": "MCPs", "blocks_agents": "agentes", "blocks_perms": "permisos",
        "err_prepare": "ws: no pude preparar «{d}» para {p}: {e}\n    No lo lanzo con tu cuenta personal para no mezclar identidades.\n    Revisa `ws doctor`, o sáltate ws esta vez: WS_OFF=1 {p} …",
        "err_config": "ws: {c}: {e} — sigo en modo normal",
        "err_not_connected": "ws: la cuenta de GitHub «{c}» no está conectada (prefix+s, ^g sobre la organización)",
        "err_no_token": "ws: no hay token de {u} para «{c}» (prefix+s, ^g sobre la organización)",
        "err_deny": "ws: no pude escribir las reglas deny ({e})",
        "err_no_direnv": "ws: {n} tiene herramientas Nix pero direnv no está instalado",
        "err_envrc": "ws: {f} ya existe y no carga `use ws`; añádelo a mano",
        "error_close": "ws terminó con error. Pulsa una tecla para cerrar…",
        "title_menu": " sesiones ", "title_new": " nueva sesion ",
        "d_missing": "no está", "d_need": "hace falta ≥ {v}", "d_config_missing": "(no existe: parte de examples/ws.toml)",
        "d_through": "{p} pasa por ws", "d_shim_not_first": "{p}: el shim existe pero {d} no va primero en el PATH",
        "d_gitconfig": "~/.gitconfig incluye ~/.local/state/ws/gitconfig",
        "d_no_email": "{g}: cuenta de GitHub propia pero sin git_correo (los commits saldrían con tu correo personal)",
        "d_broken_link": "enlace roto: {l}",
        "d_dup_path": "proyectos que comparten carpeta: {a} y {b}",
        "d_identity_ok": "identidad por organización",
        "d_secrets": "secretos (${{NOMBRE}}) con {p}",
        "d_secrets_env": "secretos (${NOMBRE}) solo del entorno: no hay [secretos].comando",
    },
}

_IDIOMA = None


def idioma(cfg=None):
    """WS_LANG > @ws-lang de tmux > [ui].lang de ws.toml > inglés."""
    global _IDIOMA
    if _IDIOMA:
        return _IDIOMA
    valor = os.environ.get("WS_LANG", "")
    if not valor and os.environ.get("TMUX"):
        try:
            valor = subprocess.run(["tmux", "show", "-gqv", "@ws-lang"], capture_output=True,
                                   text=True, timeout=2).stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            valor = ""
    if not valor:
        if cfg is None:
            try:
                import tomllib
                ruta = os.environ.get("WS_CONFIG") or os.path.expanduser("~/.config/ws/ws.toml")
                with open(ruta, "rb") as f:
                    cfg = tomllib.load(f)
            except (OSError, ValueError):
                cfg = {}
        valor = cfg.get("ui", {}).get("lang", "")
    valor = valor.lower()[:2]
    _IDIOMA = valor if valor in TEXTOS else "en"
    return _IDIOMA


def t(clave, **datos):
    texto = TEXTOS[idioma()].get(clave) or TEXTOS["en"].get(clave, clave)
    return texto.format(**datos) if datos else texto
