#!/usr/bin/env bash
# Vista previa del selector de ws (fzf --preview), sin arrancar Python en cada movimiento del cursor.
#
#   ws-preview.sh <carpeta> <clave>
#
# <carpeta> la prepara `ws menu` al abrirse (preparar_vistas en ws_menu.py): el texto fijo de cada fila
# (<clave>.txt), la sesión de cada proyecto (<clave>.ses), los colores del tema (tema.sh) y cómo llamar a ws
# (yo). Una sesión abierta se pinta con una sola llamada a tmux. Lo que no esté preparado (filas nuevas tras
# un reload del menú) lo pinta `ws preview`, como antes.
dir=$1 clave=$2
f=${clave//\//%}
# shellcheck disable=SC1091
. "$dir/tema.sh" 2>/dev/null || exec bash -c "$(cat "$dir/yo") preview \"\$1\"" _ "$clave"

case $clave in
  s:*) sesion=${clave#s:} ;;
  p:*) sesion=$(<"$dir/$f.ses") 2>/dev/null ;;
  *) sesion= ;;
esac

if [[ -n "$sesion" ]]; then
  M='@@ws-vista@@'
  # has-session corta la cadena si la sesión ya no existe: entonces no sale nada y se cae a lo fijo.
  out=$(tmux has-session -t "=$sesion" \; show -t "=$sesion:" -qv @ws \; display -p "$M" \
    \; list-windows -t "=$sesion" -F '#{window_active}	#{window_name}' \; display -p "$M" \
    \; capture-pane -ep -t "=$sesion:" 2>/dev/null)
  if [[ -n "$out" ]]; then
    marca=${out%%"$M"*}; marca=${marca%$'\n'}
    resto=${out#*"$M"$'\n'}
    ventanas=${resto%%"$M"*}
    pantalla=${resto#*"$M"$'\n'}
    lista=
    while IFS=$'\t' read -r activa nombre; do
      [[ -z "$nombre" ]] && continue
      [[ -n "$lista" ]] && lista+=" ${TENUE}·${FIN} "
      if [[ "$activa" == 1 ]]; then lista+="${TEXTO}${nombre}${FIN}"; else lista+="${TENUE}${nombre}${FIN}"; fi
    done <<<"$ventanas"
    printf ' %s%s%s%s' "$ACENTO" "$NEGRITA" "$sesion" "$FIN"
    [[ -n "$marca" ]] && printf '   %s%s%s' "$SECUNDARIO" "$marca" "$FIN"
    printf '\n %s▐%s %s\n\n%s\n' "$TENUE" "$FIN" "$lista" "$pantalla"
    exit 0
  fi
fi

if [[ -f "$dir/$f.txt" ]]; then
  cat "$dir/$f.txt"
else
  exec bash -c "$(cat "$dir/yo") preview \"\$1\"" _ "$clave"
fi
