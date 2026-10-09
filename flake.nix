{
  description = "ws: organizaciones y espacios de trabajo para tmux, con identidad por contexto (GitHub, Claude, git) y entornos Nix";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";

  outputs = { self, nixpkgs }:
    let
      sistemas = [ "aarch64-darwin" "x86_64-darwin" "aarch64-linux" "x86_64-linux" ];
      porSistema = f: nixpkgs.lib.genAttrs sistemas (s: f nixpkgs.legacyPackages.${s});
    in {
      packages = porSistema (pkgs: rec {
        tmux-ws = pkgs.callPackage ./nix/package.nix { };
        default = tmux-ws;
      });

      # nix flake check: las pruebas en un HOME aislado, con cuentas falsas.
      checks = porSistema (pkgs: {
        pruebas = pkgs.runCommand "tmux-ws-pruebas" {
          nativeBuildInputs = with pkgs; [ python3 tmux fzf git ];
        } ''
          cp -r ${self}/. src && chmod -R u+w src && cd src
          export HOME=$TMPDIR/home && mkdir -p $HOME
          python3 tests/run.py
          touch $out
        '';
      });

      homeManagerModules.default = import ./nix/module.nix self;
    };
}
