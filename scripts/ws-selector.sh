#!/usr/bin/env bash
# prefix+s / prefix+S: abre el selector de ws siempre en la ventana principal.
#
#   ws-selector.sh <menu|nueva> <cliente> <sesión> <carpeta>
#
# Con @ws-float-script configurado, si se pulsa desde una flotante <prefijo><sesión>
# la flotante se cierra sola (queda @float_abierta=1 en su sesión) y el
# selector sale en el cliente principal; al volver a esa sesión, o al cancelar,
# ws la reabre.
orden=$1 cliente=$2 sesion=$3 ruta=$4
desde_flotante=0
ws=$(tmux show -gqv @ws-bin); ws=${ws:-ws}

pf=$(tmux show -gqv @ws-float-prefix); pf=${pf:-f-}
if [[ "$sesion" == "$pf"* && -n "$(tmux show -gqv @ws-float-script)" ]]; then
  base=${sesion#"$pf"}
  externo=$(tmux list-clients -t "=$base" -F '#{client_name}' 2>/dev/null | head -1)
  if [[ -n "$externo" ]]; then
    tmux set -t "=$base:" @float_abierta 1
    tmux detach-client -t "$cliente"   # cierra el popup de la flotante
    cliente=$externo sesion=$base desde_flotante=1
    ruta=$(tmux display -p -t "=$base:" '#{pane_current_path}')
    sleep 0.15                          # que el popup termine de cerrarse
  fi
fi

opt() { local v; v=$(tmux show -gqv "$1"); echo "${v:-$2}"; }
titulo=$(opt @ws-title-menu "$("$ws" i18n title_menu)")
[[ "$orden" == nueva ]] && titulo=$(opt @ws-title-new "$("$ws" i18n title_new)")
estilo=()
[[ -n "$(opt @ws-popup-style "")" ]] && estilo+=(-s "$(opt @ws-popup-style "")")
[[ -n "$(opt @ws-popup-border-style "")" ]] && estilo+=(-S "$(opt @ws-popup-border-style "")")
tmux display-popup -c "$cliente" -E -w "$(opt @ws-popup-width 90%)" -h "$(opt @ws-popup-height 85%)" \
  "${estilo[@]}" -T "$titulo" -d "$ruta" \
  "WS_CLIENTE='$cliente' WS_ORIGEN='$sesion' WS_DESDE_FLOTANTE=$desde_flotante '$ws' $orden '$ruta' \
   || { printf '\n%s' \"\$('$ws' i18n error_close)\"; read -rn1; }"
