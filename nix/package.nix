{ lib, stdenvNoCC, makeWrapper, python3, fzf, tmux, git }:

stdenvNoCC.mkDerivation {
  pname = "tmux-ws";
  version = "0.1.0";
  src = lib.cleanSource ../.;
  nativeBuildInputs = [ makeWrapper ];
  dontBuild = true;

  installPhase = ''
    runHook preInstall
    share=$out/share/tmux-ws
    mkdir -p $share $out/bin
    cp -r src scripts shims share ws.tmux $share/
    # fzf y tmux se AÑADEN al final del PATH: ws hace exec de claude/gh y no
    # debe cambiarles qué binarios encuentran.
    makeWrapper ${python3}/bin/python3 $out/bin/ws \
      --add-flags $share/src/ws.py \
      --suffix PATH : ${lib.makeBinPath [ fzf tmux git ]}
    mkdir -p $share/bin
    ln -s $out/bin/ws $share/bin/ws
    runHook postInstall
  '';

  meta = {
    description = "Organizaciones y espacios de trabajo para tmux con identidad por contexto";
    mainProgram = "ws";
    platforms = lib.platforms.unix;
  };
}
