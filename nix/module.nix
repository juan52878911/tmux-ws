# Módulo de home-manager de ws.
self:
{ config, lib, pkgs, ... }:
let
  cfg = config.programs.ws;
  inherit (lib) mkOption mkEnableOption mkIf types;

  # Con `checkout`, ws corre desde tu copia del repo (cambios en vivo, sin
  # rebuild); si no, desde el paquete del store.
  wsBin =
    if cfg.checkout == null then
      pkgs.symlinkJoin {
        name = "ws";
        paths = [ cfg.package ];
        nativeBuildInputs = [ pkgs.makeWrapper ];
        postBuild = lib.optionalString (cfg.nixpkgs != null) ''
          wrapProgram $out/bin/ws --set-default WS_NIXPKGS ${lib.escapeShellArg cfg.nixpkgs}
        '';
      }
    else
      pkgs.writeShellScriptBin "ws" ''
        ${lib.optionalString (cfg.nixpkgs != null) "export WS_NIXPKGS=\${WS_NIXPKGS:-${lib.escapeShellArg cfg.nixpkgs}}"}
        export PATH="$PATH:${lib.makeBinPath [ pkgs.fzf pkgs.tmux ]}"
        exec ${pkgs.python3}/bin/python3 -S ${cfg.checkout}/src/ws.py "$@"
      '';

  enlace = ruta: config.lib.file.mkOutOfStoreSymlink ruta;
in {
  options.programs.ws = {
    enable = mkEnableOption "ws, organizaciones y espacios de trabajo para tmux";

    package = mkOption {
      type = types.package;
      default = self.packages.${pkgs.stdenv.hostPlatform.system}.default;
      description = "Paquete de tmux-ws.";
    };

    checkout = mkOption {
      type = types.nullOr types.str;
      default = null;
      example = "/Users/yo/src/tmux-ws";
      description = "Ruta a una copia local del repo para desarrollar ws sin rebuild.";
    };

    configDir = mkOption {
      type = types.nullOr types.str;
      default = null;
      example = "/Users/yo/dotfiles/config/ws";
      description = ''
        Carpeta con ws.toml (y orgs/<clave>.CLAUDE.md) que se enlaza a ~/.config/ws.
        Enlace fuera del store: el asistente de tmux puede escribir en ws.toml.
      '';
    };

    nixpkgs = mkOption {
      type = types.nullOr types.str;
      default = null;
      example = lib.literalExpression ''"github:NixOS/nixpkgs/''${inputs.nixpkgs.rev}"'';
      description = "nixpkgs que fijan los devShells generados (mejor el de tu flake: comparten store).";
    };

    shims = mkOption {
      type = types.listOf types.str;
      default = [ "claude" "opencode" "gh" ];
      description = "Comandos que pasan por ws (~/.local/share/ws/shims, que va primero en el PATH).";
    };
  };

  config = mkIf cfg.enable {
    home.packages = [ wsBin ];

    home.file = lib.listToAttrs (map (p: {
      name = ".local/share/ws/shims/${p}";
      value = {
        executable = true;
        text = ''
          #!/bin/sh
          exec ${wsBin}/bin/ws exec ${p} "$@"
        '';
      };
    }) cfg.shims) // {
      # Plugin de tmux en una ruta estable: run-shell ~/.local/share/ws/tmux/ws.tmux
      ".local/share/ws/tmux".source =
        if cfg.checkout == null then "${cfg.package}/share/tmux-ws" else enlace cfg.checkout;
    };

    xdg.configFile = lib.mkIf (cfg.configDir != null) { "ws".source = enlace cfg.configDir; };
  };
}
