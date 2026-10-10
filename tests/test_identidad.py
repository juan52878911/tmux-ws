"""Lo que recibe cada programa según el contexto (vía shims o `ws exec`)."""
import json
import unittest
from pathlib import Path

from escenario import CasoMundo


class Claude(CasoMundo):
    def lanzar(self, cwd, *args, **env):
        r = self.m.run(["claude", *args], cwd=cwd, **env)  # pasa por el shim
        self.assertEqual(r.returncode, 0, r.stderr)
        return self.m.ultima("claude")

    def opcion(self, llamada, nombre):
        a = llamada["args"]
        return a[a.index(nombre) + 1] if nombre in a else None

    def test_normal_solo_anade_reglas_deny(self):
        c = self.lanzar(self.m.home, "-p", "hola")
        self.assertNotIn("CLAUDE_CONFIG_DIR", c["env"])
        self.assertNotIn("--mcp-config", c["args"])
        ajustes = json.loads(Path(self.opcion(c, "--settings")).read_text())
        self.assertIn("Read(~/.local/state/ws/claude/empresa/**)", ajustes["permissions"]["deny"])
        self.assertEqual(c["args"][-2:], ["-p", "hola"])

    def test_org_con_claude_propio(self):
        c = self.lanzar(self.m.ruta("empresa/api"))
        dir_claude = Path(c["env"]["CLAUDE_CONFIG_DIR"])
        self.assertEqual(dir_claude, self.m.estado("claude", "empresa"))
        for compartido in ("skills", "agents", "hooks"):  # compartidos con el perfil personal
            self.assertEqual((dir_claude / compartido).resolve(), (self.m.home / ".claude" / compartido).resolve())
        self.assertTrue((dir_claude / "CLAUDE.md").read_text().startswith("@~/.claude/CLAUDE.md"))
        self.assertIn("navegador-defecto", c["env"]["BROWSER"])
        self.assertIn("--strict-mcp-config", c["args"])
        mcp = json.loads(Path(self.opcion(c, "--mcp-config")).read_text())["mcpServers"]
        self.assertEqual(sorted(mcp), ["kindling", "tree-sitter"])
        # el secreto viaja en el entorno del proceso, nunca en el archivo
        self.assertEqual(mcp["kindling"]["headers"]["Authorization"], "Bearer ${KLING_TOKEN}")
        self.assertEqual(c["env"]["KLING_TOKEN"], "k-secreto")

    def test_excepcion_de_proyecto_usa_claude_personal(self):
        c = self.lanzar(self.m.ruta("empresa/propio"))
        self.assertNotIn("CLAUDE_CONFIG_DIR", c["env"])
        self.assertIn("--mcp-config", c["args"])  # pero con los MCPs de la org

    def test_subcomandos_no_reciben_flags_de_sesion(self):
        c = self.lanzar(self.m.ruta("empresa/api"), "mcp", "list")
        self.assertEqual(c["args"], ["mcp", "list"])
        self.assertIn("CLAUDE_CONFIG_DIR", c["env"])

    def test_motor_minimax(self):
        c = self.lanzar(self.m.ruta("lab/nodo"))
        self.assertEqual(c["env"]["ANTHROPIC_BASE_URL"], "https://api.minimax.io/anthropic")
        self.assertEqual(c["env"]["ANTHROPIC_MODEL"], "MiniMax-M2.7")
        self.assertEqual(c["env"]["ANTHROPIC_AUTH_TOKEN"], "mm-secreto")

    def test_secreto_ausente_cae_al_entorno(self):
        self.m._keychain.pop("ws/KLING_TOKEN")
        self.m.secreto("OTRO", "x")  # reescribe keychain.json sin KLING
        c = self.lanzar(self.m.ruta("empresa/api"), KLING_TOKEN="del-entorno")
        self.assertEqual(c["env"]["KLING_TOKEN"], "del-entorno")

    def test_sin_comando_de_secretos_solo_el_entorno(self):
        # ws no sabe de almacenes de secretos: sin [secretos].comando no llama a ninguno
        del self.m.cfg["secretos"]
        self.m.escribir()
        c = self.lanzar(self.m.ruta("empresa/api"), KLING_TOKEN="del-entorno")
        self.assertEqual(c["env"]["KLING_TOKEN"], "del-entorno")
        self.assertEqual(self.m.llamadas("security"), [])

    def test_variables_de_contexto_con_secreto(self):
        c = self.lanzar(self.m.ruta("empresa/api"))
        self.assertEqual(c["env"]["AWS_PROFILE"], "desde-proyecto")
        self.assertEqual(c["env"]["NPM_TOKEN"], "npm-secreto")


