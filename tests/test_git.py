"""Identidad de git por carpeta y registro automático de repos."""
import os
import re
import unittest
from pathlib import Path

from escenario import CasoMundo


class Git(CasoMundo):
    def setUp(self):
        super().setUp()
        self.ws_ok("sync")

    def correo(self, cwd):
        r = self.m.run(["git", "config", "user.email"], cwd=cwd)
        return r.stdout.strip()

    def test_correo_por_organizacion(self):
        self.assertEqual(self.correo(self.m.ruta("empresa/api")), "yo@empresa.com")
        self.assertEqual(self.correo(self.m.ruta("aura/crm")), "yo@aura.dev")
        fuera = self.m.repo(self.m.home / "src/personal")
        self.assertEqual(self.correo(fuera), "yo@personal.dev")

    def test_push_de_la_org_usa_su_cuenta(self):
        rc, datos, _ = self.m.credencial(self.m.ruta("empresa/api"))
        self.assertEqual(rc, 0)
        self.assertEqual((datos["username"], datos["password"]), ("yo-empresa", "tok-empresa"))

    def test_cuenta_sin_conectar_falla_y_no_filtra_la_personal(self):
        # Regresión del bug real: gh con un GH_CONFIG_DIR vacío devolvía el token personal.
        rc, datos, err = self.m.credencial(self.m.ruta("nueva/x"))
        self.assertNotEqual(rc, 0)
        self.assertNotEqual(datos.get("password"), "tok-personal")
        self.assertIn("is not connected", err)

    def test_repo_personal_dentro_de_org_usa_la_personal(self):
        rc, datos, _ = self.m.credencial(self.m.ruta("empresa/propio"))
        self.assertEqual((rc, datos.get("username")), (0, "yo-personal"))

    def test_fuera_de_todo_sigue_el_helper_de_siempre(self):
        fuera = self.m.repo(self.m.home / "src/otro")
        rc, datos, _ = self.m.credencial(fuera)
        self.assertEqual((rc, datos.get("username")), (0, "yo-personal"))

    def test_ssh_por_organizacion(self):
        self.m.cfg["organizaciones"]["aura"]["ssh_clave"] = "~/.ssh/id_aura"
        self.m.escribir()
        self.ws_ok("sync")
        r = self.m.run(["git", "config", "core.sshCommand"], cwd=self.m.ruta("aura/crm"))
        self.assertIn(f"{self.m.home}/.ssh/id_aura", r.stdout)
        self.assertIn("IdentitiesOnly=yes", r.stdout)


class Descubrir(CasoMundo):
    def clonar(self, nombre, remoto):
        return self.m.repo(self.m.home / "src" / nombre, remoto)

    def proyectos(self):
        return re.findall(r'^\[proyectos\."([^"]+)"\]', self.m.config.read_text(), re.M)

    def test_repo_de_org_conocida_se_registra_solo(self):
        ruta = self.clonar("nuevo-servicio", "git@github.com:Empresa-Co/nuevo-servicio.git")
        r = self.ws_ok("descubrir", str(ruta))
        self.assertEqual(r.stdout.strip(), "empresa/nuevo-servicio")
        self.assertIn("empresa/nuevo-servicio", self.proyectos())
        rc, datos, _ = self.m.credencial(ruta)
        self.assertEqual(datos.get("username"), "yo-empresa")  # sync regeneró el gitconfig

    def test_es_idempotente(self):
        ruta = self.clonar("svc", "https://github.com/empresa-co/svc")
        for _ in range(3):
            self.ws_ok("descubrir", str(ruta))
        self.assertEqual(self.proyectos().count("empresa/svc"), 1)

    def test_clon_en_carpeta_temporal_no_se_registra(self):
        import tempfile
        tmp = Path(tempfile.mkdtemp(prefix="scratch-"))
        self.addCleanup(__import__("shutil").rmtree, tmp, True)
        ruta = self.m.repo(tmp / "h2", "https://github.com/empresa-co/h2")
        self.assertEqual(self.ws_ok("descubrir", str(ruta)).stdout.strip(), "")
        self.assertNotIn("empresa/h2", self.proyectos())

    def test_org_desconocida_no_se_registra(self):
        ruta = self.clonar("ajeno", "https://github.com/otra-org/ajeno")
        self.assertEqual(self.ws_ok("descubrir", str(ruta)).stdout.strip(), "")
        self.assertNotIn("empresa/ajeno", self.proyectos())

    def test_al_lanzar_claude_dentro_se_registra(self):
        ruta = self.clonar("svc2", "https://github.com/empresa-co/svc2")
        self.m.run(["claude"], cwd=ruta)
        self.assertEqual(self.m.ultima("claude")["env"]["CLAUDE_CONFIG_DIR"],
                         str(self.m.estado("claude", "empresa")))

    def test_concurrencia_no_duplica(self):
        # Varios shims a la vez en un repo nuevo (p. ej. tmux restaurando panes).
        import subprocess
        import sys
        from mundo import WS_PY
        ruta = self.clonar("carrera", "https://github.com/empresa-co/carrera")
        procs = [subprocess.Popen([sys.executable, str(WS_PY), "descubrir", str(ruta)],
                                  env=self.m.env(), cwd=ruta, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL) for _ in range(8)]
        for p in procs:
            p.wait(timeout=60)
        self.assertEqual(self.proyectos().count("empresa/carrera"), 1, self.m.config.read_text()[-600:])


