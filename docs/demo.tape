# GIF del README. Regenerar desde la raíz del repo con:
#   nix run nixpkgs#vhs -- docs/demo.tape
# Usa la demo aislada (tests/demo.py): organizaciones y cuentas inventadas.

Output docs/demo.gif

Set Shell "bash"
Set FontFamily "IosevkaTerm Nerd Font Mono"
Set FontSize 22
Set Width 1200
Set Height 680
Set Padding 18
Set Theme "Catppuccin Mocha"
Set TypingSpeed 55ms
Set Framerate 24

Hide
Type "clear && python3 tests/demo.py" Enter
Sleep 4s
Show

# Fuera de toda organización: tu cuenta personal
Type "gh api user" Sleep 300ms Enter
Sleep 1.5s

# Selector: organizaciones, proyectos y vista previa
Ctrl+a
Type "s"
Sleep 3s
Type "j" Sleep 500ms
Type "j" Sleep 500ms
Type "j" Sleep 1.2s
Enter
Sleep 2s

# Dentro de Acme: su cuenta de GitHub, su correo y su Claude
Type "gh api user; git config user.email" Sleep 300ms Enter
Sleep 2s
Type "claude" Sleep 300ms Enter
Sleep 2.5s

# Saltar a Globex buscando
Ctrl+a
Type "s"
Sleep 1.5s
Type "/site" Sleep 800ms
Enter
Sleep 2s
Type "gh api user; git config user.email" Sleep 300ms Enter
Sleep 2s
Type "claude" Sleep 300ms Enter
Sleep 3s

Hide
Ctrl+a
Type "d"
Sleep 1s
