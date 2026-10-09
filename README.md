# tmux-ws

Perfiles de trabajo para la terminal, como el perfil de trabajo de Android:
cada **organización** tiene su cuenta de GitHub, su login de Claude Code, su
correo de commits, sus variables, sus MCPs y sus herramientas, y tú sigues
escribiendo `claude`, `gh`, `git` o `aws` como siempre.

```
contexto (carpeta o sesión de tmux)
  └─ identidad   GitHub · Claude Code · git · tus variables (AWS_PROFILE…)
      └─ sesiones de tmux agrupadas por organización
          └─ entorno  MCPs, permisos y herramientas Nix del proyecto
```

Funciona en cualquier tmux, solo o junto a otros plugins: no impone teclas,
colores ni convenciones. Todo es opcional y configurable.

<!-- GIF: prefix+s, saltar entre dos organizaciones, `gh api user` en cada una -->

## Qué hace

- **Selector de sesiones** agrupadas en Normal, organizaciones y entornos, con
  vista previa, y **asistente** para crear sesiones, organizaciones y proyectos.
- **Identidad por contexto, sin comandos nuevos**. El contexto es el proyecto
  cuya carpeta contiene la actual; si no hay, la organización de la sesión de
  tmux; si no, Normal (todo como siempre).
  - `claude`: `CLAUDE_CONFIG_DIR` de la organización (skills, agentes y hooks
    compartidos con tu perfil), solo los MCPs de sus bloques y reglas `deny`
    hacia las credenciales de los demás contextos.
  - `gh`: `GH_CONFIG_DIR` de su cuenta; el login web abre en incógnito.
  - `git`: correo, clave SSH y credenciales de GitHub por carpeta (`includeIf`),
    en cualquier terminal.
  - `opencode`: los mismos MCPs.
  - **Cualquier otro programa**: recibe las variables `env` del contexto con un
    shim de una línea o con `ws exec <programa>`.
- **Herramientas por proyecto** con Nix: `flake.nix` generado fuera del repo y
  cargado por direnv + nix-direnv. Los repos de clientes quedan limpios.
- **Registro automático** de los repos clonados de las orgs de GitHub de cada
  organización (`github_orgs`).
- **Etiquetas de Finder** por organización (macOS).

## Dependencias

| | Versión | Para qué |
|---|---|---|
| tmux | ≥ 3.3 | popups del selector |
| python | ≥ 3.11 | `tomllib`; sin paquetes externos |
| fzf | ≥ 0.62 | selector y asistente |
| git | — | identidad por carpeta |
| gh | opcional | cuentas de GitHub por organización |
| direnv + nix-direnv, nix | opcional | herramientas por proyecto |
| `security` (macOS) / `secret-tool` (Linux) | opcional | secretos `${NOMBRE}` |

`ws doctor` comprueba todo esto y la integración (PATH, gitconfig, config).

## Instalación

### Nix + home-manager

```nix
# flake.nix
inputs.tmux-ws = {
  url = "github:juan52878911/tmux-ws";
  inputs.nixpkgs.follows = "nixpkgs";
};

# módulo de home-manager
imports = [ inputs.tmux-ws.homeManagerModules.default ];
programs.ws = {
  enable = true;
  configDir = "/Users/yo/dotfiles/config/ws";        # ws.toml y orgs/*.CLAUDE.md
  nixpkgs = "github:NixOS/nixpkgs/${inputs.nixpkgs.rev}";
  shims = [ "claude" "opencode" "gh" "aws" ];        # comandos que pasan por ws
};
```

El paquete trae python, fzf, tmux y git. El módulo instala `ws`, los shims en
`~/.local/share/ws/shims` y el plugin en `~/.local/share/ws/tmux`. Para
desarrollar sin rebuild: `programs.ws.checkout = "/ruta/a/tmux-ws";`.

### TPM

```tmux
set -g @plugin 'juan52878911/tmux-ws'
```

Los shims quedan en `~/.tmux/plugins/tmux-ws/shims`.

### Integración (las dos formas)

```tmux
# ~/.tmux.conf; con Nix, en vez de @plugin:
run-shell ~/.local/share/ws/tmux/ws.tmux
```

Añade [`share/zshrc`](share/zshrc) a `~/.zshrc` (shims primero en el PATH y
registro automático al hacer `cd`), [`share/gitconfig`](share/gitconfig) a
`~/.gitconfig` y [`share/direnvrc`](share/direnvrc) a `~/.config/direnv/direnvrc`.

