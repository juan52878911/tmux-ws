"""Fallos, regeneración, secretos fuera de disco y coste por comando."""
import json
import statistics
import sys
import time
import unittest
from pathlib import Path

from escenario import CasoMundo
from mundo import RAIZ


class Fallos(CasoMundo):
    def test_config_rota_no_te_deja_sin_comandos(self):
        self.m.config.write_text("[organizaciones.rota\nesto no es toml")
        r = self.m.run(["claude", "-p", "x"], cwd=self.m.ruta("empresa/api"))
        self.assertEqual(r.returncode, 0)
        self.assertIn("continuing in normal mode", r.stderr)
        self.assertNotIn("CLAUDE_CONFIG_DIR", self.m.ultima("claude")["env"])

    def test_fallo_con_contexto_conocido_no_usa_la_cuenta_personal(self):
        # El estado del proyecto no se puede escribir: mejor no lanzar que lanzar como "personal".
        self.m.run(["claude"], cwd=self.m.ruta("empresa/api"))
        estado = self.m.estado("p", "empresa", "api")
        for f in estado.iterdir():
            f.unlink()
        estado.chmod(0o500)
        self.addCleanup(estado.chmod, 0o700)
        antes = len(self.m.llamadas("claude"))
        r = self.m.run(["claude"], cwd=self.m.ruta("empresa/api"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("Not launching it with your personal account", r.stderr)
        self.assertEqual(len(self.m.llamadas("claude")), antes)
        # y WS_OFF=1 lo salta a propósito
        r = self.m.run(["claude"], cwd=self.m.ruta("empresa/api"), WS_OFF=1)
        self.assertEqual(r.returncode, 0)
        self.assertNotIn("CLAUDE_CONFIG_DIR", self.m.ultima("claude")["env"])

    def test_dependencias_opcionales_ausentes(self):
        # Sin direnv en el PATH (máquina mínima): nada se rompe.
        import os
        path = ":".join(d for d in os.environ["PATH"].split(":")
                        if not any(os.path.exists(os.path.join(d, b)) for b in ("direnv",)))
        path = f"{self.m.home}/.local/share/ws/shims:{self.m.bin}:{path}"
        r = self.m.ws("sync", PATH=path)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self.m.run(["claude"], cwd=self.m.ruta("lab/nodo"), PATH=path)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_sin_config_todo_es_normal(self):
        self.m.config.unlink()
        r = self.m.run(["gh", "api", "user"], cwd=self.m.ruta("empresa/api"))
        self.assertEqual(r.returncode, 0)
        self.assertNotIn("GH_CONFIG_DIR", self.m.ultima("gh")["env"])

    def test_cambio_en_config_se_aplica_sin_sync_manual(self):
        self.m.run(["claude"], cwd=self.m.ruta("aura/crm"))
        time.sleep(0.05)  # el sello compara fechas de modificación
        self.m.cfg["organizaciones"]["aura"]["claude"] = "propia"
        self.m.escribir()
        self.m.run(["claude"], cwd=self.m.ruta("aura/crm"))
        self.assertEqual(self.m.ultima("claude")["env"].get("CLAUDE_CONFIG_DIR"),
                         str(self.m.estado("claude", "aura")))

    def test_escribir_respeta_el_enlace_de_ws_toml(self):
        real = self.m.home / "dotfiles/ws.toml"
        real.parent.mkdir()
        real.write_text(self.m.config.read_text())
        self.m.config.unlink()
        self.m.config.symlink_to(real)
        pre = f"import sys; sys.path.insert(0, {str(RAIZ / 'src')!r}); import ws_menu as m\n"
        r = self.m.run([sys.executable, "-c", pre + "m.poner_campo('github.nueva', 'usuario', 'yo-nueva')"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.m.config.is_symlink(), "ws.toml dejó de ser un enlace")
        self.assertIn('usuario = "yo-nueva"', real.read_text())

    def test_doctor(self):
        r = self.m.ws("doctor")
        self.assertIn("python", r.stdout)
        self.assertIn("claude goes through ws", r.stdout)


class Secretos(CasoMundo):
    def test_ningun_secreto_en_disco(self):
        for cwd in (self.m.ruta("empresa/api"), self.m.ruta("lab/nodo"), self.m.home):
            self.m.run(["claude"], cwd=cwd)
            self.m.run(["opencode"], cwd=cwd)
        self.m.ws("sync")
        for archivo in self.m.estado().rglob("*"):
            if archivo.is_file():
                texto = archivo.read_text(errors="ignore")
                for secreto in ("k-secreto", "obs-secreto", "mm-secreto", "npm-secreto", "tok-empresa"):
                    if secreto == "tok-empresa" and archivo.name == "hosts.json":
                        continue  # el token de gh vive en su GH_CONFIG_DIR, como con gh real
                    self.assertNotIn(secreto, texto, f"{secreto} en {archivo}")

    def test_direnv_exporta_solo_variables_sin_secreto(self):
        r = self.ws_ok("direnv", cwd=self.m.ruta("empresa/api"))
        self.assertIn("export AWS_PROFILE=desde-proyecto", r.stdout)
        self.assertNotIn("NPM_TOKEN", r.stdout)
        self.assertNotIn("npm-secreto", r.stdout)

    def test_direnv_carga_el_flake_con_herramientas(self):
        r = self.ws_ok("direnv", cwd=self.m.ruta("lab/nodo"))
        self.assertIn('use flake "', r.stdout)
        flake = self.m.estado("p", "lab", "nodo", "flake", "flake.nix").read_text()
        self.assertIn("pkgs.nodejs_24", flake)


class Coste(CasoMundo):
    """Cuánto añade ws a cada comando (shim → ws → programa)."""

    def medir(self, cwd, n=7):
        tiempos = []
        for _ in range(n):
            t = time.perf_counter()
            self.m.run(["gh", "--version"], cwd=cwd)
            tiempos.append(time.perf_counter() - t)
        return statistics.median(tiempos) * 1000

    def test_sobrecoste_por_comando(self):
        self.m.run(["gh", "--version"], cwd=self.m.ruta("empresa/api"))  # primer sync
        directo = statistics.median(
            [self._directo() for _ in range(7)]) * 1000
        normal = self.medir(self.m.home)
        org = self.medir(self.m.ruta("empresa/api"))
        print(f"\n    gh directo {directo:.0f} ms · por ws en Normal {normal:.0f} ms · "
              f"en una org {org:.0f} ms", file=sys.stderr)
        self.assertLess(org - directo, 400, "ws añade demasiado a cada comando")

    def _directo(self):
        t = time.perf_counter()
        self.m.run([str(self.m.bin / "gh"), "--version"])
        return time.perf_counter() - t


if __name__ == "__main__":
    unittest.main()


class Actualizacion(CasoMundo):
    def test_otra_version_de_ws_regenera_aunque_las_fechas_no_cambien(self):
        import os
        self.ws_ok("sync")
        sello = self.m.estado(".sync")
        os.utime(sello, (2_000_000_000, 2_000_000_000))  # sello "más nuevo" que todo
        gitcfg = self.m.estado("gitconfig")
        gitcfg.write_text("# viejo\n")
        sello.write_text(sello.read_text().replace("ws.py", "ws-de-otra-version.py"))
        os.utime(sello, (2_000_000_000, 2_000_000_000))
        self.m.run(["gh", "--version"], cwd=self.m.ruta("empresa/api"))
        self.assertIn("git-credential auto", gitcfg.read_text())