if __name__ == "__main__":
    unittest.main()


class CredencialPorUrl(CasoMundo):
    """Caso real: un clon hecho antes de que ws conociera el repo dejó la cuenta
    de la empresa en el helper del sistema, y todos los repos personales
    empezaron a salir con ella. ws reemplaza ese helper en github.com."""

    def setUp(self):
        super().setUp()
        self.ws_ok("sync")
        # el helper "del sistema" quedó con la cuenta equivocada
        self.m._json(self.m.mock / "personal.json", {"usuario": "yo-empresa", "token": "tok-empresa"})

    def test_llavero_contaminado_no_afecta(self):
        fuera = self.m.repo(self.m.home / "src/mio")
        rc, datos, _ = self.m.credencial(fuera, "https://github.com/yo-personal/mio.git")
        self.assertEqual((rc, datos.get("username"), datos.get("password")), (0, "yo-personal", "tok-personal"))

    def test_clon_de_org_desde_cualquier_carpeta(self):
        rc, datos, _ = self.m.credencial(self.m.home, "https://github.com/Empresa-Co/nuevo.git")
        self.assertEqual(datos.get("username"), "yo-empresa")

    def test_repo_personal_en_carpeta_de_org(self):
        rc, datos, _ = self.m.credencial(self.m.ruta("empresa/api"), "https://github.com/yo-personal/x.git")
        self.assertEqual(datos.get("username"), "yo-personal")

    def test_dueno_desconocido_usa_la_carpeta(self):
        rc, datos, _ = self.m.credencial(self.m.ruta("empresa/api"), "https://github.com/terceros/lib.git")
        self.assertEqual(datos.get("username"), "yo-empresa")

    def test_no_guarda_en_el_llavero(self):
        entrada = "protocol=https\nhost=github.com\npath=yo-personal/x.git\nusername=u\npassword=p\n\n"
        self.m.run(["git", "credential", "approve"], cwd=self.m.home, entrada=entrada)
        self.assertEqual([c for c in self.m.llamadas("mock-keychain-helper") if c["args"][:1] == ["store"]], [])


class SinConfig(CasoMundo):
    def test_sin_config_lo_personal_sigue_funcionando(self):
        # p. ej. mientras se mueve ws.toml: el helper no debe bloquear pushes personales
        self.ws_ok("sync")
        self.m.config.unlink()
        fuera = self.m.repo(self.m.home / "src/mio")
        rc, datos, _ = self.m.credencial(fuera, "https://github.com/yo-personal/mio.git")
        self.assertEqual((rc, datos.get("password")), (0, "tok-personal"))
