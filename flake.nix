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

      homeManagerModules.default = import ./nix/module.nix self;
    };
}
