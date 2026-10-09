#!/usr/bin/env bash
# Plugin de tmux para ws (TPM: set -g @plugin 'juan52878911/tmux-ws').
#
# Opciones (antes de cargar el plugin):
#   @ws-key-menu       tecla del selector          (por defecto: s; "none" = no enlazar)
#   @ws-key-new        tecla de nueva sesión       (por defecto: S; "none" = no enlazar)
#   @ws-bin            ruta de ws                  (por defecto: la de Nix o bin/ws)
#   @ws-float-script   script `<sesión> <cliente>` que abre la flotante de una
#                      sesión: activa el cierre/reapertura automática de flotantes
#   @ws-float-prefix   prefijo de las sesiones flotantes   (por defecto: f-)
#   @ws-popup-width / -height / -style / -border-style, @ws-title-menu / -new
#   Tema: @ws-color-*, @ws-nerd-font, @ws-icon-*, @ws-pointer, @ws-preview
#         (ver src/tema.py)
#   @ws-hook-index     índice del hook session-created (por defecto: 42)
#
# En la barra, #{@ws} es la organización/proyecto de la sesión.
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
opt() { local v; v=$(tmux show -gqv "$1"); echo "${v:-$2}"; }

ws_bin=$(opt @ws-bin "")
if [[ -z "$ws_bin" ]]; then
  for c in "/etc/profiles/per-user/$USER/bin/ws" "$HOME/.nix-profile/bin/ws" "$DIR/bin/ws"; do
    [[ -x "$c" ]] && { ws_bin=$c; break; }
  done
fi
tmux set -g @ws-bin "$ws_bin"

# Un valor "none" deja la tecla sin tocar (útil si otro plugin ya la usa).
sel="$DIR/scripts/ws-selector.sh"
for par in "menu:$(opt @ws-key-menu s)" "nueva:$(opt @ws-key-new S)"; do
  orden=${par%%:*} tecla=${par#*:}
  [[ "$tecla" == none ]] && continue
  tmux bind-key "$tecla" run-shell -b \
    "'$sel' $orden '#{client_name}' '#{session_name}' '#{pane_current_path}'"
done

# Marca @ws en las sesiones que nacen dentro de una organización (también las
# restauradas por resurrect y las flotantes f-*, que heredan la de su sesión).
tmux set-hook -g "session-created[$(opt @ws-hook-index 42)]" \
  "run-shell -b \"'$ws_bin' apply #{hook_session_name}\""