class Deny(CasoMundo):
    def deny(self, cwd):
        self.m.run(["claude"], cwd=cwd)
        a = self.m.ultima("claude")["args"]
        return json.loads(Path(a[a.index("--settings") + 1]).read_text())["permissions"]["deny"]

    def test_matriz_de_aislamiento(self):
        casos = {
            # contexto: (debe denegar, no debe denegar)
            self.m.home: (["Read(~/.local/state/ws/gh/empresa/**)", "Read(~/.local/state/ws/claude/empresa/**)"],
                          ["Read(~/.claude/projects/**)", "Read(~/.config/gh/hosts.yml)"]),
            self.m.ruta("empresa/api"): (["Read(~/.claude/projects/**)", "Read(~/.config/gh/hosts.yml)",
                                          "Read(~/.local/state/ws/gh/nueva/**)"],
                                         ["Read(~/.local/state/ws/gh/empresa/**)",
                                          "Read(~/.local/state/ws/claude/empresa/**)"]),
            self.m.ruta("aura/crm"): (["Read(~/.local/state/ws/gh/empresa/**)"],
                                      ["Read(~/.config/gh/hosts.yml)"]),
        }
        for cwd, (si, no) in casos.items():
            d = self.deny(cwd)
            with self.subTest(cwd=str(cwd)):
                for regla in si:
                    self.assertIn(regla, d)
                for regla in no:
                    self.assertNotIn(regla, d)
                self.assertIn("Bash(gh auth token:*)", d)

    def test_deny_de_tu_almacen_de_secretos(self):
        self.m.cfg["secretos"]["deny"] = ["Bash(secret-tool lookup:*)"]
        self.m.escribir()
        d = self.deny(self.m.home)
        self.assertIn("Bash(secret-tool lookup:*)", d)
        self.assertIn("Bash(security find-generic-password:*)", d)  # las de siempre siguen


class GhYOpencode(CasoMundo):
    def test_gh_por_cuenta(self):
        self.m.run(["gh", "api", "user"], cwd=self.m.ruta("empresa/api"))
        emp = self.m.ultima("gh")
        self.assertEqual(emp["env"]["GH_CONFIG_DIR"], str(self.m.estado("gh", "empresa")))
        self.assertIn("navegador-defecto", emp["env"]["GH_BROWSER"])
        self.m.run(["gh", "api", "user"], cwd=self.m.ruta("aura/crm"))
        self.assertNotIn("GH_CONFIG_DIR", self.m.ultima("gh")["env"])

    def test_navegador_propio_de_la_cuenta(self):
        self.m.cfg["github"]["empresa"]["navegador"] = "otro"
        self.m.escribir()
        self.m.run(["gh", "api", "user"], cwd=self.m.ruta("empresa/api"))
        self.assertIn("navegador-otro", self.m.ultima("gh")["env"]["GH_BROWSER"])
        # un nombre que no existe cae al de por defecto
        self.m.cfg["github"]["empresa"]["navegador"] = "no-existe"
        self.m.escribir()
        self.m.run(["gh", "api", "user"], cwd=self.m.ruta("empresa/api"))
        self.assertIn("navegador-defecto", self.m.ultima("gh")["env"]["GH_BROWSER"])

    def test_navegador_sin_definir_usa_el_del_sistema(self):
        del self.m.cfg["navegadores"]
        self.m.escribir()
        self.m.run(["gh", "api", "user"], cwd=self.m.ruta("empresa/api"))
        self.assertNotIn("GH_BROWSER", self.m.ultima("gh")["env"])

    def test_opencode_recibe_mcps_traducidos(self):
        self.m.run(["opencode"], cwd=self.m.ruta("empresa/api"))
        oc = self.m.ultima("opencode")
        cfg = json.loads(Path(oc["env"]["OPENCODE_CONFIG"]).read_text())["mcp"]
        self.assertEqual(cfg["kindling"]["type"], "remote")
        self.assertEqual(cfg["kindling"]["headers"]["Authorization"], "Bearer {env:KLING_TOKEN}")
        self.assertEqual(cfg["tree-sitter"]["command"], ["npx", "-y", "mcp-server-tree-sitter"])
        self.assertEqual(oc["env"]["KLING_TOKEN"], "k-secreto")

    def test_cualquier_programa_con_ws_exec(self):
        self.m.ws("exec", "opencode", "--version", cwd=self.m.ruta("empresa/api"))
        self.assertEqual(self.m.ultima("opencode")["env"]["AWS_PROFILE"], "desde-proyecto")


if __name__ == "__main__":
    unittest.main()
