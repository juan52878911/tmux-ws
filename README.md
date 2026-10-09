# tmux-ws

Work profiles for your terminal, like Android's work profile: each
**organization** has its own GitHub account, Claude Code login, commit email,
variables, MCPs and tools, and you keep typing `claude`, `gh`, `git` or `aws`
as always.

```
context (folder or tmux session)
  └─ identity   GitHub · Claude Code · git · your variables (AWS_PROFILE…)
      └─ tmux sessions grouped by organization
          └─ environment  per-project MCPs, permissions and Nix tools
```

Works in any tmux, alone or next to other plugins: it imposes no keys, colors
or conventions. Everything is optional and configurable.

<!-- GIF: prefix+s, switch between two organizations, `gh api user` in each -->

## What it does

- **Session picker** grouping sessions into Normal, organizations and
  environments, with a preview, and a **wizard** to create sessions,
  organizations and projects.
- **Per-context identity, no new commands.** The context is the project whose
  folder contains the current one; otherwise the tmux session's organization;
  otherwise Normal (everything as usual).
  - `claude`: the organization's `CLAUDE_CONFIG_DIR` (skills, agents and hooks
    shared with your profile), only its blocks' MCPs, and `deny` rules towards
    the other contexts' credentials.
  - `gh`: its account's `GH_CONFIG_DIR`; the web login opens in a private window.
  - `git`: email and SSH key per folder (`includeIf`). For github.com, ws
    replaces the system credential helper: the account is picked by **the repo
    owner in the URL** (an organization's `github_orgs`, or your own user),
    then by folder, then personal. Nothing is stored, so one account's
    credential can never shadow the others.
  - `opencode`: the same MCPs.
  - **Any other program** gets the context's `env` variables through a
    one-line shim or `ws exec <program>`.
- **Per-project tools** with Nix: a `flake.nix` generated outside the repo and
  loaded by direnv + nix-direnv. Client repos stay clean.
- **Automatic registration** of repos cloned from each organization's GitHub
  orgs (`github_orgs`).
- **Finder tags** per organization (macOS).

## Requirements

| | Version | Used for |
|---|---|---|
| tmux | ≥ 3.3 | picker popups |
| python | ≥ 3.11 | `tomllib`; no external packages |
| fzf | ≥ 0.62 | picker and wizard |
| git | — | per-folder identity |
| gh | optional | GitHub accounts (also the personal one, for git over HTTPS) |
| direnv + nix-direnv, nix | optional | per-project tools |
| `security` (macOS) / `secret-tool` (Linux) | optional | `${NAME}` secrets |

`ws doctor` checks all of this plus the integration (PATH, gitconfig, config).

## Installation

### Nix + home-manager

```nix
# flake.nix
inputs.tmux-ws = {
  url = "github:juan52878911/tmux-ws";
  inputs.nixpkgs.follows = "nixpkgs";
};

# home-manager module
imports = [ inputs.tmux-ws.homeManagerModules.default ];
programs.ws = {
  enable = true;
  configDir = "/Users/me/dotfiles/config/ws";        # ws.toml and orgs/*.CLAUDE.md
  nixpkgs = "github:NixOS/nixpkgs/${inputs.nixpkgs.rev}";
  shims = [ "claude" "opencode" "gh" "aws" ];        # commands routed through ws
};
```

The package ships python, fzf, tmux and git. The module installs `ws`, the
shims in `~/.local/share/ws/shims` and the plugin in `~/.local/share/ws/tmux`.
To hack on ws without rebuilding: `programs.ws.checkout = "/path/to/tmux-ws";`.

### TPM

```tmux
set -g @plugin 'juan52878911/tmux-ws'
```

The shims live in `~/.tmux/plugins/tmux-ws/shims`.

### Integration (both ways)

```tmux
# ~/.tmux.conf; with Nix, instead of @plugin:
run-shell ~/.local/share/ws/tmux/ws.tmux
```

Add [`share/zshrc`](share/zshrc) to `~/.zshrc` (shims first in PATH and
automatic registration on `cd`), [`share/gitconfig`](share/gitconfig) to
`~/.gitconfig` and [`share/direnvrc`](share/direnvrc) to
`~/.config/direnv/direnvrc`.

## Configuration

Everything lives in `~/.config/ws/ws.toml`; start from
[`examples/ws.toml`](examples/ws.toml). The wizard adds organizations, accounts
and projects for you. (Config keys are in Spanish: they are part of the format.)

| Section | Defines |
|---|---|
| `[github.<account>]` | GitHub accounts; `personal` is your usual one |
| `[organizaciones.<key>]` | credentials, blocks, `github_orgs`, `env`, root folder and tag |
| `[entornos.<key>]` | your own credentials with a set of blocks |
| `[bloques]` | reusable pieces: `mcps`, `agentes`, `herramientas`, `permitir`, `env`, `claude_motor` |
| `[mcps.<name>]` | each MCP once, in a neutral format (translated for Claude and opencode) |
| `[agentes.<name>]` | each agent's command (one window per agent in the session) |
| `[acciones.<name>]` | your own picker keys |
| `[proyectos."<group>/<name>"]` | folder, extra blocks, `quitar`, `env` and credential overrides |
| `[ui]` | `lang = "en"` or `"es"` |

Secrets are written as `${NAME}`. They are read when the command launches, from
the macOS Keychain (`security add-generic-password -s ws/NAME -w`), from
libsecret on Linux (`secret-tool store --label ws service ws/NAME`) or from the
environment. They are never written to disk or to your shell.

## Language

The interface is in English by default. For Spanish, any of:

```tmux
set -g @ws-lang es          # tmux.conf
```
```toml
[ui]
lang = "es"                 # ws.toml
```

or `WS_LANG=es` in the environment (it wins over the other two). Strings live
in [`src/i18n.py`](src/i18n.py); adding a language means copying the `en`
block and translating it (a test checks every language has the same keys).

Confirmations put "Yes" first (Enter confirms) and take a single key:
`y`/`n` in English, `s`/`n` in Spanish.

## Look and feel

By default the picker uses your terminal's ANSI colors, so it fits any theme.
To make it yours:

```tmux
set -g @ws-color-accent    '#cba6f7'   # titles, keys, pointer, current session
set -g @ws-color-active    '#a6e3a1'   # open sessions
set -g @ws-color-muted     '#6c7086'   # labels and footer
set -g @ws-color-dim       '#585b70'   # details and closed sessions
set -g @ws-color-info      '#89b4fa'   # Nix tools
set -g @ws-color-text      '#cdd6f4'
set -g @ws-color-match     '#f38ba8'   # search matches
set -g @ws-color-selection '#313244'   # selected row background
set -g @ws-color-border    '#45475a'
set -g @ws-nerd-font       on          # icons; or @ws-icon-normal/-organization/-environment/-github/-search
set -g @ws-pointer         '▌'
set -g @ws-preview         'right,58%,border-left,<120(down,55%,border-top)'
set -g @ws-popup-width 90%   ;  set -g @ws-popup-height 85%
set -g @ws-popup-style 'fg=#cdd6f4,bg=#181825'  ;  set -g @ws-popup-border-style 'fg=#585b70'
```

Colors accept ANSI names (`magenta`, `bright-black`), numbers 0-255,
`#rrggbb` or `default`.

## Playing well with other plugins

| Option | Default | |
|---|---|---|
| `@ws-key-menu` / `@ws-key-new` | `s` / `S` | `none` = don't bind (call `scripts/ws-selector.sh` yourself) |
| `@ws-hook-index` | `42` | `session-created` index, so other hooks aren't overwritten |
| `@ws-bin` | the Nix one or `bin/ws` | path to `ws` |
| `@ws-float-script` | — | script `<session> <client>` that opens a session's floating window; enables closing it and reopening it automatically when the picker is used from inside it |
| `@ws-float-prefix` | `f-` | floating sessions prefix |
| `@ws-lang` | `en` | interface language |

For other plugins and status bars:
- `#{@ws}` in any tmux format: the session's organization or project.
- `ws contexto [--json]`: context of the current folder.
- `ws exec <program>`: launch anything with the context's identity and variables.
- `[acciones]`: your own commands in the picker, with `WS_GRUPO`,
  `WS_PROYECTO`, `WS_SESION` and `WS_RUTA`.

## Tests

```bash
python3 tests/run.py            # all of them, in parallel (~20 s)
python3 tests/run.py --rapido   # without the end-to-end ones
nix flake check                 # the same, in the Nix sandbox
```

Each test builds an isolated world ([`tests/mundo.py`](tests/mundo.py)): a
temporary `HOME`, fake GitHub and Claude accounts, a fake Keychain, git repos
with remotes from made-up orgs and its own tmux server. `claude`, `gh`,
`opencode` and `security` are fake programs that record the identity they were
called with; git and tmux are the real ones. Nothing touches your accounts.

| Module | Checks |
|---|---|
| `test_contexto` | folder, subfolders, nested projects, symlinks, org root, inheritance and `quitar` |
| `test_identidad` | what each program gets: Claude config, MCPs, engine, secrets, `env`, `deny` rules, gh, opencode |
| `test_git` | email and SSH per folder, account by repo owner, unconnected account (never falls back to the personal one), contaminated system keychain, automatic registration, concurrency |
| `test_tmux` | marks, floating windows, session as context, picker rows and preview, agents, actions, theme, fzf options, language |
| `test_robustez` | broken or missing config, failure with a known context (won't launch as personal), machine without optional dependencies, secrets off disk, direnv, Finder tags, per-command overhead |
| `test_e2e` | a real tmux client on a pty: `prefix+s`, search, open, Esc, and the full floating-window cycle |
| `test_e2e_confirmar` | closing a session with Enter, `y`, `n` and `s` (Spanish) |

## What it is not

`WS_OFF=1 <command>` skips ws entirely. If ws knows the context but something
fails while preparing it, the command does not launch: running it with your
personal account would mix identities exactly where it must not.

**It is not a sandbox.** Everything runs as your user: it protects against
mistakes (a push with the wrong account, an agent reading someone else's
credentials by accident), not against malicious code. Claude's `deny` rules
cover its file tools, not a `cat` run through Bash. For real isolation, use a
separate system user or a VM per context.

The Claude desktop app and GitHub Desktop don't go through the shims.

## License

MIT