## Configuración

Todo vive en `~/.config/ws/ws.toml`; parte de [`examples/ws.toml`](examples/ws.toml).
El asistente añade organizaciones, cuentas y proyectos por ti.

| Sección | Qué define |
|---|---|
| `[github.<cuenta>]` | cuentas de GitHub; `personal` es la de siempre |
| `[organizaciones.<clave>]` | credenciales, bloques, `github_orgs`, `env`, raíz y etiqueta |
| `[entornos.<clave>]` | tus credenciales con un conjunto de bloques |
| `[bloques]` | piezas reutilizables: `mcps`, `agentes`, `herramientas`, `permitir`, `env`, `claude_motor` |
| `[mcps.<nombre>]` | cada MCP una vez, en formato neutro (se traduce para Claude y opencode) |
| `[agentes.<nombre>]` | comando de cada agente (una ventana por agente en la sesión) |
| `[acciones.<nombre>]` | teclas propias del selector |
| `[proyectos."<grupo>/<nombre>"]` | carpeta, bloques extra, `quitar`, `env` y excepciones de credenciales |

Los secretos van como `${NOMBRE}`. Se leen al lanzar el comando del Llavero de
macOS (`security add-generic-password -s ws/NOMBRE -w`), de libsecret en Linux
(`secret-tool store --label ws service ws/NOMBRE`) o del entorno. Nunca se
escriben en disco ni en el shell.

## Diseño

El selector usa por defecto los colores ANSI de tu terminal, así encaja con
cualquier tema. Para darle el tuyo:

```tmux
set -g @ws-color-accent    '#cba6f7'   # títulos, teclas, puntero, sesión actual
set -g @ws-color-active    '#a6e3a1'   # sesiones abiertas
set -g @ws-color-muted     '#6c7086'   # etiquetas y pie
set -g @ws-color-dim       '#585b70'   # detalles y sesiones cerradas
set -g @ws-color-info      '#89b4fa'   # herramientas Nix
set -g @ws-color-text      '#cdd6f4'
set -g @ws-color-match     '#f38ba8'   # coincidencias de búsqueda
set -g @ws-color-selection '#313244'   # fondo de la fila elegida
set -g @ws-color-border    '#45475a'
set -g @ws-nerd-font       on          # iconos; o @ws-icon-normal/-organization/-environment/-github/-search
set -g @ws-pointer         '▌'
set -g @ws-preview         'right,58%,border-left,<120(down,55%,border-top)'
set -g @ws-popup-width 90%   ;  set -g @ws-popup-height 85%
set -g @ws-popup-style 'fg=#cdd6f4,bg=#181825'  ;  set -g @ws-popup-border-style 'fg=#585b70'
```

Los colores aceptan nombres ANSI (`magenta`, `bright-black`), números 0-255,
`#rrggbb` o `default`.

## Convivir con otros plugins

| Opción | Por defecto | |
|---|---|---|
| `@ws-key-menu` / `@ws-key-new` | `s` / `S` | `none` = no enlazar (llama tú a `scripts/ws-selector.sh`) |
| `@ws-hook-index` | `42` | índice de `session-created`, para no pisar otros hooks |
| `@ws-bin` | el de Nix o `bin/ws` | ruta de `ws` |
| `@ws-float-script` | — | script `<sesión> <cliente>` que abre la flotante de una sesión; activa el cierre y la reapertura automáticos al usar el selector desde una flotante |
| `@ws-float-prefix` | `f-` | prefijo de las sesiones flotantes |

Para otros plugins y barras:
- `#{@ws}` en cualquier formato de tmux: organización o proyecto de la sesión.
- `ws contexto [--json]`: contexto de la carpeta actual.
- `ws exec <programa>`: lanza cualquier cosa con la identidad y las variables del contexto.
- `[acciones]`: comandos propios en el selector, con `WS_GRUPO`, `WS_PROYECTO`, `WS_SESION` y `WS_RUTA`.

## Lo que no es

**No es un sandbox.** Todo corre con tu usuario: protege contra errores (un
push con la cuenta equivocada, un agente leyendo credenciales ajenas por
accidente), no contra código malicioso. Las reglas `deny` de Claude cubren sus
herramientas de lectura, no un `cat` lanzado por Bash. Para aislamiento real,
un usuario del sistema o una VM por contexto.

La app de escritorio de Claude y GitHub Desktop no pasan por los shims.

## Licencia

MIT
